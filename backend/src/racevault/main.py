"""RaceVault FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from racevault import __version__
from racevault.api.health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="RaceVault API",
        summary="Traceable motorsport engineering evidence retrieval",
        version=__version__,
    )
    application.include_router(health_router)

    @application.get("/", tags=["service"])
    async def root() -> dict[str, str]:
        return {"service": "racevault-api", "version": __version__}

    return application


app = create_app()

