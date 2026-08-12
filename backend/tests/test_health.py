from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from racevault.main import app


def _client_with_probes(
    postgres: AsyncMock, opensearch: AsyncMock
) -> Iterator[TestClient]:
    with (
        patch("racevault.api.health.check_postgres", postgres),
        patch("racevault.api.health.check_opensearch", opensearch),
        TestClient(app) as client,
    ):
        yield client


def test_readiness_succeeds_when_dependencies_are_ready() -> None:
    clients = _client_with_probes(
        AsyncMock(return_value="ok"), AsyncMock(return_value="ok")
    )
    client = next(clients)
    try:
        response = client.get("/health/ready")
    finally:
        clients.close()

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_returns_503_when_dependency_is_unavailable() -> None:
    clients = _client_with_probes(
        AsyncMock(side_effect=RuntimeError("database offline")),
        AsyncMock(return_value="ok"),
    )
    client = next(clients)
    try:
        response = client.get("/health/ready")
    finally:
        clients.close()

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["dependencies"]["postgres"] == {
        "status": "unavailable",
        "detail": "database offline",
    }
    assert payload["dependencies"]["opensearch"] == {
        "status": "ok",
        "detail": None,
    }
