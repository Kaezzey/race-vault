"""Liveness and readiness routes."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from racevault.config import Settings, get_settings
from racevault.dependencies import check_opensearch, check_postgres

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: str
    service: str


class DependencyStatus(BaseModel):
    status: str
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    dependencies: dict[str, DependencyStatus]


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok", service="racevault-api")


async def _run_probe(
    probe: Callable[[Settings], Awaitable[str]], settings: Settings
) -> DependencyStatus:
    try:
        result = await probe(settings)
        return DependencyStatus(status=result)
    except Exception as exc:  # readiness must report dependency failure details
        return DependencyStatus(status="unavailable", detail=str(exc))


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(response: Response) -> ReadinessResponse:
    settings = get_settings()
    postgres, opensearch = await asyncio.gather(
        _run_probe(check_postgres, settings),
        _run_probe(check_opensearch, settings),
    )
    dependencies = {"postgres": postgres, "opensearch": opensearch}
    ready = all(item.status == "ok" for item in dependencies.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if ready else "unavailable", dependencies=dependencies
    )
