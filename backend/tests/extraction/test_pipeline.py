from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from racevault.extraction.docling_adapter import DoclingResult
from racevault.extraction.io import canonical_json_bytes, sha256_file
from racevault.extraction.models import BoundingBox, PageArtifact, PageBlock
from racevault.extraction.pipeline import ExtractionOptions, extract_document


def _page() -> PageArtifact:
    text = "Page text"
    return PageArtifact(
        page_number=1,
        width=100,
        height=200,
        rotation=0,
        text=text,
        text_sha256=(
            "2740b99974a64ebbac0d971377e0bf97a30442dfc852a743a0b1435d7a8270ba"
        ),
        blocks=(
            PageBlock(
                block_number=0,
                bbox=BoundingBox(
                    left=0,
                    top=0,
                    right=10,
                    bottom=10,
                    coordinate_origin="TOPLEFT",
                ),
                text=text,
            ),
        ),
    )


def test_pipeline_writes_and_reuses_canonical_artifact(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "manual.pdf"
    source.write_bytes(b"test PDF bytes")
    output = tmp_path / "output"
    docling_document = {
        "body": {"children": []},
        "furniture": {"children": []},
        "texts": [],
        "tables": [],
        "pictures": [],
        "groups": [],
        "key_value_items": [],
        "form_items": [],
    }

    with (
        patch(
            "racevault.extraction.pipeline.read_pdf_pages",
            return_value=(1, (_page(),), "1.28.2"),
        ),
        patch(
            "racevault.extraction.pipeline.convert_pdf",
            return_value=DoclingResult(docling_document, "2.119.0", "2.91.0"),
        ) as converter,
    ):
        first = extract_document(
            corpus_root=corpus,
            relative_path="manual.pdf",
            output_root=output,
            options=ExtractionOptions(),
        )
        first_bytes = first.artifact_path.read_bytes()
        second = extract_document(
            corpus_root=corpus,
            relative_path="manual.pdf",
            output_root=output,
            options=ExtractionOptions(),
        )

    assert first.reused is False
    assert second.reused is True
    assert converter.call_count == 1
    assert first_bytes == canonical_json_bytes(second.artifact)
    assert second.artifact.source.sha256 == sha256_file(source)


def test_reused_extraction_refreshes_manifest_metadata(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "manual.pdf").write_bytes(b"test PDF bytes")
    output = tmp_path / "output"
    docling_document = {
        "body": {"children": []},
        "furniture": {"children": []},
        "texts": [],
        "tables": [],
        "pictures": [],
        "groups": [],
        "key_value_items": [],
        "form_items": [],
    }

    with (
        patch(
            "racevault.extraction.pipeline.read_pdf_pages",
            return_value=(1, (_page(),), "1.28.2"),
        ),
        patch(
            "racevault.extraction.pipeline.convert_pdf",
            return_value=DoclingResult(docling_document, "2.119.0", "2.91.0"),
        ) as converter,
    ):
        extract_document(
            corpus_root=corpus,
            relative_path="manual.pdf",
            output_root=output,
            role="regulation",
            metadata={"championship": "Original championship"},
        )
        refreshed = extract_document(
            corpus_root=corpus,
            relative_path="manual.pdf",
            output_root=output,
            role="regulation",
            metadata={"championship": "Canonical championship"},
        )

    assert refreshed.reused is True
    assert refreshed.artifact.source.metadata == {
        "championship": "Canonical championship"
    }
    assert converter.call_count == 1
