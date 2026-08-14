"""Read the latest resumable ingestion checkpoint."""

from __future__ import annotations

from typing import Annotated, Self, cast

from fastapi import APIRouter, Depends, Request, status
from pydantic import Field, model_validator

from racevault.api.errors import ApiError
from racevault.api.ingestion_service import IngestionCoordinator
from racevault.config import Settings, get_settings
from racevault.corpus.ingestion import IngestionReport, IngestionStage
from racevault.extraction.models import ArtifactModel

router = APIRouter(prefix="/v1/ingestion", tags=["ingestion"])


class IngestionStatusResponse(ArtifactModel):
    trigger_enabled: bool
    available: bool
    run_id: str | None = None
    active: bool
    report: IngestionReport | None = None
    detail: str | None = Field(default=None)


class IngestionStartRequest(ArtifactModel):
    roles: tuple[str, ...] = ()
    all_documents: bool = False
    through: IngestionStage = IngestionStage.SEMANTIC

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if self.all_documents == bool(self.roles):
            raise ValueError("set roles or all_documents, but not both")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("roles must be unique")
        return self


class IngestionRunAccepted(ArtifactModel):
    run_id: str
    status: str = "accepted"


def get_ingestion_coordinator(request: Request) -> IngestionCoordinator:
    return cast(IngestionCoordinator, request.app.state.ingestion_coordinator)


@router.get("/status", response_model=IngestionStatusResponse)
async def ingestion_status(
    coordinator: Annotated[
        IngestionCoordinator, Depends(get_ingestion_coordinator)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestionStatusResponse:
    run_id, active, detail, report = coordinator.snapshot()
    return IngestionStatusResponse(
        trigger_enabled=settings.api_ingestion_enabled,
        available=report is not None,
        run_id=run_id,
        active=active,
        report=report,
        detail=detail
        or (None if report is not None else "No checkpoint is available."),
    )


@router.post(
    "/runs",
    response_model=IngestionRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_ingestion(
    request: IngestionStartRequest,
    coordinator: Annotated[
        IngestionCoordinator, Depends(get_ingestion_coordinator)
    ],
) -> IngestionRunAccepted:
    try:
        run_id = coordinator.start(
            roles=None if request.all_documents else set(request.roles),
            through=request.through,
        )
    except PermissionError as error:
        raise ApiError(
            status_code=403,
            code="ingestion_disabled",
            message="API-triggered ingestion is disabled.",
        ) from error
    except RuntimeError as error:
        raise ApiError(
            status_code=409,
            code="ingestion_conflict",
            message=str(error),
        ) from error
    except (FileNotFoundError, ValueError) as error:
        raise ApiError(
            status_code=422,
            code="ingestion_request_invalid",
            message=str(error),
        ) from error
    return IngestionRunAccepted(run_id=run_id)
