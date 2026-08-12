from __future__ import annotations

from pathlib import Path

import pytest

from racevault.chunking.pipeline import (
    ChunkingOptions,
    chunk_extraction,
    validate_chunking_artifact,
)
from racevault.extraction.io import write_json_atomic
from tests.chunking.factories import element, extraction_artifact


def test_pipeline_writes_valid_artifact_and_reuses_it(tmp_path: Path) -> None:
    extraction_path = tmp_path / "extraction.json"
    extraction = extraction_artifact(
        (element(1, "Set the pressure."),), document_type="technical_manual"
    )
    write_json_atomic(extraction_path, extraction)

    first = chunk_extraction(
        extraction_path=extraction_path,
        output_root=tmp_path / "chunks",
        options=ChunkingOptions(),
    )
    second = chunk_extraction(
        extraction_path=extraction_path,
        output_root=tmp_path / "chunks",
        options=ChunkingOptions(),
    )

    assert first.reused is False
    assert second.reused is True
    assert first.artifact_path.read_bytes() == second.artifact_path.read_bytes()
    validate_chunking_artifact(first.artifact_path, extraction_path)


def test_validation_rejects_wrong_extraction(tmp_path: Path) -> None:
    extraction_path = tmp_path / "extraction.json"
    extraction = extraction_artifact((element(1, "Original"),))
    write_json_atomic(extraction_path, extraction)
    result = chunk_extraction(
        extraction_path=extraction_path, output_root=tmp_path / "chunks"
    )
    write_json_atomic(
        extraction_path,
        extraction_artifact((element(2, "Replacement"),)),
    )

    with pytest.raises(ValueError, match="extraction hash"):
        validate_chunking_artifact(result.artifact_path, extraction_path)

