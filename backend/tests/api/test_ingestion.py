from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from racevault.api.ingestion_service import IngestionCoordinator
from racevault.corpus.ingestion import IngestionReport, IngestionStage
from racevault.main import create_app


class FakeCoordinator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.started: tuple[set[str] | None, IngestionStage] | None = None

    def start(self, *, roles: set[str] | None, through: IngestionStage) -> str:
        if self.error is not None:
            raise self.error
        self.started = roles, through
        return "run-123"

    def snapshot(
        self,
    ) -> tuple[str | None, bool, str | None, IngestionReport | None]:
        return "run-123", False, None, None


def _client(coordinator: FakeCoordinator) -> TestClient:
    return TestClient(
        create_app(
            ingestion_coordinator=cast(IngestionCoordinator, coordinator)
        )
    )


def test_ingestion_run_requires_explicit_scope() -> None:
    response = _client(FakeCoordinator()).post(
        "/v1/ingestion/runs", json={"through": "semantic"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_ingestion_status_distinguishes_trigger_and_checkpoint_state() -> None:
    response = _client(FakeCoordinator()).get("/v1/ingestion/status")

    assert response.status_code == 200
    assert response.json()["trigger_enabled"] is False
    assert response.json()["available"] is False
    assert response.json()["active"] is False


def test_ingestion_run_returns_accepted_identifier() -> None:
    coordinator = FakeCoordinator()
    response = _client(coordinator).post(
        "/v1/ingestion/runs",
        json={"roles": ["tyre_data"], "through": "semantic"},
    )

    assert response.status_code == 202
    assert response.json() == {"run_id": "run-123", "status": "accepted"}
    assert coordinator.started == ({"tyre_data"}, IngestionStage.SEMANTIC)


def test_disabled_ingestion_returns_403() -> None:
    response = _client(FakeCoordinator(error=PermissionError("disabled"))).post(
        "/v1/ingestion/runs",
        json={"all_documents": True, "through": "extract"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ingestion_disabled"
