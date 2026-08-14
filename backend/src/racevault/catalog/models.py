"""Source catalogue contracts."""

from __future__ import annotations

from pydantic import Field

from racevault.api.models import SHA256_PATTERN
from racevault.extraction.models import ArtifactModel, ProvenanceRef


class SourceSummary(ArtifactModel):
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    source_path: str
    filename: str
    source_role: str | None
    title: str | None
    document_type: str
    vehicle_generation: str | None
    championship: str | None
    season: int | None
    revision: str | None
    authority: str
    language: str | None
    page_count: int | None
    extra_metadata: dict[str, object]
    chunk_count: int = Field(ge=0)
    embedding_count: int = Field(ge=0)


class SourceListResponse(ArtifactModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    sources: tuple[SourceSummary, ...]


class SourceChunk(ArtifactModel):
    chunk_id: str
    ordinal: int = Field(ge=0)
    kind: str
    evidence_text: str
    evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    section_path: tuple[str, ...]
    clause_reference: str | None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    page_numbers: tuple[int, ...]
    table_ids: tuple[str, ...]
    provenance: tuple[ProvenanceRef, ...]
    oversize: bool


class SourceChunkListResponse(ArtifactModel):
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    chunks: tuple[SourceChunk, ...]


class CorpusStatus(ArtifactModel):
    documents: int = Field(ge=0)
    chunks: int = Field(ge=0)
    embeddings: int = Field(ge=0)
    embedded_documents: int = Field(ge=0)
    opensearch_chunks: int = Field(ge=0)
    consistent: bool
    embedding_model_id: str
    embedding_model_revision: str
