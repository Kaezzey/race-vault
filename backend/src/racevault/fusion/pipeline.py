"""Hybrid retrieval orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from racevault.fusion.models import (
    FusedCandidate,
    HybridSearchRequest,
    HybridSearchResponse,
)
from racevault.fusion.reranker import CandidateReranker, rerank_candidates
from racevault.fusion.rrf import reciprocal_rank_fusion
from racevault.lexical.models import LexicalSearchRequest, LexicalSearchResponse
from racevault.semantic.embedder import DenseEmbedder
from racevault.semantic.models import SemanticSearchRequest, SemanticSearchResponse
from racevault.semantic.pipeline import semantic_search
from racevault.semantic.store import SemanticStore
from racevault.telemetry import metrics, span


class LexicalSearcher(Protocol):
    def search(self, request: LexicalSearchRequest) -> LexicalSearchResponse: ...


@dataclass(frozen=True)
class HybridStages:
    lexical: LexicalSearchResponse
    semantic: SemanticSearchResponse
    fused: tuple[FusedCandidate, ...]
    reranked: tuple[FusedCandidate, ...]


def hybrid_search_stages(
    request: HybridSearchRequest,
    *,
    lexical: LexicalSearcher,
    semantic_embedder: DenseEmbedder,
    semantic_store: SemanticStore,
    reranker: CandidateReranker,
) -> HybridStages:
    if request.reranker != reranker.spec:
        raise ValueError("request reranker does not match the loaded reranker")
    with span("retrieval.lexical"):
        lexical_response = lexical.search(
            LexicalSearchRequest(
                query=request.query,
                limit=request.channel_limit,
                filters=request.filters,
            )
        )
    with span("retrieval.semantic"):
        semantic_response = semantic_search(
            SemanticSearchRequest(
                query=request.query,
                limit=request.channel_limit,
                filters=request.filters,
                model_id=request.embedding_model_id,
                model_revision=request.embedding_model_revision,
            ),
            embedder=semantic_embedder,
            store=semantic_store,
        )
    with span("retrieval.fusion"):
        fused = reciprocal_rank_fusion(
            lexical_response.hits,
            semantic_response.hits,
            settings=request.rrf,
            limit=request.fusion_limit,
        )
    with span("retrieval.rerank"):
        reranked = rerank_candidates(
            request.query,
            fused,
            reranker=reranker,
            limit=request.rerank_limit,
        )
    for stage_name, count in (
        ("lexical", len(lexical_response.hits)),
        ("semantic", len(semantic_response.hits)),
        ("fused", len(fused)),
        ("reranked", len(reranked)),
    ):
        metrics.observe(
            "racevault_retrieval_candidates",
            count,
            labels={"stage": stage_name},
            buckets=(0, 1, 3, 5, 10, 15, 30, 50, 100),
        )
    return HybridStages(
        lexical=lexical_response,
        semantic=semantic_response,
        fused=fused,
        reranked=reranked,
    )


def hybrid_search(
    request: HybridSearchRequest,
    *,
    lexical: LexicalSearcher,
    semantic_embedder: DenseEmbedder,
    semantic_store: SemanticStore,
    reranker: CandidateReranker,
) -> HybridSearchResponse:
    stages = hybrid_search_stages(
        request,
        lexical=lexical,
        semantic_embedder=semantic_embedder,
        semantic_store=semantic_store,
        reranker=reranker,
    )
    return HybridSearchResponse(
        query=request.query,
        lexical_hits=len(stages.lexical.hits),
        semantic_hits=len(stages.semantic.hits),
        fused_candidates=len(stages.fused),
        reranked_candidates=len(stages.reranked),
        results=stages.reranked[: request.result_limit],
    )
