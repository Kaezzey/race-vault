"""Contracts for rank fusion and cross-encoder reranking."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from racevault.extraction.models import ArtifactModel
from racevault.retrieval.models import EvidenceHit, SearchFilters
from racevault.semantic.models import DEFAULT_MODEL_ID, DEFAULT_MODEL_REVISION

DEFAULT_RERANKER_ID = "BAAI/bge-reranker-v2-m3"
DEFAULT_RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"


class RrfSettings(ArtifactModel):
    rank_constant: int = Field(default=60, ge=1, le=1000)
    lexical_weight: float = Field(default=1.0, gt=0)
    semantic_weight: float = Field(default=1.0, gt=0)


class RerankerSpec(ArtifactModel):
    model_id: str = DEFAULT_RERANKER_ID
    model_revision: str = DEFAULT_RERANKER_REVISION
    max_tokens: int = Field(default=8192, ge=1, le=8192)
    normalized_scores: Literal[True] = True


class FusedCandidate(EvidenceHit):
    lexical_rank: int | None = Field(default=None, ge=1)
    lexical_score: float | None = None
    semantic_rank: int | None = Field(default=None, ge=1)
    semantic_score: float | None = None
    rrf_score: float = Field(ge=0)
    fused_rank: int = Field(ge=1)
    reranker_score: float | None = Field(default=None, ge=0, le=1)
    final_rank: int | None = Field(default=None, ge=1)


class HybridSearchRequest(ArtifactModel):
    query: str = Field(min_length=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    channel_limit: int = Field(default=50, ge=1, le=100)
    fusion_limit: int = Field(default=30, ge=1, le=100)
    rerank_limit: int = Field(default=15, ge=1, le=100)
    result_limit: int = Field(default=10, ge=1, le=100)
    rrf: RrfSettings = Field(default_factory=RrfSettings)
    embedding_model_id: str = DEFAULT_MODEL_ID
    embedding_model_revision: str = DEFAULT_MODEL_REVISION
    reranker: RerankerSpec = Field(default_factory=RerankerSpec)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value

    @model_validator(mode="after")
    def validate_depths(self) -> Self:
        if self.fusion_limit > self.channel_limit * 2:
            raise ValueError("fusion_limit exceeds the maximum channel union")
        if self.rerank_limit > self.fusion_limit:
            raise ValueError("rerank_limit must not exceed fusion_limit")
        if self.result_limit > self.rerank_limit:
            raise ValueError("result_limit must not exceed rerank_limit")
        return self


class HybridSearchResponse(ArtifactModel):
    query: str
    lexical_hits: int = Field(ge=0)
    semantic_hits: int = Field(ge=0)
    fused_candidates: int = Field(ge=0)
    reranked_candidates: int = Field(ge=0)
    results: tuple[FusedCandidate, ...]
