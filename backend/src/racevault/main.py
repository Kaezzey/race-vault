"""RaceVault FastAPI application factory."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

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
from racevault.telemetry import (
    bind_request_id,
    configure_json_logging,
    configure_opentelemetry,
    metrics,
    new_request_id,
    reset_request_id,
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
    configure_json_logging(settings.json_logging)
    configure_opentelemetry(
        settings.otel_exporter_endpoint,
        service_name=settings.otel_service_name,
    )
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        # The retrieval service and generation client each hold a connection
        # open for the process, because opening one costs more than the request
        # that follows it.
        for resource in (app.state.retrieval_service, app.state.answer_service):
            close = getattr(resource, "close", None)
            if callable(close):
                close()

    application = FastAPI(
        title="RaceVault API",
        summary="Traceable motorsport engineering evidence retrieval",
        version=__version__,
        lifespan=lifespan,
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
    application.state.pipeline_fingerprint = settings.pipeline_fingerprint
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def request_telemetry(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = new_request_id(request.headers.get("X-Request-ID"))
        token = bind_request_id(request_id)
        started = time.perf_counter()
        method = request.method
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            metrics.increment(
                "racevault_http_requests_total",
                labels={
                    "method": method,
                    "path": path,
                    "status": str(status_code),
                },
            )
            metrics.observe(
                "racevault_http_request_duration_seconds",
                time.perf_counter() - started,
                labels={"method": method, "path": path},
            )
            reset_request_id(token)
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

    if settings.metrics_enabled:
        @application.get("/metrics", tags=["operations"], include_in_schema=False)
        async def prometheus_metrics() -> PlainTextResponse:
            return PlainTextResponse(
                metrics.render_prometheus(),
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

    return application


app = create_app()
