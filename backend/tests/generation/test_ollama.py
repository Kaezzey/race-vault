from __future__ import annotations

import json
from typing import Any

import pytest

from racevault.generation.models import GeneratedAnswer, GeneratedStatement
from racevault.generation.ollama import (
    OllamaClient,
    OllamaModelNotFoundError,
    OllamaResponseError,
)


class StubOllamaClient(OllamaClient):
    def __init__(self, *, installed: bool = True) -> None:
        super().__init__(
            base_url="http://ollama.test",
            model="qwen3.5:9b",
            timeout_seconds=30,
            context_tokens=8192,
            max_output_tokens=512,
            keep_alive="0",
        )
        self.installed = installed
        self.chat_payload: dict[str, Any] | None = None
        self.paths: list[str] = []

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
    ) -> Any:
        self.paths.append(path)
        if path == "/api/version":
            return {"version": "0.32.9"}
        if path == "/api/tags":
            return {
                "models": (
                    [
                        {
                            "name": "qwen3.5:9b",
                            "model": "qwen3.5:9b",
                            "digest": "a" * 64,
                            "details": {
                                "parameter_size": "9.7B",
                                "quantization_level": "Q4_K_M",
                            },
                        }
                    ]
                    if self.installed
                    else []
                )
            }
        if path == "/api/show":
            return {"capabilities": ["completion", "vision", "thinking"]}
        if path == "/api/chat":
            assert isinstance(json, dict)
            self.chat_payload = json
            content = GeneratedAnswer(
                answer=(
                    GeneratedStatement(
                        text="Adjust the wheel.",
                        citations=("E1",),
                    ),
                ),
                conflicts=(),
                limitations=(),
                insufficient_evidence=False,
            ).model_dump_json()
            return {
                "model": "qwen3.5:9b",
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "total_duration": 2_000_000,
                "load_duration": 1_000_000,
                "prompt_eval_count": 100,
                "eval_count": 20,
            }
        raise AssertionError(f"unexpected request: {method} {path}")


class TruncatedOllamaClient(StubOllamaClient):
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
    ) -> Any:
        if path != "/api/chat":
            return super()._request(method, path, json=json)
        return {
            "model": "qwen3.5:9b",
            "message": {"role": "assistant", "content": '{"answer": ['},
            "done": True,
            "done_reason": "length",
            "prompt_eval_count": 100,
            "eval_count": 512,
        }


def test_status_reports_installed_model_identity() -> None:
    status = StubOllamaClient().status()

    assert status.available is True
    assert status.ollama_version == "0.32.9"
    assert status.model.parameter_size == "9.7B"
    assert status.model.quantization_level == "Q4_K_M"
    assert status.capabilities == ("completion", "vision", "thinking")


def test_status_rejects_missing_model() -> None:
    with pytest.raises(OllamaModelNotFoundError):
        StubOllamaClient(installed=False).status()


def test_generate_uses_structured_non_thinking_contract() -> None:
    client = StubOllamaClient()

    output = client.generate(system_prompt="system", user_prompt="evidence")

    assert output.answer.answer[0].citations == ("E1",)
    assert output.usage.prompt_tokens == 100
    assert client.chat_payload is not None
    assert client.chat_payload["stream"] is False
    assert client.chat_payload["think"] is False
    assert client.chat_payload["keep_alive"] == "0"
    assert client.chat_payload["options"] == {
        "temperature": 0,
        "num_ctx": 8192,
        "num_predict": 512,
        "seed": 0,
    }
    assert json.dumps(client.chat_payload["format"])


def test_generate_reports_truncated_structured_output_without_content() -> None:
    with pytest.raises(
        OllamaResponseError,
        match=r"done_reason=length, output_tokens=512; : json_invalid",
    ):
        TruncatedOllamaClient().generate(
            system_prompt="system",
            user_prompt="evidence",
        )


def test_repeated_generation_resolves_the_model_once() -> None:
    """status() costs three round trips and reports the same pinned digest."""

    client = StubOllamaClient()
    for _ in range(3):
        client.generate(system_prompt="system", user_prompt="user")

    assert client.paths.count("/api/chat") == 3
    assert client.paths.count("/api/tags") == 1
    assert client.paths.count("/api/version") == 1
    assert client.paths.count("/api/show") == 1


def test_generation_reports_the_resolved_model() -> None:
    result = StubOllamaClient().generate(system_prompt="s", user_prompt="u")

    assert result.model.model == "qwen3.5:9b"
    assert result.model.quantization_level == "Q4_K_M"


def test_health_status_stays_live() -> None:
    """A cached identity must not make the health endpoint stale."""

    client = StubOllamaClient()
    client.generate(system_prompt="s", user_prompt="u")
    client.status()

    assert client.paths.count("/api/version") == 2


def test_one_connection_serves_the_process() -> None:
    """Opening a connection costs more than the request that follows it."""

    client = OllamaClient(
        base_url="http://ollama.test",
        model="qwen3.5:9b",
        timeout_seconds=30,
        context_tokens=8192,
        max_output_tokens=512,
        keep_alive="5m",
    )

    assert client._http() is client._http()

    client.close()
    assert client._client is None
