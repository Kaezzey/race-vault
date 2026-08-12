"""Versioned extraction artifact models."""

from __future__ import annotations

import hashlib
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArtifactModel(BaseModel):
    """Base model for strict, immutable artifact records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BoundingBox(ArtifactModel):
    left: float
    top: float
    right: float
    bottom: float
    coordinate_origin: str


class ProvenanceRef(ArtifactModel):
    page_number: int = Field(ge=1)
    bbox: BoundingBox
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_char_span(self) -> Self:
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class PageBlock(ArtifactModel):
    block_number: int = Field(ge=0)
    bbox: BoundingBox
    text: str


class PageArtifact(ArtifactModel):
    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: int
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocks: tuple[PageBlock, ...]

    @model_validator(mode="after")
    def validate_text_hash(self) -> Self:
        expected = hashlib.sha256(self.text.encode()).hexdigest()
        if self.text_sha256 != expected:
            raise ValueError("text_sha256 does not match page text")
        return self


class TableCell(ArtifactModel):
    row_start: int = Field(ge=0)
    row_end: int = Field(ge=1)
    column_start: int = Field(ge=0)
    column_end: int = Field(ge=1)
    text: str
    is_column_header: bool = False
    is_row_header: bool = False
    bbox: BoundingBox | None = None


class TableArtifact(ArtifactModel):
    table_id: str = Field(pattern=r"^tbl_[0-9a-f]{32}$")
    docling_ref: str
    reading_order: int = Field(ge=0)
    section_path: tuple[str, ...]
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    cells: tuple[TableCell, ...]
    provenance: tuple[ProvenanceRef, ...] = Field(min_length=1)


class ElementArtifact(ArtifactModel):
    element_id: str = Field(pattern=r"^el_[0-9a-f]{32}$")
    docling_ref: str
    label: str
    content_layer: str
    reading_order: int = Field(ge=0)
    text: str
    heading_level: int | None = Field(default=None, ge=1, le=100)
    section_path: tuple[str, ...]
    provenance: tuple[ProvenanceRef, ...] = Field(min_length=1)
    table_id: str | None = None


class SourceArtifact(ArtifactModel):
    relative_path: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    page_count: int = Field(gt=0)
    role: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ExtractorSettings(ArtifactModel):
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    device: str
    num_threads: int = Field(ge=1)
    ocr_enabled: bool
    table_structure_enabled: bool
    heading_hierarchy_enabled: bool
    model_compilation_enabled: bool

    @model_validator(mode="after")
    def validate_page_range(self) -> Self:
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class ExtractionProvenance(ArtifactModel):
    pipeline: str
    pipeline_version: str
    docling_version: str
    docling_core_version: str
    pymupdf_version: str
    raw_docling_file: str
    raw_docling_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings: ExtractorSettings


class ExtractionStatistics(ArtifactModel):
    extracted_pages: int = Field(ge=1)
    elements: int = Field(ge=0)
    tables: int = Field(ge=0)
    page_text_characters: int = Field(ge=0)


class ExtractionArtifact(ArtifactModel):
    schema_name: str = "racevault.extraction"
    schema_version: str = "1.0"
    source: SourceArtifact
    provenance: ExtractionProvenance
    pages: tuple[PageArtifact, ...]
    elements: tuple[ElementArtifact, ...]
    tables: tuple[TableArtifact, ...]
    statistics: ExtractionStatistics

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        page_numbers = [page.page_number for page in self.pages]
        if page_numbers != sorted(set(page_numbers)):
            raise ValueError("pages must be unique and sorted")

        expected_pages = list(
            range(
                self.provenance.settings.page_start,
                self.provenance.settings.page_end + 1,
            )
        )
        if page_numbers != expected_pages:
            raise ValueError("pages must cover the configured page range")

        available_pages = set(page_numbers)
        table_ids = {table.table_id for table in self.tables}
        if len(table_ids) != len(self.tables):
            raise ValueError("table IDs must be unique")

        element_ids = {element.element_id for element in self.elements}
        if len(element_ids) != len(self.elements):
            raise ValueError("element IDs must be unique")

        for element in self.elements:
            if element.table_id is not None and element.table_id not in table_ids:
                raise ValueError(f"unknown table reference: {element.table_id}")
            for reference in element.provenance:
                if reference.page_number not in available_pages:
                    raise ValueError("element references a page outside the artifact")

        for table in self.tables:
            for reference in table.provenance:
                if reference.page_number not in available_pages:
                    raise ValueError("table references a page outside the artifact")

        expected_statistics = ExtractionStatistics(
            extracted_pages=len(self.pages),
            elements=len(self.elements),
            tables=len(self.tables),
            page_text_characters=sum(len(page.text) for page in self.pages),
        )
        if self.statistics != expected_statistics:
            raise ValueError("statistics do not match artifact contents")
        return self
