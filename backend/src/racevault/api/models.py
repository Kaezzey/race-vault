"""Public V1 API request and response contracts."""

from __future__ import annotations

from typing import Self

from pydantic import Field, field_validator, model_validator

from racevault.extraction.models import ArtifactModel, ProvenanceRef
from racevault.retrieval.models import SearchFilters

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class RetrievalOptions(ArtifactModel):
    channel_limit: int = Field(default=50, ge=1, le=100)
    fusion_limit: int = Field(default=30, ge=1, le=100)
    rerank_limit: int = Field(default=15, ge=1, le=50)
    result_limit: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_depths(self) -> Self:
        if self.fusion_limit > self.channel_limit * 2:
            raise ValueError("fusion_limit exceeds the channel union")
        if self.rerank_limit > self.fusion_limit:
            raise ValueError("rerank_limit must not exceed fusion_limit")
        if self.result_limit > self.rerank_limit:
            raise ValueError("result_limit must not exceed rerank_limit")
        return self


class RetrievalSearchRequest(ArtifactModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    options: RetrievalOptions = Field(default_factory=RetrievalOptions)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value


class ModelIdentity(ArtifactModel):
    model_id: str
    model_revision: str


class CandidateCounts(ArtifactModel):
    lexical: int = Field(ge=0)
    semantic: int = Field(ge=0)
    fused: int = Field(ge=0)
    reranked: int = Field(ge=0)


class Citation(ArtifactModel):
    chunk_id: str
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    source_path: str
    source_filename: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    page_numbers: tuple[int, ...]
    section_path: tuple[str, ...]
    clause_reference: str | None
    evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    element_ids: tuple[str, ...]
    table_ids: tuple[str, ...]
    provenance: tuple[ProvenanceRef, ...]


class RetrievalDiagnostics(ArtifactModel):
    lexical_rank: int | None = Field(default=None, ge=1)
    lexical_score: float | None = None
    semantic_rank: int | None = Field(default=None, ge=1)
    semantic_score: float | None = None
    fused_rank: int = Field(ge=1)
    rrf_score: float = Field(ge=0)
    reranker_score: float = Field(ge=0, le=1)


class RetrievalResult(ArtifactModel):
    rank: int = Field(ge=1)
    evidence_text: str
    document_class: str
    chunk_kind: str
    source_role: str | None
    source_metadata: dict[str, object]
    citation: Citation
    diagnostics: RetrievalDiagnostics


class RetrievalSearchResponse(ArtifactModel):
    query: str
    filters: SearchFilters
    resolved_championships: tuple[str, ...] = ()
    counts: CandidateCounts
    embedding_model: ModelIdentity
    reranker_model: ModelIdentity
    results: tuple[RetrievalResult, ...]


class SourceComparisonRequest(ArtifactModel):
    query: str = Field(min_length=1, max_length=2000)
    left_source_sha256: str = Field(pattern=SHA256_PATTERN)
    right_source_sha256: str = Field(pattern=SHA256_PATTERN)
    result_limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value

    @model_validator(mode="after")
    def sources_must_differ(self) -> Self:
        if self.left_source_sha256 == self.right_source_sha256:
            raise ValueError("comparison sources must differ")
        return self


class SourceComparisonResponse(ArtifactModel):
    query: str
    left: RetrievalSearchResponse
    right: RetrievalSearchResponse
