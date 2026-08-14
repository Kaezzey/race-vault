from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from racevault.api.source_management import LocalSourceManager
from racevault.chunking.models import DocumentClass
from racevault.config import Settings


def _settings(tmp_path: Path, max_bytes: int = 1024) -> Settings:
    return Settings(
        upload_root_path=str(tmp_path / "uploads"),
        upload_max_bytes=max_bytes,
    )


def test_upload_is_stored_by_hash_before_background_ingestion(
    tmp_path: Path,
) -> None:
    manager = LocalSourceManager(_settings(tmp_path))

    with patch("racevault.api.source_management.threading.Thread") as thread:
        status = manager.start_upload(
            filename="../Workshop Manual.pdf",
            file=BytesIO(b"%PDF-test content"),
            document_type=DocumentClass.TECHNICAL_MANUAL,
            authority="manufacturer_document",
        )

    stored = (
        tmp_path
        / "uploads"
        / status.source_sha256
        / "Workshop Manual.pdf"
    )
    assert status.status == "queued"
    assert stored.read_bytes() == b"%PDF-test content"
    thread.return_value.start.assert_called_once_with()


@pytest.mark.parametrize(
    ("content", "max_bytes", "message"),
    [
        (b"not a pdf", 1024, "PDF header"),
        (b"%PDF-" + b"x" * 1024, 1024, "size limit"),
    ],
)
def test_upload_rejects_invalid_pdf_input(
    tmp_path: Path,
    content: bytes,
    max_bytes: int,
    message: str,
) -> None:
    manager = LocalSourceManager(_settings(tmp_path, max_bytes))

    with pytest.raises(ValueError, match=message):
        manager.start_upload(
            filename="document.pdf",
            file=BytesIO(content),
            document_type=None,
            authority="unknown",
        )
