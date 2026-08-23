"""V2 grounded-answer generation routes."""

from __future__ import annotations

from typing import Annotated, cast

import psycopg
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from racevault.api.errors import ApiError
from racevault.config import get_settings
from racevault.generation.models import (
    GenerationStatus,
    GroundedAnswerRequest,
    GroundedAnswerResponse,
)
from racevault.generation.ollama import (
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaUnavailableError,
)
from racevault.generation.service import (
    AnswerService,
    GenerationQueueFullError,
    GroundingValidationError,
)
from racevault.lexical.client import OpenSearchError
from racevault.telemetry import current_request_id

router = APIRouter(prefix="/v2", tags=["generation"])


def get_answer_service(request: Request) -> AnswerService:
    return cast(AnswerService, request.app.state.answer_service)


def _generation_unavailable(error: Exception) -> ApiError:
    return ApiError(
        status_code=503,
        code="generation_unavailable",
        message="Local answer generation is unavailable.",
        details={"reason": str(error)},
    )


@router.get("/generation/status", response_model=GenerationStatus)
async def generation_status(
    service: Annotated[AnswerService, Depends(get_answer_service)],
) -> GenerationStatus:
    try:
        return await run_in_threadpool(service.status)
    except (OllamaUnavailableError, OllamaModelNotFoundError) as error:
        raise _generation_unavailable(error) from error
    except OllamaResponseError as error:
        raise ApiError(
            status_code=502,
            code="generation_service_invalid",
            message="Ollama returned an invalid response.",
            details={"reason": str(error)},
        ) from error


@router.post("/answers", response_model=GroundedAnswerResponse)
async def grounded_answer(
    body: GroundedAnswerRequest,
    http_request: Request,
    service: Annotated[AnswerService, Depends(get_answer_service)],
) -> GroundedAnswerResponse:
    try:
        response = await run_in_threadpool(service.answer, body)
        return response.model_copy(
            update={
                "request_id": current_request_id(),
                "pipeline_fingerprint": http_request.app.state.pipeline_fingerprint,
            }
        )
    except GenerationQueueFullError as error:
        retry_after = get_settings().generation_retry_after_seconds
        raise ApiError(
            status_code=429,
            code="generation_queue_full",
            message="Local answer generation is at capacity.",
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        ) from error
    except (OllamaUnavailableError, OllamaModelNotFoundError) as error:
        raise _generation_unavailable(error) from error
    except (OllamaResponseError, GroundingValidationError) as error:
        raise ApiError(
            status_code=502,
            code="grounded_answer_invalid",
            message="The generated answer failed validation.",
            details={"reason": str(error)},
        ) from error
    except (OpenSearchError, RuntimeError, ValueError, psycopg.Error) as error:
        raise ApiError(
            status_code=503,
            code="retrieval_unavailable",
            message="Retrieval is temporarily unavailable.",
            details={"reason": str(error)},
        ) from error
