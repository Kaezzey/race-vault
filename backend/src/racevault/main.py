"""RaceVault FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from racevault import __version__
from racevault.api.corpus import router as corpus_router
from racevault.api.errors import install_error_handlers
from racevault.api.health import router as health_router
from racevault.api.ingestion import router as ingestion_router
from racevault.api.ingestion_service import (
    IngestionCoordinator,
    LocalIngestionCoordinator,
)
from racevault.api.retrieval import router as retrieval_router
from racevault.api.services import HybridRetrievalService, RetrievalService
from racevault.api.sources import router as sources_router
from racevault.catalog.store import CatalogStore
from racevault.config import get_settings


def create_app(
    *,
    retrieval_service: RetrievalService | None = None,
    catalog_store: CatalogStore | None = None,
    ingestion_coordinator: IngestionCoordinator | None = None,
) -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="RaceVault API",
        summary="Traceable motorsport engineering evidence retrieval",
        version=__version__,
    )
    application.state.retrieval_service = (
        retrieval_service or HybridRetrievalService(settings)
    )
    application.state.catalog_store = catalog_store or CatalogStore(
        settings.psycopg_conninfo,
        connect_timeout_seconds=settings.dependency_timeout_seconds,
    )
    application.state.ingestion_coordinator = (
        ingestion_coordinator or LocalIngestionCoordinator(settings)
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(application)
    application.include_router(health_router)
    application.include_router(retrieval_router)
    application.include_router(sources_router)
    application.include_router(corpus_router)
    application.include_router(ingestion_router)

    @application.get("/", tags=["service"])
    async def root() -> dict[str, str]:
        return {"service": "racevault-api", "version": __version__}

    return application


app = create_app()
