"""Source document and chunk inspection routes."""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Path, Query
from fastapi.concurrency import run_in_threadpool

from racevault.api.errors import ApiError
from racevault.api.models import SHA256_PATTERN
from racevault.api.services import get_catalog_store, get_embedding_spec
from racevault.catalog.models import (
    SourceChunkListResponse,
    SourceListResponse,
    SourceSummary,
)
from racevault.catalog.store import CatalogStore
from racevault.retrieval.models import SearchFilters

router = APIRouter(prefix="/v1/sources", tags=["sources"])


def _database_unavailable(error: Exception) -> ApiError:
    return ApiError(
        status_code=503,
        code="catalog_unavailable",
        message="The source catalogue is temporarily unavailable.",
        details={"reason": str(error)},
    )


@router.get("", response_model=SourceListResponse)
async def list_sources(
    store: Annotated[CatalogStore, Depends(get_catalog_store)],
    document_class: str | None = None,
    authority: str | None = None,
    vehicle_generation: str | None = None,
    championship: str | None = None,
    season: int | None = Query(default=None, ge=1900, le=2200),
    revision: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SourceListResponse:
    filters = SearchFilters(
        document_class=document_class,
        authority=authority,
        vehicle_generation=vehicle_generation,
        championship=championship,
        season=season,
        revision=revision,
    )
    try:
        return await run_in_threadpool(
            store.list_sources,
            filters=filters,
            spec=get_embedding_spec(),
            limit=limit,
            offset=offset,
        )
    except (RuntimeError, ValueError, psycopg.Error) as error:
        raise _database_unavailable(error) from error


@router.get("/{source_sha256}", response_model=SourceSummary)
async def get_source(
    source_sha256: Annotated[str, Path(pattern=SHA256_PATTERN)],
    store: Annotated[CatalogStore, Depends(get_catalog_store)],
) -> SourceSummary:
    try:
        source = await run_in_threadpool(
            store.get_source, source_sha256, get_embedding_spec()
        )
    except (RuntimeError, ValueError, psycopg.Error) as error:
        raise _database_unavailable(error) from error
    if source is None:
        raise ApiError(
            status_code=404,
            code="source_not_found",
            message="The requested source does not exist.",
            details={"source_sha256": source_sha256},
        )
    return source


@router.get("/{source_sha256}/chunks", response_model=SourceChunkListResponse)
async def list_source_chunks(
    source_sha256: Annotated[str, Path(pattern=SHA256_PATTERN)],
    store: Annotated[CatalogStore, Depends(get_catalog_store)],
    page: int | None = Query(default=None, ge=1, le=32767),
    kind: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SourceChunkListResponse:
    try:
        source = await run_in_threadpool(
            store.get_source, source_sha256, get_embedding_spec()
        )
        if source is None:
            raise ApiError(
                status_code=404,
                code="source_not_found",
                message="The requested source does not exist.",
                details={"source_sha256": source_sha256},
            )
        return await run_in_threadpool(
            store.list_chunks,
            source_sha256=source_sha256,
            page_number=page,
            kind=kind,
            limit=limit,
            offset=offset,
        )
    except ApiError:
        raise
    except (RuntimeError, ValueError, psycopg.Error) as error:
        raise _database_unavailable(error) from error
