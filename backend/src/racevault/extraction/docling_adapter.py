"""Docling conversion and version reporting."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DoclingOptions:
    device: str
    num_threads: int
    ocr_enabled: bool
    table_structure_enabled: bool
    heading_hierarchy_enabled: bool = True
    model_compilation_enabled: bool = False


@dataclass(frozen=True)
class DoclingResult:
    document: dict[str, Any]
    docling_version: str
    docling_core_version: str


@lru_cache(maxsize=4)
def _document_converter(options: DoclingOptions) -> Any:
    """Create one converter per settings contract for the current process."""
    try:
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError(
            "Docling is required. Install the 'extraction' dependency group."
        ) from exc

    pipeline_options = PdfPipelineOptions(
        do_ocr=options.ocr_enabled,
        do_table_structure=options.table_structure_enabled,
        accelerator_options=AcceleratorOptions(
            device=options.device, num_threads=options.num_threads
        ),
    )
    pipeline_options.heading_hierarchy_options.enabled = (
        options.heading_hierarchy_enabled
    )
    layout_engine_options = getattr(
        pipeline_options.layout_options, "engine_options", None
    )
    if layout_engine_options is None:
        raise RuntimeError("Docling layout engine does not expose compile settings")
    layout_engine_options.compile_model = options.model_compilation_enabled

    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        },
    )


def convert_pdf(
    source_path: Path,
    page_start: int,
    page_end: int,
    options: DoclingOptions,
) -> DoclingResult:
    converter = _document_converter(options)
    conversion = converter.convert(
        source_path,
        page_range=(page_start, page_end),
        raises_on_error=True,
    )
    return DoclingResult(
        document=conversion.document.export_to_dict(),
        docling_version=version("docling"),
        docling_core_version=version("docling-core"),
    )
