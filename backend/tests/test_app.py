from __future__ import annotations

from fastapi.testclient import TestClient

from racevault.main import app


def test_root_identifies_service() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {"service": "racevault-api", "version": "0.1.0"}


def test_liveness_does_not_require_external_services() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "racevault-api"}

