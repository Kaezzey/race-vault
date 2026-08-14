"""RaceVault FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from racevault import __version__
from racevault.api.answers import router as answers_router
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
from racevault.api.source_management import (
    LocalSourceManager,
    SourceManager,
)
from racevault.api.sources import router as sources_router
from racevault.catalog.store import CatalogStore
from racevault.config import get_settings
from racevault.generation.service import (
    AnswerService,
    build_answer_service,
)


def create_app(
    *,
    retrieval_service: RetrievalService | None = None,
    catalog_store: CatalogStore | None = None,
    ingestion_coordinator: IngestionCoordinator | None = None,
    source_manager: SourceManager | None = None,
    answer_service: AnswerService | None = None,
) -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="RaceVault API",
        summary="Traceable motorsport engineering evidence retrieval",
        version=__version__,
    )
    configured_catalog = catalog_store or CatalogStore(
        settings.psycopg_conninfo,
        connect_timeout_seconds=settings.dependency_timeout_seconds,
    )
    configured_retrieval = retrieval_service or HybridRetrievalService(
        settings,
        configured_catalog,
    )
    application.state.retrieval_service = configured_retrieval
    application.state.answer_service = answer_service or build_answer_service(
        settings, configured_retrieval
    )
    application.state.catalog_store = configured_catalog
    application.state.ingestion_coordinator = (
        ingestion_coordinator or LocalIngestionCoordinator(settings)
    )
    application.state.source_manager = source_manager or LocalSourceManager(settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(application)
    application.include_router(health_router)
    application.include_router(retrieval_router)
    application.include_router(sources_router)
    application.include_router(corpus_router)
    application.include_router(ingestion_router)
    application.include_router(answers_router)

    @application.get("/", tags=["service"])
    async def root() -> dict[str, str]:
        return {"service": "racevault-api", "version": __version__}

    return application


app = create_app()
