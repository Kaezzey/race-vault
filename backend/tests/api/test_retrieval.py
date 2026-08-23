from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from fastapi.testclient import TestClient

from racevault.api.models import RetrievalSearchRequest, RetrievalSearchResponse
from racevault.api.services import RetrievalService
from racevault.catalog.store import CatalogStore
from racevault.main import create_app
from tests.api.factories import retrieval_response, source_summary


class FakeRetrieval:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[RetrievalSearchRequest] = []

    def search(self, request: RetrievalSearchRequest) -> RetrievalSearchResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return retrieval_response(request.query).model_copy(
            update={"filters": request.filters}
        )


def _client(service: FakeRetrieval, catalog: Mock | None = None) -> TestClient:
    configured_catalog = catalog or Mock(spec=CatalogStore)
    return TestClient(
        create_app(
            retrieval_service=cast(RetrievalService, service),
            catalog_store=cast(CatalogStore, configured_catalog),
        )
    )


def test_search_returns_citation_and_stage_diagnostics() -> None:
    service = FakeRetrieval()
    response = _client(service).post(
        "/v1/retrieval/search",
        json={
            "query": "What is a Joker Tyre?",
            "filters": {"document_class": "regulation", "season": 2026},
            "options": {"result_limit": 5},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["citation"]["page_start"] == 6
    assert payload["results"][0]["diagnostics"]["reranker_score"] == 0.9
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert len(payload["pipeline_fingerprint"]) == 64
    assert service.requests[0].options.result_limit == 5


def test_search_validation_uses_stable_error_shape() -> None:
    response = _client(FakeRetrieval()).post(
        "/v1/retrieval/search", json={"query": "   "}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_search_maps_runtime_failure_to_service_unavailable() -> None:
    response = _client(FakeRetrieval(error=RuntimeError("model unavailable"))).post(
        "/v1/retrieval/search", json={"query": "Joker Tyre"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "retrieval_unavailable"


def test_comparison_scopes_each_search_to_one_source() -> None:
    service = FakeRetrieval()
    catalog = Mock(spec=CatalogStore)
    catalog.get_source.side_effect = [
        source_summary("a" * 64),
        source_summary("b" * 64),
    ]
    response = _client(service, catalog).post(
        "/v1/sources/compare",
        json={
            "query": "brake pressure",
            "left_source_sha256": "a" * 64,
            "right_source_sha256": "b" * 64,
            "result_limit": 3,
        },
    )

    assert response.status_code == 200
    assert [item.filters.source_sha256 for item in service.requests] == [
        "a" * 64,
        "b" * 64,
    ]
