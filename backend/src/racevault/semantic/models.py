"""Contracts for dense embedding and semantic retrieval."""

from __future__ import annotations

import math
from typing import Self

from pydantic import Field, field_validator, model_validator

from racevault.extraction.models import ArtifactModel, ProvenanceRef
from racevault.retrieval.models import SearchFilters

DEFAULT_MODEL_ID = "BAAI/bge-m3"
DEFAULT_MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
BGE_M3_DIMENSIONS = 1024
BGE_M3_MAX_TOKENS = 8192


class EmbeddingModelSpec(ArtifactModel):
    model_id: str = DEFAULT_MODEL_ID
    model_revision: str = DEFAULT_MODEL_REVISION
    dimensions: int = BGE_M3_DIMENSIONS
    normalized: bool = True
    max_tokens: int = Field(default=BGE_M3_MAX_TOKENS, ge=1, le=8192)


class DenseVector(ArtifactModel):
    values: tuple[float, ...]

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if len(self.values) != BGE_M3_DIMENSIONS:
            raise ValueError(f"dense vector must have {BGE_M3_DIMENSIONS} values")
        if not all(math.isfinite(value) for value in self.values):
            raise ValueError("dense vector values must be finite")
        norm = math.sqrt(sum(value * value for value in self.values))
        if not math.isclose(norm, 1.0, rel_tol=1e-3, abs_tol=1e-3):
            raise ValueError("dense vector must be L2-normalized")
        return self


class EmbeddedChunk(ArtifactModel):
    chunk_id: str
    input_sha256: str
    vector: DenseVector


class SemanticIndexingResult(ArtifactModel):
    source_sha256: str
    artifact_id: str
    total_chunks: int = Field(ge=0)
    generated_embeddings: int = Field(ge=0)
    reused_embeddings: int = Field(ge=0)
    removed_stale_chunks: int = Field(ge=0)


class SemanticSearchRequest(ArtifactModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    model_id: str = DEFAULT_MODEL_ID
    model_revision: str = DEFAULT_MODEL_REVISION

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value


class SemanticSearchHit(ArtifactModel):
    chunk_id: str
    artifact_id: str
    ordinal: int
    score: float
    evidence_text: str
    evidence_sha256: str
    contextual_text: str
    contextual_sha256: str
    source_path: str
    source_filename: str
    source_sha256: str
    source_role: str | None
    source_metadata: dict[str, object]
    document_class: str
    strategy: str
    kind: str
    section_path: tuple[str, ...]
    clause_reference: str | None
    page_start: int
    page_end: int
    page_numbers: tuple[int, ...]
    element_ids: tuple[str, ...]
    table_ids: tuple[str, ...]
    provenance: tuple[ProvenanceRef, ...]
    character_count: int
    oversize: bool
    model_id: str
    model_revision: str


class SemanticSearchResponse(ArtifactModel):
    query: str
    hits: tuple[SemanticSearchHit, ...]
