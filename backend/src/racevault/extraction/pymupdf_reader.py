"""Page-level extraction using PyMuPDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from racevault.extraction.io import sha256_text
from racevault.extraction.models import BoundingBox, PageArtifact, PageBlock


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def _block_text(block: dict[str, Any]) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        text = "".join(str(span.get("text", "")) for span in spans)
        if text:
            lines.append(text)
    return _normalize_text("\n".join(lines))


def read_pdf_pages(
    source_path: Path, page_start: int, page_end: int | None
) -> tuple[int, tuple[PageArtifact, ...], str]:
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError(
            "PyMuPDF is required. Install the 'extraction' dependency group."
        ) from exc

    with pymupdf.open(source_path) as document:  # type: ignore[no-untyped-call]
        if document.needs_pass:
            raise RuntimeError("password-protected PDFs are not supported")
        total_pages = document.page_count
        final_page = total_pages if page_end is None else page_end
        if page_start < 1 or final_page < page_start or final_page > total_pages:
            raise ValueError(
                f"page range {page_start}-{final_page} is invalid for "
                f"a {total_pages}-page PDF"
            )

        pages: list[PageArtifact] = []
        for page_number in range(page_start, final_page + 1):
            page = document.load_page(page_number - 1)
            page_dict = page.get_text("dict", sort=True)
            blocks: list[PageBlock] = []
            for block_number, block in enumerate(page_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                text = _block_text(block)
                if not text:
                    continue
                left, top, right, bottom = block["bbox"]
                blocks.append(
                    PageBlock(
                        block_number=block_number,
                        bbox=BoundingBox(
                            left=round(float(left), 6),
                            top=round(float(top), 6),
                            right=round(float(right), 6),
                            bottom=round(float(bottom), 6),
                            coordinate_origin="TOPLEFT",
                        ),
                        text=text,
                    )
                )

            page_text = _normalize_text(page.get_text("text", sort=True))
            pages.append(
                PageArtifact(
                    page_number=page_number,
                    width=round(float(page.rect.width), 6),
                    height=round(float(page.rect.height), 6),
                    rotation=page.rotation,
                    text=page_text,
                    text_sha256=sha256_text(page_text),
                    blocks=tuple(blocks),
                )
            )

    return total_pages, tuple(pages), pymupdf.__version__
