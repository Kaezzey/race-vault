from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast

import pytest
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
from racevault.generation.service import AnswerService, GenerationQueueFullError
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

    def answer(
        self,
        request: GroundedAnswerRequest,
        *,
        on_draft: Callable[[str], None] | None = None,
    ) -> GroundedAnswerResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if on_draft is not None:
            on_draft("A Joker")
            on_draft("A Joker Tyre")
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
    return TestClient(create_app(answer_service=cast(AnswerService, service)))


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
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert service.requests[0].filters.season == 2026


def test_grounded_answer_rejects_blank_query() -> None:
    response = _client(FakeAnswerService()).post("/v2/answers", json={"query": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_grounded_answer_maps_ollama_failure_to_stable_error() -> None:
    response = _client(FakeAnswerService(error=OllamaUnavailableError("offline"))).post(
        "/v2/answers", json={"query": "Joker Tyre"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "generation_unavailable"


def test_grounded_answer_rejects_when_generation_queue_is_full() -> None:
    response = _client(FakeAnswerService(error=GenerationQueueFullError("full"))).post(
        "/v2/answers", json={"query": "Joker Tyre"}
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "5"
    assert response.json()["error"]["code"] == "generation_queue_full"


def test_answer_stream_sends_drafts_then_validated_response() -> None:
    response = _client(FakeAnswerService()).post(
        "/v2/answers/stream", json={"query": "Joker Tyre"}
    )
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in events] == ["draft", "draft", "complete"]
    assert events[0]["text"] == "A Joker"
    result = events[-1]["response"]
    assert result["request_id"] == response.headers["X-Request-ID"]
    assert result["citations"][0]["evidence_id"] == "E1"


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (GenerationQueueFullError("full"), "generation_queue_full", 429),
        (OllamaUnavailableError("offline"), "generation_unavailable", 503),
    ],
)
def test_answer_stream_reports_terminal_errors(error, code, status) -> None:
    response = _client(FakeAnswerService(error=error)).post(
        "/v2/answers/stream", json={"query": "Joker Tyre"}
    )
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["status"] == status
    assert events[0]["error"]["code"] == code


def test_disconnect_stops_stream_and_releases_generation_slot() -> None:
    import threading
    from types import SimpleNamespace

    import anyio
    from starlette.requests import Request

    from racevault.api.answers import stream_grounded_answer
    from racevault.generation.service import QueuedAnswerService

    stopped = threading.Event()

    class StreamingService(FakeAnswerService):
        def answer(self, request, *, on_draft=None):
            try:
                while True:
                    on_draft("Partial answer")
            finally:
                stopped.set()

    service = QueuedAnswerService(StreamingService(), max_concurrency=1, queue_depth=0)

    async def run():
        disconnect = anyio.Event()
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v2/answers/stream",
            "headers": [],
            "asgi": {"spec_version": "2.0"},
            "app": SimpleNamespace(state=SimpleNamespace(pipeline_fingerprint="test")),
        }

        async def receive():
            await disconnect.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if b'"type": "draft"' in message.get("body", b""):
                disconnect.set()

        response = await stream_grounded_answer(
            GroundedAnswerRequest(query="tyres"), Request(scope), service
        )
        with anyio.fail_after(5):
            await response(scope, receive, send)

    anyio.run(run)
    assert stopped.is_set()
    assert service.state() == (0, 0)
