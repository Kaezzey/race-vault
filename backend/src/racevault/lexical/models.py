"""Contracts for lexical indexing and search."""

from __future__ import annotations

from pydantic import Field, field_validator

from racevault.extraction.models import ArtifactModel, ProvenanceRef


class SearchFilters(ArtifactModel):
    source_sha256: str | None = None
    source_role: str | None = None
    document_class: str | None = None
    authority: str | None = None
    vehicle_generation: str | None = None
    championship: str | None = None
    season: int | None = Field(default=None, ge=1900, le=2200)
    revision: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    chunk_kind: str | None = None
    oversize: bool | None = None


class LexicalSearchRequest(ArtifactModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value


class LexicalSearchHit(ArtifactModel):
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
    highlights: tuple[str, ...] = ()


class LexicalSearchResponse(ArtifactModel):
    query: str
    total: int = Field(ge=0)
    hits: tuple[LexicalSearchHit, ...]


class IndexingResult(ArtifactModel):
    index_name: str
    source_sha256: str
    indexed_chunks: int = Field(ge=0)
    removed_chunks: int = Field(ge=0)
