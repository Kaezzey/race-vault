"""Lazy runtime services used by V1 API routes."""

from __future__ import annotations

import gc
import importlib
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
from racevault.fusion.models import (
    FusedCandidate,
    HybridSearchRequest,
    HybridSearchResponse,
    RerankerSpec,
)
from racevault.fusion.pipeline import hybrid_search
from racevault.fusion.reranker import BgeReranker
from racevault.lexical.client import OpenSearchClient
from racevault.retrieval.editions import resolve_latest_edition
from racevault.retrieval.models import SearchFilters
from racevault.retrieval.query_scope import (
    remove_query_scope_terms,
    resolve_query_filter_scopes,
)
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.store import SemanticStore
from racevault.telemetry import span


class RetrievalService(Protocol):
    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse: ...

    def resolve_scopes(
        self,
        query: str,
        filters: SearchFilters,
    ) -> tuple[SearchFilters, ...]: ...


def _interleave_scoped_results(
    responses: tuple[HybridSearchResponse, ...],
    *,
    limit: int,
) -> tuple[FusedCandidate, ...]:
    """Keep each requested metadata scope represented in the final results."""

    combined: list[FusedCandidate] = []
    depth = 0
    while len(combined) < limit:
        added = False
        for response in responses:
            if depth >= len(response.results):
                continue
            combined.append(
                response.results[depth].model_copy(
                    update={"final_rank": len(combined) + 1}
                )
            )
            added = True
            if len(combined) == limit:
                break
        if not added:
            break
        depth += 1
    return tuple(combined)


class HybridRetrievalService:
    """Load local models on the first request and serialize GPU inference."""

    def __init__(self, settings: Settings, catalog: CatalogStore) -> None:
        self._settings = settings
        self._catalog = catalog
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
        self._lexical: OpenSearchClient | None = None
        self._semantic_store: SemanticStore | None = None
        self._lock = threading.Lock()

    def _clients(self) -> tuple[OpenSearchClient, SemanticStore]:
        """Reuse one HTTP client and connection string across every search.

        A compound question runs one search per facet plus a full-question
        search, and building an OpenSearch client costs more than the query it
        then issues.
        """

        if self._lexical is None:
            self._lexical = OpenSearchClient(
                base_url=self._settings.opensearch_url,
                index_name=self._settings.opensearch_index_name,
                timeout_seconds=self._settings.opensearch_timeout_seconds,
            )
        if self._semantic_store is None:
            timeout = max(
                1, math.ceil(self._settings.dependency_timeout_seconds)
            )
            self._semantic_store = SemanticStore(
                f"{self._settings.psycopg_conninfo} connect_timeout={timeout}"
            )
        return self._lexical, self._semantic_store

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

    def resolve_scopes(
        self,
        query: str,
        filters: SearchFilters,
    ) -> tuple[SearchFilters, ...]:
        """Resolve named metadata scopes and narrow them to current editions.

        Callers use this to plan work before the retrieval models are loaded.
        """

        editions = self._catalog.list_document_editions()
        scopes = resolve_query_filter_scopes(
            query,
            filters,
            championships=tuple(
                dict.fromkeys(edition.championship for edition in editions)
            ),
            vehicle_generations=self._catalog.list_vehicle_generations(),
        )
        if not self._settings.retrieval_prefer_latest_edition:
            return scopes
        return tuple(
            resolve_latest_edition(scope, editions) for scope in scopes
        )

    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse:
        with span("retrieval.scope_resolution"):
            filter_scopes = self.resolve_scopes(request.query, request.filters)
            content_query = remove_query_scope_terms(request.query, filter_scopes)
        with self._lock:
            embedder, reranker = self._models()
            lexical, semantic_store = self._clients()
            options = request.options
            responses = tuple(
                hybrid_search(
                    HybridSearchRequest(
                        query=content_query,
                        filters=filters,
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
                    semantic_store=semantic_store,
                    reranker=reranker,
                )
                for filters in filter_scopes
            )
        if len(responses) == 1:
            candidates = responses[0].results
            response_filters = filter_scopes[0]
        else:
            candidates = _interleave_scoped_results(
                responses,
                limit=request.options.result_limit,
            )
            response_filters = request.filters
        results = []
        for item in candidates:
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
            query=request.query,
            filters=response_filters,
            resolved_championships=tuple(
                filters.championship
                for filters in filter_scopes
                if filters.championship is not None
            ),
            resolved_scopes=filter_scopes,
            counts=CandidateCounts(
                lexical=sum(item.lexical_hits for item in responses),
                semantic=sum(item.semantic_hits for item in responses),
                fused=sum(item.fused_candidates for item in responses),
                reranked=sum(item.reranked_candidates for item in responses),
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

    def close(self) -> None:
        """Release the shared search clients on application shutdown."""

        with self._lock:
            if self._lexical is not None:
                self._lexical.close()
                self._lexical = None
            self._semantic_store = None

    def release_models(self) -> None:
        """Release local retrieval models and cached CUDA allocations."""

        with self._lock:
            used_cuda = any(
                model is not None and model.device == "cuda"
                for model in (self._embedder, self._reranker)
            )
            self._embedder = None
            self._reranker = None
            gc.collect()
            if used_cuda:
                torch = importlib.import_module("torch")
                torch.cuda.empty_cache()


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
