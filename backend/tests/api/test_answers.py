from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from racevault.generation.models import (
    AnswerTimings,
    GenerationModelIdentity,
    GenerationStatus,
    GenerationUsage,
    GroundedAnswerRequest,
    GroundedAnswerResponse,
    GroundedCitation,
)
from racevault.generation.ollama import OllamaUnavailableError
from racevault.generation.service import AnswerService
from racevault.main import create_app
from tests.api.factories import retrieval_response


def _status() -> GenerationStatus:
    return GenerationStatus(
        available=True,
        ollama_version="0.32.9",
        model=GenerationModelIdentity(
            model="qwen3.5:9b",
            digest="a" * 64,
            parameter_size="9.7B",
            quantization_level="Q4_K_M",
        ),
        capabilities=("completion", "vision", "thinking"),
    )


class FakeAnswerService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[GroundedAnswerRequest] = []

    def status(self) -> GenerationStatus:
        if self.error is not None:
            raise self.error
        return _status()

    def answer(self, request: GroundedAnswerRequest) -> GroundedAnswerResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        retrieval = retrieval_response(request.query)
        return GroundedAnswerResponse(
            query=request.query,
            filters=request.filters,
            answer="A Joker Tyre is declared replacement evidence [E1].",
            insufficient_evidence=False,
            conflicts=(),
            limitations=(),
            citations=(
                GroundedCitation(
                    evidence_id="E1",
                    citation=retrieval.results[0].citation,
                ),
            ),
            evidence=retrieval.results,
            retrieval_counts=retrieval.counts,
            generation_model=_status().model,
            generation_usage=GenerationUsage(
                total_duration_ms=100,
                load_duration_ms=20,
                prompt_tokens=300,
                output_tokens=40,
            ),
            timings=AnswerTimings(retrieval_ms=50, generation_ms=100),
        )


def _client(service: FakeAnswerService) -> TestClient:
    return TestClient(
        create_app(answer_service=cast(AnswerService, service))
    )


def test_generation_status_reports_local_model() -> None:
    response = _client(FakeAnswerService()).get("/v2/generation/status")

    assert response.status_code == 200
    assert response.json()["model"]["model"] == "qwen3.5:9b"
    assert "vision" in response.json()["capabilities"]


def test_grounded_answer_returns_validated_citations_and_evidence() -> None:
    service = FakeAnswerService()
    response = _client(service).post(
        "/v2/answers",
        json={
            "query": "What is a Joker Tyre?",
            "filters": {"season": 2026, "document_class": "regulation"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"][0]["evidence_id"] == "E1"
    assert payload["evidence"][0]["citation"]["page_start"] == 6
    assert service.requests[0].filters.season == 2026


def test_grounded_answer_rejects_blank_query() -> None:
    response = _client(FakeAnswerService()).post(
        "/v2/answers", json={"query": "   "}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_grounded_answer_maps_ollama_failure_to_stable_error() -> None:
    response = _client(
        FakeAnswerService(error=OllamaUnavailableError("offline"))
    ).post("/v2/answers", json={"query": "Joker Tyre"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "generation_unavailable"
