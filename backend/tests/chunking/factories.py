"""Factories for classification and chunking tests."""

from __future__ import annotations

from racevault.extraction.io import sha256_text
from racevault.extraction.models import (
    BoundingBox,
    ElementArtifact,
    ExtractionArtifact,
    ExtractionProvenance,
    ExtractionStatistics,
    ExtractorSettings,
    PageArtifact,
    ProvenanceRef,
    SourceArtifact,
    TableArtifact,
    TableCell,
)

SOURCE_SHA256 = "a" * 64
RAW_SHA256 = "b" * 64


def provenance(page: int) -> tuple[ProvenanceRef, ...]:
    return (
        ProvenanceRef(
            page_number=page,
            bbox=BoundingBox(
                left=10,
                top=20,
                right=100,
                bottom=40,
                coordinate_origin="TOPLEFT",
            ),
            char_start=0,
            char_end=10,
        ),
    )


def element(
    number: int,
    text: str,
    *,
    page: int = 1,
    label: str = "text",
    section_path: tuple[str, ...] = (),
    table_id: str | None = None,
    content_layer: str = "body",
) -> ElementArtifact:
    return ElementArtifact(
        element_id=f"el_{number:032x}",
        docling_ref=f"#/texts/{number}",
        label=label,
        content_layer=content_layer,
        reading_order=number,
        text=text,
        heading_level=1 if label in {"title", "section_header"} else None,
        section_path=section_path,
        provenance=provenance(page),
        table_id=table_id,
    )


def extraction_artifact(
    elements: tuple[ElementArtifact, ...],
    *,
    document_type: str | None = "technical_manual",
    relative_path: str = "Porsche Technical Manuals/manual.pdf",
    page_count: int = 2,
    tables: tuple[TableArtifact, ...] = (),
) -> ExtractionArtifact:
    pages = tuple(
        PageArtifact(
            page_number=page_number,
            width=600,
            height=800,
            rotation=0,
            text=f"Page {page_number}",
            text_sha256=sha256_text(f"Page {page_number}"),
            blocks=(),
        )
        for page_number in range(1, page_count + 1)
    )
    metadata: dict[str, object] = {}
    if document_type is not None:
        metadata["document_type"] = document_type
    return ExtractionArtifact(
        source=SourceArtifact(
            relative_path=relative_path,
            filename="manual.pdf",
            sha256=SOURCE_SHA256,
            size_bytes=100,
            page_count=page_count,
            metadata=metadata,
        ),
        provenance=ExtractionProvenance(
            pipeline="test",
            pipeline_version="1",
            docling_version="1",
            docling_core_version="1",
            pymupdf_version="1",
            raw_docling_file="docling.json",
            raw_docling_sha256=RAW_SHA256,
            settings=ExtractorSettings(
                page_start=1,
                page_end=page_count,
                device="cpu",
                num_threads=1,
                ocr_enabled=False,
                table_structure_enabled=True,
                heading_hierarchy_enabled=True,
                model_compilation_enabled=False,
            ),
        ),
        pages=pages,
        elements=elements,
        tables=tables,
        statistics=ExtractionStatistics(
            extracted_pages=page_count,
            elements=len(elements),
            tables=len(tables),
            page_text_characters=sum(len(page.text) for page in pages),
        ),
    )


def table(number: int, *, page: int, section_path: tuple[str, ...]) -> TableArtifact:
    return TableArtifact(
        table_id=f"tbl_{number:032x}",
        docling_ref=f"#/tables/{number}",
        reading_order=number,
        section_path=section_path,
        row_count=1,
        column_count=1,
        cells=(
            TableCell(
                row_start=0,
                row_end=1,
                column_start=0,
                column_end=1,
                text="Pressure",
            ),
        ),
        provenance=provenance(page),
    )

