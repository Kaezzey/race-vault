"""Corpus and index identity routes."""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from racevault.api.errors import ApiError
from racevault.api.services import get_catalog_store, get_embedding_spec
from racevault.catalog.models import CorpusStatus
from racevault.catalog.store import CatalogStore
from racevault.config import get_settings
from racevault.lexical.client import OpenSearchClient, OpenSearchError

router = APIRouter(prefix="/v1/corpus", tags=["corpus"])


def _opensearch_count() -> int:
    settings = get_settings()
    with OpenSearchClient(
        base_url=settings.opensearch_url,
        index_name=settings.opensearch_index_name,
        timeout_seconds=settings.opensearch_timeout_seconds,
    ) as client:
        return client.count()


@router.get("/status", response_model=CorpusStatus)
async def corpus_status(
    store: Annotated[CatalogStore, Depends(get_catalog_store)],
) -> CorpusStatus:
    try:
        opensearch_chunks = await run_in_threadpool(_opensearch_count)
        return await run_in_threadpool(
            store.corpus_status,
            spec=get_embedding_spec(),
            opensearch_chunks=opensearch_chunks,
        )
    except (OpenSearchError, RuntimeError, ValueError, psycopg.Error) as error:
        raise ApiError(
            status_code=503,
            code="corpus_status_unavailable",
            message="Corpus status is temporarily unavailable.",
            details={"reason": str(error)},
        ) from error
