"""Hybrid retrieval and document comparison routes."""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from racevault.api.errors import ApiError
from racevault.api.models import (
    RetrievalOptions,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    SourceComparisonRequest,
    SourceComparisonResponse,
)
from racevault.api.services import (
    RetrievalService,
    get_catalog_store,
    get_embedding_spec,
    get_retrieval_service,
)
from racevault.catalog.store import CatalogStore
from racevault.lexical.client import OpenSearchError
from racevault.retrieval.models import SearchFilters

router = APIRouter(prefix="/v1", tags=["retrieval"])


def _unavailable(error: Exception) -> ApiError:
    return ApiError(
        status_code=503,
        code="retrieval_unavailable",
        message="Retrieval is temporarily unavailable.",
        details={"reason": str(error)},
    )


@router.post("/retrieval/search", response_model=RetrievalSearchResponse)
async def search(
    request: RetrievalSearchRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> RetrievalSearchResponse:
    try:
        return await run_in_threadpool(service.search, request)
    except (OpenSearchError, RuntimeError, ValueError, psycopg.Error) as error:
        raise _unavailable(error) from error


@router.post("/sources/compare", response_model=SourceComparisonResponse)
async def compare_sources(
    request: SourceComparisonRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    catalog: Annotated[CatalogStore, Depends(get_catalog_store)],
) -> SourceComparisonResponse:
    options = RetrievalOptions(
        rerank_limit=max(15, request.result_limit),
        result_limit=request.result_limit,
    )
    left_request = RetrievalSearchRequest(
        query=request.query,
        filters=SearchFilters(source_sha256=request.left_source_sha256),
        options=options,
    )
    right_request = RetrievalSearchRequest(
        query=request.query,
        filters=SearchFilters(source_sha256=request.right_source_sha256),
        options=options,
    )
    try:
        spec = get_embedding_spec()
        left_source = await run_in_threadpool(
            catalog.get_source, request.left_source_sha256, spec
        )
        right_source = await run_in_threadpool(
            catalog.get_source, request.right_source_sha256, spec
        )
        missing = []
        if left_source is None:
            missing.append(request.left_source_sha256)
        if right_source is None:
            missing.append(request.right_source_sha256)
        if missing:
            raise ApiError(
                status_code=404,
                code="source_not_found",
                message="One or more comparison sources do not exist.",
                details={"source_sha256": missing},
            )
        left = await run_in_threadpool(service.search, left_request)
        right = await run_in_threadpool(service.search, right_request)
    except ApiError:
        raise
    except (OpenSearchError, RuntimeError, ValueError, psycopg.Error) as error:
        raise _unavailable(error) from error
    return SourceComparisonResponse(query=request.query, left=left, right=right)
