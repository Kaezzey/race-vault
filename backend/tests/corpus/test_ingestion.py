from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from racevault.chunking.pipeline import ChunkingOptions, ChunkingResult
from racevault.corpus.ingestion import IngestionStage, ingest_manifest
from racevault.corpus.models import CorpusDocument, CorpusManifest
from racevault.extraction.pipeline import ExtractionOptions, ExtractionResult
from tests.lexical.factories import chunking_artifact


def _manifest() -> CorpusManifest:
    return CorpusManifest(
        documents=(
            CorpusDocument(
                role="one",
                path="one.pdf",
                document_type="component_manual",
                authority="component_supplier_document",
            ),
            CorpusDocument(
                role="two",
                path="two.pdf",
                document_type="component_manual",
                authority="component_supplier_document",
            ),
        )
    )


def test_ingestion_continues_after_document_failure(tmp_path: Path) -> None:
    artifact = chunking_artifact()
    extraction = ExtractionResult(
        artifact=None,  # type: ignore[arg-type]
        artifact_path=tmp_path / "extraction.json",
        raw_docling_path=tmp_path / "docling.json",
        reused=False,
    )
    chunking = ChunkingResult(
        artifact=artifact,
        artifact_path=tmp_path / "chunks.json",
        reused=False,
    )
    calls = 0

    def extract(**_: object) -> ExtractionResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("broken PDF")
        return extraction

    with (
        patch("racevault.corpus.ingestion.extract_document", side_effect=extract),
        patch("racevault.corpus.ingestion.chunk_extraction", return_value=chunking),
    ):
        report = ingest_manifest(
            _manifest(),
            corpus_root=tmp_path,
            extraction_root=tmp_path,
            chunk_root=tmp_path,
            through=IngestionStage.CHUNK,
            extraction_options=ExtractionOptions(),
            chunking_options=ChunkingOptions(),
        )

    assert report.completed_documents == 1
    assert report.failed_documents == 1
    assert report.documents[0].error == "RuntimeError: broken PDF"
    assert report.documents[1].status == "complete"
