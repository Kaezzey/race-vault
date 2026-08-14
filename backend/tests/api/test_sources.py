from __future__ import annotations

from io import BytesIO
from typing import BinaryIO, cast
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from racevault.api.source_management import (
    SourceDeletionResult,
    SourceManager,
    SourceUploadStatus,
)
from racevault.catalog.models import CorpusStatus, SourceListResponse
from racevault.catalog.store import CatalogStore
from racevault.chunking.models import DocumentClass
from racevault.main import create_app
from tests.api.factories import source_summary


class FakeSourceManager:
    def __init__(self) -> None:
        self.started: tuple[str, bytes, DocumentClass | None, str] | None = None

    def start_upload(
        self,
        *,
        filename: str,
        file: BinaryIO,
        document_type: DocumentClass | None,
        authority: str,
    ) -> SourceUploadStatus:
        content = file.read()
        self.started = filename, content, document_type, authority
        return SourceUploadStatus(
            run_id="1" * 32,
            filename=filename,
            source_sha256="b" * 64,
            status="queued",
        )

    def upload_status(self, run_id: str) -> SourceUploadStatus | None:
        if run_id != "1" * 32:
            return None
        return SourceUploadStatus(
            run_id=run_id,
            filename="manual.pdf",
            source_sha256="b" * 64,
            status="complete",
            chunks=12,
            generated_embeddings=12,
        )

    def delete_source(self, source_sha256: str) -> SourceDeletionResult:
        return SourceDeletionResult(
            source_sha256=source_sha256,
            removed_documents=1,
            removed_chunks=12,
            removed_opensearch_chunks=12,
        )


def _client(catalog: Mock, manager: FakeSourceManager | None = None) -> TestClient:
    return TestClient(
        create_app(
            catalog_store=cast(CatalogStore, catalog),
            source_manager=cast(SourceManager, manager or FakeSourceManager()),
        )
    )


def test_source_listing_passes_metadata_filters() -> None:
    catalog = Mock(spec=CatalogStore)
    catalog.list_sources.return_value = SourceListResponse(
        total=1,
        limit=20,
        offset=0,
        sources=(source_summary(),),
    )
    response = _client(catalog).get(
        "/v1/sources?document_class=regulation&season=2026&limit=20"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    filters = catalog.list_sources.call_args.kwargs["filters"]
    assert filters.document_class == "regulation"
    assert filters.season == 2026


def test_missing_source_returns_404() -> None:
    catalog = Mock(spec=CatalogStore)
    catalog.get_source.return_value = None

    response = _client(catalog).get(f"/v1/sources/{'a' * 64}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"


def test_corpus_status_exposes_cross_store_consistency() -> None:
    catalog = Mock(spec=CatalogStore)
    catalog.corpus_status.return_value = CorpusStatus(
        documents=64,
        chunks=9212,
        embeddings=9212,
        embedded_documents=64,
        opensearch_chunks=9212,
        consistent=True,
        embedding_model_id="BAAI/bge-m3",
        embedding_model_revision="a" * 40,
    )
    with patch("racevault.api.corpus._opensearch_count", return_value=9212):
        response = _client(catalog).get("/v1/corpus/status")

    assert response.status_code == 200
    assert response.json()["consistent"] is True


def test_pdf_upload_starts_source_ingestion() -> None:
    catalog = Mock(spec=CatalogStore)
    manager = FakeSourceManager()

    response = _client(catalog, manager).post(
        "/v1/sources/uploads",
        files={"file": ("manual.pdf", BytesIO(b"%PDF-test"), "application/pdf")},
        data={
            "document_type": "technical_manual",
            "authority": "manufacturer_document",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert manager.started == (
        "manual.pdf",
        b"%PDF-test",
        DocumentClass.TECHNICAL_MANUAL,
        "manufacturer_document",
    )


def test_source_upload_status_and_delete() -> None:
    catalog = Mock(spec=CatalogStore)
    client = _client(catalog, FakeSourceManager())

    upload = client.get(f"/v1/sources/uploads/{'1' * 32}")
    deleted = client.delete(f"/v1/sources/{'b' * 64}")

    assert upload.status_code == 200
    assert upload.json()["chunks"] == 12
    assert deleted.status_code == 200
    assert deleted.json()["removed_chunks"] == 12
