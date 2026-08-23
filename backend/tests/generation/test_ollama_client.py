"""Connection and status handling in the local generation client.

Opening a connection to Ollama costs far more than the request that follows it,
so these tests pin the two behaviours that keep that cost off the answer path.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from racevault.generation.models import GeneratedAnswer, GeneratedStatement
from racevault.generation.ollama import OllamaClient

ANSWER = GeneratedAnswer(
    answer=(
        GeneratedStatement(
            text="The minimum weight is 1300 kg.", citations=("E1",)
        ),
    ),
    conflicts=(),
    limitations=(),
    insufficient_evidence=False,
)


class RecordingTransport(httpx.BaseTransport):
    """Count requests by path and how many connections were opened."""

    def __init__(self) -> None:
        self.paths: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        if path == "/api/version":
            body: dict[str, Any] = {"version": "0.5.0"}
        elif path == "/api/tags":
            body = {
                "models": [
                    {
                        "name": "qwen3.5:9b",
                        "model": "qwen3.5:9b",
                        "digest": "sha256:abc",
                        "details": {
                            "parameter_size": "9.7B",
                            "quantization_level": "Q4_K_M",
                        },
                    }
                ]
            }
        elif path == "/api/show":
            body = {"capabilities": ["completion"]}
        elif path == "/api/chat":
            body = {
                "model": "qwen3.5:9b",
                "message": {
                    "role": "assistant",
                    "content": ANSWER.model_dump_json(),
                },
                "done": True,
                "total_duration": 1_000_000,
                "load_duration": 0,
                "prompt_eval_count": 100,
                "eval_count": 10,
            }
        else:  # pragma: no cover - the client asks for nothing else
            raise AssertionError(f"unexpected path {path}")
        return httpx.Response(200, content=json.dumps(body).encode())


@pytest.fixture
def client() -> OllamaClient:
    transport = RecordingTransport()
    client = OllamaClient(
        base_url="http://ollama.invalid:11434",
        model="qwen3.5:9b",
        timeout_seconds=30,
        context_tokens=16384,
        max_output_tokens=3072,
        keep_alive="5m",
    )
    client._client = httpx.Client(
        base_url="http://ollama.invalid:11434", transport=transport
    )
    client._transport = transport  # type: ignore[attr-defined]
    return client


def _generate(client: OllamaClient) -> None:
    client.generate(system_prompt="system", user_prompt="user")


def test_repeated_generation_resolves_the_model_once(client: OllamaClient) -> None:
    """status() costs three round trips and reports the same pinned digest."""

    _generate(client)
    _generate(client)
    _generate(client)

    paths = client._transport.paths  # type: ignore[attr-defined]
    assert paths.count("/api/chat") == 3
    assert paths.count("/api/tags") == 1
    assert paths.count("/api/version") == 1
    assert paths.count("/api/show") == 1


def test_generation_still_reports_the_resolved_model(client: OllamaClient) -> None:
    result = client.generate(system_prompt="system", user_prompt="user")

    assert result.model.model == "qwen3.5:9b"
    assert result.model.digest == "sha256:abc"
    assert result.model.quantization_level == "Q4_K_M"


def test_health_status_stays_live(client: OllamaClient) -> None:
    """A cached identity must not make the health endpoint stale."""

    _generate(client)
    client.status()

    paths = client._transport.paths  # type: ignore[attr-defined]
    assert paths.count("/api/version") == 2


def test_one_connection_serves_the_process() -> None:
    client = OllamaClient(
        base_url="http://ollama.invalid:11434",
        model="qwen3.5:9b",
        timeout_seconds=30,
        context_tokens=16384,
        max_output_tokens=3072,
        keep_alive="5m",
    )
    client._client = httpx.Client(
        base_url="http://ollama.invalid:11434", transport=RecordingTransport()
    )

    first = client._http()
    second = client._http()

    assert first is second
    client.close()
    assert client._client is None
