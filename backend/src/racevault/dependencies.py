"""External dependency probes used by the readiness endpoint."""

from __future__ import annotations

import math

import httpx
import psycopg

from racevault.config import Settings


async def check_postgres(settings: Settings) -> str:
    timeout = settings.dependency_timeout_seconds
    async with await psycopg.AsyncConnection.connect(
        settings.psycopg_conninfo, connect_timeout=max(1, math.ceil(timeout))
    ) as connection, connection.cursor() as cursor:
        await cursor.execute("SELECT 1")
        value = await cursor.fetchone()
    if value != (1,):
        raise RuntimeError("unexpected PostgreSQL readiness response")
    return "ok"


async def check_opensearch(settings: Settings) -> str:
    timeout = settings.dependency_timeout_seconds
    url = f"{settings.opensearch_url.rstrip('/')}/_cluster/health"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        status = response.json().get("status")
    if status not in {"green", "yellow"}:
        raise RuntimeError(f"OpenSearch cluster status is {status!r}")
    return "ok"
