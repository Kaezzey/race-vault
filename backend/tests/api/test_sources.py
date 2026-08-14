from __future__ import annotations

from typing import cast
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from racevault.catalog.models import CorpusStatus, SourceListResponse
from racevault.catalog.store import CatalogStore
from racevault.main import create_app
from tests.api.factories import source_summary


def _client(catalog: Mock) -> TestClient:
    return TestClient(create_app(catalog_store=cast(CatalogStore, catalog)))


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
