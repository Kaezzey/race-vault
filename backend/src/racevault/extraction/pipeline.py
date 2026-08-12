"""RaceVault PDF extraction pipeline."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from racevault import __version__
from racevault.extraction.docling_adapter import (
    DoclingOptions,
    convert_pdf,
)
from racevault.extraction.io import (
    canonical_json_bytes,
    load_json,
    resolve_corpus_source,
    sha256_file,
    write_json_atomic,
)
from racevault.extraction.models import (
    ExtractionArtifact,
    ExtractionProvenance,
    ExtractionStatistics,
    ExtractorSettings,
    SourceArtifact,
)
from racevault.extraction.normalizer import normalize_docling
from racevault.extraction.pymupdf_reader import read_pdf_pages


@dataclass(frozen=True)
class ExtractionOptions:
    page_start: int = 1
    page_end: int | None = None
    device: str = "cpu" if os.name == "nt" else "auto"
    num_threads: int = 8
    ocr_enabled: bool = False
    table_structure_enabled: bool = True
    heading_hierarchy_enabled: bool = True
    model_compilation_enabled: bool = False
    force: bool = False


@dataclass(frozen=True)
class ExtractionResult:
    artifact: ExtractionArtifact
    artifact_path: Path
    raw_docling_path: Path
    reused: bool


def extract_document(
    *,
    corpus_root: Path,
    relative_path: str,
    output_root: Path,
    options: ExtractionOptions | None = None,
    role: str | None = None,
    metadata: dict[str, object] | None = None,
) -> ExtractionResult:
    settings = options or ExtractionOptions()
    source_path = resolve_corpus_source(corpus_root, relative_path)
    source_sha256 = sha256_file(source_path)

    total_pages, pages, pymupdf_version = read_pdf_pages(
        source_path, settings.page_start, settings.page_end
    )
    final_page = pages[-1].page_number
    extractor_settings = ExtractorSettings(
        page_start=settings.page_start,
        page_end=final_page,
        device=settings.device,
        num_threads=settings.num_threads,
        ocr_enabled=settings.ocr_enabled,
        table_structure_enabled=settings.table_structure_enabled,
        heading_hierarchy_enabled=settings.heading_hierarchy_enabled,
        model_compilation_enabled=settings.model_compilation_enabled,
    )
    configuration_id = hashlib.sha256(
        canonical_json_bytes(extractor_settings)
    ).hexdigest()[:12]
    output_directory = (
        output_root.resolve()
        / source_sha256
        / f"pages-{settings.page_start:04d}-{final_page:04d}-{configuration_id}"
    )
    artifact_path = output_directory / "extraction.json"
    raw_docling_path = output_directory / "docling.json"

    if artifact_path.exists() and raw_docling_path.exists() and not settings.force:
        artifact = validate_extraction_artifact(artifact_path)
        if artifact.source.sha256 != source_sha256:
            raise ValueError("existing artifact source hash does not match the PDF")
        return ExtractionResult(
            artifact=artifact,
            artifact_path=artifact_path,
            raw_docling_path=raw_docling_path,
            reused=True,
        )

    docling_options = DoclingOptions(
        device=settings.device,
        num_threads=settings.num_threads,
        ocr_enabled=settings.ocr_enabled,
        table_structure_enabled=settings.table_structure_enabled,
        heading_hierarchy_enabled=settings.heading_hierarchy_enabled,
        model_compilation_enabled=settings.model_compilation_enabled,
    )
    docling_result = convert_pdf(
        source_path, settings.page_start, final_page, docling_options
    )
    raw_docling_sha256 = hashlib.sha256(
        canonical_json_bytes(docling_result.document)
    ).hexdigest()
    elements, tables = normalize_docling(docling_result.document, source_sha256)

    artifact = ExtractionArtifact(
        source=SourceArtifact(
            relative_path=Path(relative_path.replace("\\", "/")).as_posix(),
            filename=source_path.name,
            sha256=source_sha256,
            size_bytes=source_path.stat().st_size,
            page_count=total_pages,
            role=role,
            metadata=metadata or {},
        ),
        provenance=ExtractionProvenance(
            pipeline="racevault.pdf_extraction",
            pipeline_version=__version__,
            docling_version=docling_result.docling_version,
            docling_core_version=docling_result.docling_core_version,
            pymupdf_version=pymupdf_version,
            raw_docling_file=raw_docling_path.name,
            raw_docling_sha256=raw_docling_sha256,
            settings=extractor_settings,
        ),
        pages=pages,
        elements=elements,
        tables=tables,
        statistics=ExtractionStatistics(
            extracted_pages=len(pages),
            elements=len(elements),
            tables=len(tables),
            page_text_characters=sum(len(page.text) for page in pages),
        ),
    )

    write_json_atomic(raw_docling_path, docling_result.document)
    write_json_atomic(artifact_path, artifact)
    return ExtractionResult(
        artifact=artifact,
        artifact_path=artifact_path,
        raw_docling_path=raw_docling_path,
        reused=False,
    )


def validate_extraction_artifact(
    artifact_path: Path,
    corpus_root: Path | None = None,
    verify_source_hash: bool = False,
) -> ExtractionArtifact:
    artifact = ExtractionArtifact.model_validate(load_json(artifact_path))
    raw_docling_path = artifact_path.parent / artifact.provenance.raw_docling_file
    if not raw_docling_path.is_file():
        raise FileNotFoundError(raw_docling_path)
    load_json(raw_docling_path)
    if sha256_file(raw_docling_path) != artifact.provenance.raw_docling_sha256:
        raise ValueError("raw Docling file hash does not match the artifact")

    if verify_source_hash:
        if corpus_root is None:
            raise ValueError("corpus_root is required when verifying the source hash")
        source_path = resolve_corpus_source(
            corpus_root, artifact.source.relative_path
        )
        if sha256_file(source_path) != artifact.source.sha256:
            raise ValueError("source hash does not match the extraction artifact")
    return artifact
