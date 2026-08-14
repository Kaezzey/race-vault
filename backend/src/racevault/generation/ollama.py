"""Minimal client for the local Ollama HTTP API."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from racevault.generation.models import (
    GeneratedAnswer,
    GenerationModelIdentity,
    GenerationStatus,
    GenerationUsage,
)


class OllamaError(RuntimeError):
    """Base error for local generation failures."""


class OllamaUnavailableError(OllamaError):
    """Ollama cannot be reached."""


class OllamaModelNotFoundError(OllamaError):
    """The configured model is not installed."""


class OllamaResponseError(OllamaError):
    """Ollama or the model returned an invalid response."""


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

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
    ) -> Any:
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = client.request(method, path, json=json)
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
        return GenerationStatus(
            available=True,
            ollama_version=version.version,
            model=GenerationModelIdentity(
                model=self._model,
                digest=tag.digest,
                parameter_size=tag.details.parameter_size,
                quantization_level=tag.details.quantization_level,
            ),
            capabilities=show.capabilities,
        )

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> OllamaGeneration:
        status = self.status()
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
            answer = GeneratedAnswer.model_validate_json(response.message.content)
        except ValidationError as error:
            raise OllamaResponseError(
                "the generation model returned an invalid structured answer"
            ) from error
        if not response.done:
            raise OllamaResponseError("Ollama did not complete the response")
        return OllamaGeneration(
            answer=answer,
            model=status.model,
            usage=GenerationUsage(
                total_duration_ms=response.total_duration // 1_000_000,
                load_duration_ms=response.load_duration // 1_000_000,
                prompt_tokens=response.prompt_eval_count,
                output_tokens=response.eval_count,
            ),
        )
