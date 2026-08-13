"""Hybrid retrieval orchestration."""

from __future__ import annotations

from typing import Protocol

from racevault.fusion.models import HybridSearchRequest, HybridSearchResponse
from racevault.fusion.reranker import CandidateReranker, rerank_candidates
from racevault.fusion.rrf import reciprocal_rank_fusion
from racevault.lexical.models import LexicalSearchRequest, LexicalSearchResponse
from racevault.semantic.embedder import DenseEmbedder
from racevault.semantic.models import SemanticSearchRequest
from racevault.semantic.pipeline import semantic_search
from racevault.semantic.store import SemanticStore


class LexicalSearcher(Protocol):
    def search(self, request: LexicalSearchRequest) -> LexicalSearchResponse: ...


def hybrid_search(
    request: HybridSearchRequest,
    *,
    lexical: LexicalSearcher,
    semantic_embedder: DenseEmbedder,
    semantic_store: SemanticStore,
    reranker: CandidateReranker,
) -> HybridSearchResponse:
    if request.reranker != reranker.spec:
        raise ValueError("request reranker does not match the loaded reranker")
    lexical_response = lexical.search(
        LexicalSearchRequest(
            query=request.query,
            limit=request.channel_limit,
            filters=request.filters,
        )
    )
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
    fused = reciprocal_rank_fusion(
        lexical_response.hits,
        semantic_response.hits,
        settings=request.rrf,
        limit=request.fusion_limit,
    )
    reranked = rerank_candidates(
        request.query,
        fused,
        reranker=reranker,
        limit=request.rerank_limit,
    )
    return HybridSearchResponse(
        query=request.query,
        lexical_hits=len(lexical_response.hits),
        semantic_hits=len(semantic_response.hits),
        fused_candidates=len(fused),
        reranked_candidates=len(reranked),
        results=reranked[: request.result_limit],
    )
