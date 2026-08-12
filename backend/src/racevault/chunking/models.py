"""Versioned classification and chunk artifact models."""

from __future__ import annotations

import enum
import hashlib
from typing import Self

from pydantic import Field, model_validator

from racevault.extraction.models import ArtifactModel, ProvenanceRef, SourceArtifact


class DocumentClass(enum.StrEnum):
    REGULATION = "regulation"
    TECHNICAL_MANUAL = "technical_manual"
    TYRE_DATA = "tyre_data"
    PART_CATALOGUE = "part_catalogue"
    COMPONENT_MANUAL = "component_manual"
    ENGINEERING_REFERENCE = "engineering_reference"
    UNKNOWN = "unknown"


class ChunkStrategy(enum.StrEnum):
    CLAUSE = "clause"
    SECTION_EVIDENCE = "section_evidence"
    PAGE_TABLE = "page_table"
    HIERARCHICAL_PASSAGE = "hierarchical_passage"
    GENERIC_EVIDENCE = "generic_evidence"


class ChunkKind(enum.StrEnum):
    CLAUSE = "clause"
    SECTION = "section"
    PASSAGE = "passage"
    TABLE = "table"
    PAGE = "page"
    EVIDENCE = "evidence"


class ClassificationArtifact(ArtifactModel):
    document_class: DocumentClass
    strategy: ChunkStrategy
    method: str
    rule: str


class ChunkingSettings(ArtifactModel):
    max_characters: int = Field(default=2400, ge=200)
    include_section_context: bool = True
    strategy_version: str = "1.0"


class ChunkArtifact(ArtifactModel):
    chunk_id: str = Field(pattern=r"^chk_[0-9a-f]{32}$")
    ordinal: int = Field(ge=0)
    kind: ChunkKind
    strategy: ChunkStrategy
    document_class: DocumentClass
    evidence_text: str = Field(min_length=1)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contextual_text: str = Field(min_length=1)
    contextual_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_path: tuple[str, ...]
    clause_reference: str | None = None
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    page_numbers: tuple[int, ...] = Field(min_length=1)
    element_ids: tuple[str, ...] = Field(min_length=1)
    table_ids: tuple[str, ...]
    provenance: tuple[ProvenanceRef, ...] = Field(min_length=1)
    character_count: int = Field(ge=1)
    oversize: bool

    @model_validator(mode="after")
    def validate_content(self) -> Self:
        if self.evidence_sha256 != hashlib.sha256(
            self.evidence_text.encode()
        ).hexdigest():
            raise ValueError("evidence_sha256 does not match evidence_text")
        if self.contextual_sha256 != hashlib.sha256(
            self.contextual_text.encode()
        ).hexdigest():
            raise ValueError("contextual_sha256 does not match contextual_text")
        if self.character_count != len(self.contextual_text):
            raise ValueError("character_count does not match contextual_text")
        if self.page_numbers != tuple(sorted(set(self.page_numbers))):
            raise ValueError("page_numbers must be unique and sorted")
        if self.page_start != self.page_numbers[0]:
            raise ValueError("page_start must match the first page number")
        if self.page_end != self.page_numbers[-1]:
            raise ValueError("page_end must match the last page number")
        if self.page_end < self.page_start:
            raise ValueError("page_end must not precede page_start")
        if len(set(self.element_ids)) != len(self.element_ids):
            raise ValueError("element_ids must be unique within a chunk")
        if len(set(self.table_ids)) != len(self.table_ids):
            raise ValueError("table_ids must be unique within a chunk")
        if self.kind is ChunkKind.TABLE and len(self.table_ids) != 1:
            raise ValueError("table chunks must reference exactly one table")
        return self


class ChunkingProvenance(ArtifactModel):
    pipeline: str
    pipeline_version: str
    extraction_file: str
    extraction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings: ChunkingSettings


class ChunkingStatistics(ArtifactModel):
    chunks: int = Field(ge=0)
    table_chunks: int = Field(ge=0)
    oversize_chunks: int = Field(ge=0)
    evidence_characters: int = Field(ge=0)


class ChunkingArtifact(ArtifactModel):
    schema_name: str = "racevault.chunking"
    schema_version: str = "1.0"
    source: SourceArtifact
    classification: ClassificationArtifact
    provenance: ChunkingProvenance
    chunks: tuple[ChunkArtifact, ...]
    statistics: ChunkingStatistics

    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        chunk_ids = [chunk.chunk_id for chunk in self.chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("chunk IDs must be unique")
        if [chunk.ordinal for chunk in self.chunks] != list(range(len(self.chunks))):
            raise ValueError("chunk ordinals must be consecutive")

        element_ids = [
            element_id for chunk in self.chunks for element_id in chunk.element_ids
        ]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("an extraction element appears in more than one chunk")

        expected = ChunkingStatistics(
            chunks=len(self.chunks),
            table_chunks=sum(chunk.kind is ChunkKind.TABLE for chunk in self.chunks),
            oversize_chunks=sum(chunk.oversize for chunk in self.chunks),
            evidence_characters=sum(len(chunk.evidence_text) for chunk in self.chunks),
        )
        if self.statistics != expected:
            raise ValueError("statistics do not match chunk contents")
        return self
