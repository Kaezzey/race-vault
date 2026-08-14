"""Lazy runtime services used by V1 API routes."""

from __future__ import annotations

import math
import threading
from typing import Protocol, cast

from fastapi import Request

from racevault.api.models import (
    CandidateCounts,
    Citation,
    ModelIdentity,
    RetrievalDiagnostics,
    RetrievalResult,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from racevault.catalog.store import CatalogStore
from racevault.config import Settings, get_settings
from racevault.fusion.models import HybridSearchRequest, RerankerSpec
from racevault.fusion.pipeline import hybrid_search
from racevault.fusion.reranker import BgeReranker
from racevault.lexical.client import OpenSearchClient
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.store import SemanticStore


class RetrievalService(Protocol):
    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse: ...


class HybridRetrievalService:
    """Load local models on the first request and serialize GPU inference."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedding_spec = EmbeddingModelSpec(
            model_id=settings.semantic_model_id,
            model_revision=settings.semantic_model_revision,
            max_tokens=settings.semantic_max_tokens,
        )
        self._reranker_spec = RerankerSpec(
            model_id=settings.reranker_model_id,
            model_revision=settings.reranker_model_revision,
            max_tokens=settings.reranker_max_tokens,
        )
        self._embedder: BgeM3Embedder | None = None
        self._reranker: BgeReranker | None = None
        self._lock = threading.Lock()

    def _models(self) -> tuple[BgeM3Embedder, BgeReranker]:
        if self._embedder is None:
            self._embedder = BgeM3Embedder(
                spec=self._embedding_spec,
                device=self._settings.api_model_device,
                batch_size=1,
                local_files_only=self._settings.api_local_files_only,
            )
        if self._reranker is None:
            self._reranker = BgeReranker(
                spec=self._reranker_spec,
                device=self._settings.api_model_device,
                batch_size=self._settings.reranker_batch_size,
                local_files_only=self._settings.api_local_files_only,
            )
        return self._embedder, self._reranker

    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse:
        with self._lock:
            embedder, reranker = self._models()
            options = request.options
            with OpenSearchClient(
                base_url=self._settings.opensearch_url,
                index_name=self._settings.opensearch_index_name,
                timeout_seconds=self._settings.opensearch_timeout_seconds,
            ) as lexical:
                response = hybrid_search(
                    HybridSearchRequest(
                        query=request.query,
                        filters=request.filters,
                        channel_limit=options.channel_limit,
                        fusion_limit=options.fusion_limit,
                        rerank_limit=options.rerank_limit,
                        result_limit=options.result_limit,
                        embedding_model_id=self._embedding_spec.model_id,
                        embedding_model_revision=(
                            self._embedding_spec.model_revision
                        ),
                        reranker=self._reranker_spec,
                    ),
                    lexical=lexical,
                    semantic_embedder=embedder,
                    semantic_store=SemanticStore(
                        self._settings.psycopg_conninfo
                        + " connect_timeout="
                        + str(
                            max(
                                1,
                                math.ceil(
                                    self._settings.dependency_timeout_seconds
                                ),
                            )
                        )
                    ),
                    reranker=reranker,
                )
        results = []
        for item in response.results:
            if item.final_rank is None or item.reranker_score is None:
                raise RuntimeError("retrieval returned an incomplete final result")
            results.append(
                RetrievalResult(
                    rank=item.final_rank,
                    evidence_text=item.evidence_text,
                    document_class=item.document_class,
                    chunk_kind=item.kind,
                    source_role=item.source_role,
                    source_metadata=item.source_metadata,
                    citation=Citation(
                        chunk_id=item.chunk_id,
                        source_sha256=item.source_sha256,
                        source_path=item.source_path,
                        source_filename=item.source_filename,
                        page_start=item.page_start,
                        page_end=item.page_end,
                        page_numbers=item.page_numbers,
                        section_path=item.section_path,
                        clause_reference=item.clause_reference,
                        evidence_sha256=item.evidence_sha256,
                        element_ids=item.element_ids,
                        table_ids=item.table_ids,
                        provenance=item.provenance,
                    ),
                    diagnostics=RetrievalDiagnostics(
                        lexical_rank=item.lexical_rank,
                        lexical_score=item.lexical_score,
                        semantic_rank=item.semantic_rank,
                        semantic_score=item.semantic_score,
                        fused_rank=item.fused_rank,
                        rrf_score=item.rrf_score,
                        reranker_score=item.reranker_score,
                    ),
                )
            )
        return RetrievalSearchResponse(
            query=response.query,
            filters=request.filters,
            counts=CandidateCounts(
                lexical=response.lexical_hits,
                semantic=response.semantic_hits,
                fused=response.fused_candidates,
                reranked=response.reranked_candidates,
            ),
            embedding_model=ModelIdentity(
                model_id=self._embedding_spec.model_id,
                model_revision=self._embedding_spec.model_revision,
            ),
            reranker_model=ModelIdentity(
                model_id=self._reranker_spec.model_id,
                model_revision=self._reranker_spec.model_revision,
            ),
            results=tuple(results),
        )


def get_retrieval_service(request: Request) -> RetrievalService:
    return cast(RetrievalService, request.app.state.retrieval_service)


def get_catalog_store(request: Request) -> CatalogStore:
    return cast(CatalogStore, request.app.state.catalog_store)


def get_embedding_spec() -> EmbeddingModelSpec:
    settings = get_settings()
    return EmbeddingModelSpec(
        model_id=settings.semantic_model_id,
        model_revision=settings.semantic_model_revision,
        max_tokens=settings.semantic_max_tokens,
    )
