"""Minimal client for the local Ollama HTTP API."""

from __future__ import annotations

import logging
from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from racevault.generation.models import (
    GeneratedAnswer,
    GenerationModelIdentity,
    GenerationStatus,
    GenerationUsage,
)
from racevault.telemetry import metrics

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Base error for local generation failures."""


class OllamaUnavailableError(OllamaError):
    """Ollama cannot be reached."""


class OllamaModelNotFoundError(OllamaError):
    """The configured model is not installed."""


class OllamaResponseError(OllamaError):
    """Ollama or the model returned an invalid response."""


def _validation_summary(error: ValidationError) -> str:
    """Return validation locations and error types without model output."""

    failures = (
        f"{'.'.join(str(part) for part in item['loc'])}: {item['type']}"
        for item in error.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
    )
    return "; ".join(failures)


class _OllamaModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _ModelDetails(_OllamaModel):
    parameter_size: str | None = None
    quantization_level: str | None = None


class _Tag(_OllamaModel):
    name: str
    model: str
    digest: str
    details: _ModelDetails = Field(default_factory=_ModelDetails)


class _TagsResponse(_OllamaModel):
    models: tuple[_Tag, ...]


class _VersionResponse(_OllamaModel):
    version: str


class _ShowResponse(_OllamaModel):
    capabilities: tuple[str, ...] = ()


class _ChatMessage(_OllamaModel):
    role: str
    content: str


class _ChatResponse(_OllamaModel):
    model: str
    message: _ChatMessage
    done: bool
    done_reason: str | None = None
    total_duration: int = Field(default=0, ge=0)
    load_duration: int = Field(default=0, ge=0)
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


class OllamaGeneration:
    def __init__(
        self,
        *,
        answer: GeneratedAnswer,
        model: GenerationModelIdentity,
        usage: GenerationUsage,
    ) -> None:
        self.answer = answer
        self.model = model
        self.usage = usage


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        context_tokens: int,
        max_output_tokens: int,
        keep_alive: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._context_tokens = context_tokens
        self._max_output_tokens = max_output_tokens
        self._keep_alive = keep_alive
        self._client: httpx.Client | None = None
        self._identity: GenerationModelIdentity | None = None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _http(self) -> httpx.Client:
        """Hold one connection open for the process.

        Opening a connection costs far more than the request that follows it,
        and on a host whose "localhost" resolves to ::1 before 127.0.0.1 the
        refused IPv6 attempt adds about two seconds before the IPv4 retry.
        """

        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
    ) -> Any:
        try:
            response = self._http().request(method, path, json=json)
            response.raise_for_status()
            return response.json()
        except (httpx.ConnectError, httpx.TimeoutException) as error:
            raise OllamaUnavailableError(
                "the local Ollama service is unavailable"
            ) from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise OllamaModelNotFoundError(
                    f"Ollama model is unavailable: {self._model}"
                ) from error
            raise OllamaResponseError(
                f"Ollama returned HTTP {error.response.status_code}"
            ) from error
        except (ValueError, TypeError) as error:
            raise OllamaResponseError("Ollama returned invalid JSON") from error

    def status(self) -> GenerationStatus:
        try:
            version = _VersionResponse.model_validate(
                self._request("GET", "/api/version")
            )
            tags = _TagsResponse.model_validate(self._request("GET", "/api/tags"))
        except ValidationError as error:
            raise OllamaResponseError(
                "Ollama returned an invalid status response"
            ) from error
        tag = next(
            (
                item
                for item in tags.models
                if item.name == self._model or item.model == self._model
            ),
            None,
        )
        if tag is None:
            raise OllamaModelNotFoundError(
                f"Ollama model is unavailable: {self._model}"
            )
        try:
            show = _ShowResponse.model_validate(
                self._request("POST", "/api/show", json={"model": self._model})
            )
        except ValidationError as error:
            raise OllamaResponseError(
                "Ollama returned invalid model details"
            ) from error
        identity = GenerationModelIdentity(
            model=self._model,
            digest=tag.digest,
            parameter_size=tag.details.parameter_size,
            quantization_level=tag.details.quantization_level,
        )
        self._identity = identity
        return GenerationStatus(
            available=True,
            ollama_version=version.version,
            model=identity,
            capabilities=show.capabilities,
        )

    def _model_identity(self) -> GenerationModelIdentity:
        """Return the model identity, resolving it at most once.

        `status()` costs three round trips and reports the same digest every
        time for a pinned model, so paying it before each generation doubled
        the latency of a short answer.
        """

        if self._identity is None:
            return self.status().model
        return self._identity

    def _check_context_headroom(self, prompt_tokens: int) -> None:
        """Report a prompt that filled the space reserved for it.

        Ollama does not error when a prompt exceeds `num_ctx`; it discards the
        oldest tokens, which are the system prompt carrying every grounding
        rule. A silently ungrounded answer looks exactly like a grounded one,
        so the condition is surfaced rather than left to be inferred later.
        """

        headroom = self._context_tokens - self._max_output_tokens
        metrics.observe(
            "racevault_generation_prompt_tokens",
            prompt_tokens,
            buckets=(1000, 2000, 4000, 8000, 12000, 16000, 24000, 32000),
        )
        if prompt_tokens < headroom:
            return
        metrics.increment("racevault_generation_context_overflow_total")
        logger.warning(
            "generation prompt used %d tokens with only %d available before the "
            "%d-token context window; the system prompt may have been truncated",
            prompt_tokens,
            headroom,
            self._context_tokens,
        )

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> OllamaGeneration:
        identity = self._model_identity()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "format": GeneratedAnswer.model_json_schema(),
            "keep_alive": self._keep_alive,
            "options": {
                "temperature": 0,
                "num_ctx": self._context_tokens,
                "num_predict": self._max_output_tokens,
                "seed": 0,
            },
        }
        try:
            response = _ChatResponse.model_validate(
                self._request("POST", "/api/chat", json=payload)
            )
        except ValidationError as error:
            raise OllamaResponseError(
                "Ollama returned an invalid chat response: "
                f"{_validation_summary(error)}"
            ) from error
        if not response.done:
            raise OllamaResponseError("Ollama did not complete the response")
        self._check_context_headroom(response.prompt_eval_count)
        try:
            answer = GeneratedAnswer.model_validate_json(response.message.content)
        except ValidationError as error:
            raise OllamaResponseError(
                "the generation model returned an invalid structured answer: "
                f"done_reason={response.done_reason or 'unknown'}, "
                f"output_tokens={response.eval_count}; {_validation_summary(error)}"
            ) from error
        return OllamaGeneration(
            answer=answer,
            model=identity,
            usage=GenerationUsage(
                total_duration_ms=response.total_duration // 1_000_000,
                load_duration_ms=response.load_duration // 1_000_000,
                prompt_tokens=response.prompt_eval_count,
                output_tokens=response.eval_count,
            ),
        )
