"""Read-only PostgreSQL queries for source and corpus inspection."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from racevault.catalog.models import (
    CorpusStatus,
    SourceChunk,
    SourceChunkListResponse,
    SourceListResponse,
    SourceSummary,
)
from racevault.retrieval.models import SearchFilters
from racevault.semantic.models import EmbeddingModelSpec

SOURCE_FILTER_SQL = {
    "source_sha256": "d.sha256 = %s",
    "source_role": "d.source_role = %s",
    "document_class": "d.document_type::text = %s",
    "authority": "d.authority::text = %s",
    "vehicle_generation": "d.vehicle_generation = %s",
    "championship": "d.championship = %s",
    "season": "d.season = %s",
    "revision": "d.revision = %s",
}


def _source(row: Mapping[str, object]) -> SourceSummary:
    return SourceSummary.model_validate(
        {
            "source_sha256": row["source_sha256"],
            "source_path": row["source_path"],
            "filename": row["filename"],
            "source_role": row["source_role"],
            "title": row["title"],
            "document_type": row["document_type"],
            "vehicle_generation": row["vehicle_generation"],
            "championship": row["championship"],
            "season": row["season"],
            "revision": row["revision"],
            "authority": row["authority"],
            "language": row["language"],
            "page_count": row["page_count"],
            "extra_metadata": row["extra_metadata"],
            "chunk_count": row["chunk_count"],
            "embedding_count": row["embedding_count"],
        }
    )


class CatalogStore:
    def __init__(self, conninfo: str, connect_timeout_seconds: float = 2.0) -> None:
        self._conninfo = conninfo
        self._connect_timeout = max(1, math.ceil(connect_timeout_seconds))

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(
            self._conninfo,
            row_factory=dict_row,
            connect_timeout=self._connect_timeout,
        )

    def _source_conditions(
        self, filters: SearchFilters
    ) -> tuple[list[str], list[object]]:
        values = filters.model_dump(exclude_none=True)
        unsupported = set(values) - set(SOURCE_FILTER_SQL)
        if unsupported:
            raise ValueError(
                f"source listing does not support filters: {sorted(unsupported)}"
            )
        conditions = [SOURCE_FILTER_SQL[name] for name in values]
        parameters = [values[name] for name in values]
        return conditions, parameters

    def list_sources(
        self,
        *,
        filters: SearchFilters,
        spec: EmbeddingModelSpec,
        limit: int,
        offset: int,
    ) -> SourceListResponse:
        conditions, parameters = self._source_conditions(filters)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        count_query = f"SELECT count(*) AS total FROM documents d {where}"
        query = f"""
            SELECT
                d.sha256 AS source_sha256, d.source_path, d.filename,
                d.source_role, d.title, d.document_type::text AS document_type,
                d.vehicle_generation, d.championship, d.season, d.revision,
                d.authority::text AS authority, d.language, d.page_count,
                d.extra_metadata,
                count(DISTINCT c.id) AS chunk_count,
                count(DISTINCT ce.chunk_id) FILTER (
                    WHERE ce.model_id = %s AND ce.model_revision = %s
                      AND ce.input_sha256 = c.contextual_sha256
                ) AS embedding_count
            FROM documents d
            LEFT JOIN chunks c ON c.document_id = d.id
            LEFT JOIN chunk_embeddings ce ON ce.chunk_id = c.id
            {where}
            GROUP BY d.id
            ORDER BY d.source_path, d.sha256
            LIMIT %s OFFSET %s
        """
        with self._connect() as connection:
            count_row = connection.execute(count_query, parameters).fetchone()
            rows = connection.execute(
                query,
                [spec.model_id, spec.model_revision, *parameters, limit, offset],
            ).fetchall()
        total = int(count_row["total"]) if count_row is not None else 0
        return SourceListResponse(
            total=total,
            limit=limit,
            offset=offset,
            sources=tuple(_source(row) for row in rows),
        )

    def get_source(
        self, source_sha256: str, spec: EmbeddingModelSpec
    ) -> SourceSummary | None:
        response = self.list_sources(
            filters=SearchFilters(source_sha256=source_sha256),
            spec=spec,
            limit=1,
            offset=0,
        )
        return response.sources[0] if response.sources else None

    def list_championships(self) -> tuple[str, ...]:
        """Return the championship values available for retrieval filters."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT championship
                FROM documents
                WHERE championship IS NOT NULL
                ORDER BY championship
                """
            ).fetchall()
        return tuple(str(row["championship"]) for row in rows)

    def list_chunks(
        self,
        *,
        source_sha256: str,
        limit: int,
        offset: int,
        page_number: int | None = None,
        kind: str | None = None,
    ) -> SourceChunkListResponse:
        conditions = ["d.sha256 = %s"]
        parameters: list[object] = [source_sha256]
        if page_number is not None:
            conditions.append("c.page_numbers @> ARRAY[%s]::smallint[]")
            parameters.append(page_number)
        if kind is not None:
            conditions.append("c.kind::text = %s")
            parameters.append(kind)
        where = " AND ".join(conditions)
        count_query = f"""
            SELECT count(*) AS total
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE {where}
        """
        query = f"""
            SELECT c.id AS chunk_id, c.ordinal, c.kind::text AS kind,
                   c.evidence_text, c.evidence_sha256, c.section_path,
                   c.clause_reference, c.page_start, c.page_end,
                   c.page_numbers, c.table_ids, c.provenance, c.oversize
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE {where}
            ORDER BY c.ordinal, c.id
            LIMIT %s OFFSET %s
        """
        with self._connect() as connection:
            count_row = connection.execute(count_query, parameters).fetchone()
            rows = connection.execute(
                query, [*parameters, limit, offset]
            ).fetchall()
        total = int(count_row["total"]) if count_row is not None else 0
        return SourceChunkListResponse(
            source_sha256=source_sha256,
            total=total,
            limit=limit,
            offset=offset,
            chunks=tuple(SourceChunk.model_validate(row) for row in rows),
        )

    def corpus_status(
        self, *, spec: EmbeddingModelSpec, opensearch_chunks: int
    ) -> CorpusStatus:
        query = """
            SELECT
                (SELECT count(*) FROM documents) AS documents,
                (SELECT count(*) FROM chunks) AS chunks,
                (SELECT count(*) FROM chunk_embeddings
                 WHERE model_id = %s AND model_revision = %s) AS embeddings,
                (SELECT count(DISTINCT c.document_id)
                 FROM chunks c
                 JOIN chunk_embeddings ce ON ce.chunk_id = c.id
                 WHERE ce.model_id = %s AND ce.model_revision = %s
                   AND ce.input_sha256 = c.contextual_sha256
                ) AS embedded_documents
        """
        with self._connect() as connection:
            row = connection.execute(
                query,
                (
                    spec.model_id,
                    spec.model_revision,
                    spec.model_id,
                    spec.model_revision,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("corpus status query returned no row")
        documents = int(cast(int, row["documents"]))
        chunks = int(cast(int, row["chunks"]))
        embeddings = int(cast(int, row["embeddings"]))
        embedded_documents = int(cast(int, row["embedded_documents"]))
        return CorpusStatus(
            documents=documents,
            chunks=chunks,
            embeddings=embeddings,
            embedded_documents=embedded_documents,
            opensearch_chunks=opensearch_chunks,
            consistent=(
                chunks == embeddings == opensearch_chunks
                and documents == embedded_documents
            ),
            embedding_model_id=spec.model_id,
            embedding_model_revision=spec.model_revision,
        )
