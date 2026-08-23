from __future__ import annotations

from fastapi.testclient import TestClient

from racevault.main import app


def test_root_identifies_service() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {"service": "racevault-api", "version": "0.1.0"}
    assert response.headers["X-Request-ID"]


def test_request_id_is_propagated_and_metrics_do_not_capture_content() -> None:
    client = TestClient(app)
    response = client.get("/", headers={"X-Request-ID": "review-run-17"})

    assert response.headers["X-Request-ID"] == "review-run-17"
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "racevault_http_requests_total" in metrics_response.text
    assert "review-run-17" not in metrics_response.text


def test_liveness_does_not_require_external_services() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "racevault-api"}
