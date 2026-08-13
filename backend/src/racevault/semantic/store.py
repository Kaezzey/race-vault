"""Transactional PostgreSQL storage and pgvector search."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, cast

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from racevault.chunking.identity import chunk_artifact_identity
from racevault.chunking.models import ChunkingArtifact
from racevault.semantic.models import (
    EmbeddedChunk,
    EmbeddingModelSpec,
    SemanticIndexingResult,
    SemanticSearchHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
)

FILTER_SQL: dict[str, str] = {
    "source_sha256": "d.sha256 = %s",
    "source_role": "d.source_role = %s",
    "document_class": "d.document_type::text = %s",
    "authority": "d.authority::text = %s",
    "vehicle_generation": "d.vehicle_generation = %s",
    "championship": "d.championship = %s",
    "season": "d.season = %s",
    "revision": "d.revision = %s",
    "page_number": "c.page_numbers @> ARRAY[%s]::smallint[]",
    "chunk_kind": "c.kind::text = %s",
    "oversize": "c.oversize = %s",
}


def _metadata_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


def _metadata_integer(metadata: dict[str, object], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class SemanticStore:
    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        connection = psycopg.connect(self._conninfo, row_factory=dict_row)
        register_vector(connection)
        return connection

    def existing_inputs(
        self,
        chunk_ids: Sequence[str],
        spec: EmbeddingModelSpec,
    ) -> dict[str, str]:
        if not chunk_ids:
            return {}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, input_sha256
                FROM chunk_embeddings
                WHERE model_id = %s
                  AND model_revision = %s
                  AND chunk_id = ANY(%s)
                """,
                (spec.model_id, spec.model_revision, list(chunk_ids)),
            ).fetchall()
        return {str(row["chunk_id"]): str(row["input_sha256"]) for row in rows}

    def _upsert_document(
        self,
        connection: psycopg.Connection[dict[str, Any]],
        artifact: ChunkingArtifact,
    ) -> uuid.UUID:
        source = artifact.source
        metadata = source.metadata
        row = connection.execute(
            """
            INSERT INTO documents (
                id, sha256, source_path, filename, source_role, title,
                document_type, vehicle_generation, championship, season,
                revision, authority, language, page_count, extra_metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::document_type, %s, %s, %s,
                %s, %s::source_authority, %s, %s, %s
            )
            ON CONFLICT (sha256) DO UPDATE SET
                source_path = EXCLUDED.source_path,
                filename = EXCLUDED.filename,
                source_role = EXCLUDED.source_role,
                title = EXCLUDED.title,
                document_type = EXCLUDED.document_type,
                vehicle_generation = EXCLUDED.vehicle_generation,
                championship = EXCLUDED.championship,
                season = EXCLUDED.season,
                revision = EXCLUDED.revision,
                authority = EXCLUDED.authority,
                language = EXCLUDED.language,
                page_count = EXCLUDED.page_count,
                extra_metadata = EXCLUDED.extra_metadata,
                updated_at = now()
            RETURNING id
            """,
            (
                uuid.uuid4(),
                source.sha256,
                source.relative_path,
                source.filename,
                source.role,
                _metadata_string(metadata, "title"),
                artifact.classification.document_class.value,
                _metadata_string(metadata, "vehicle_generation"),
                _metadata_string(metadata, "championship"),
                _metadata_integer(metadata, "season"),
                _metadata_string(metadata, "revision"),
                _metadata_string(metadata, "authority") or "unknown",
                _metadata_string(metadata, "language"),
                source.page_count,
                Jsonb(metadata),
            ),
        ).fetchone()
        if row is None or not isinstance(row["id"], uuid.UUID):
            raise RuntimeError("document upsert did not return an ID")
        return row["id"]

    def _upsert_chunks(
        self,
        connection: psycopg.Connection[dict[str, Any]],
        artifact: ChunkingArtifact,
        document_id: uuid.UUID,
        artifact_id: str,
    ) -> None:
        for chunk in artifact.chunks:
            connection.execute(
                """
                INSERT INTO chunks (
                    id, document_id, ordinal, artifact_id, extraction_sha256,
                    strategy, kind, evidence_text, evidence_sha256,
                    contextual_text, contextual_sha256, section_path,
                    clause_reference, page_start, page_end, page_numbers,
                    element_ids, table_ids, provenance, character_count, oversize
                ) VALUES (
                    %s, %s, %s, %s, %s, %s::chunk_strategy, %s::chunk_kind,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    ordinal = EXCLUDED.ordinal,
                    artifact_id = EXCLUDED.artifact_id,
                    extraction_sha256 = EXCLUDED.extraction_sha256,
                    strategy = EXCLUDED.strategy,
                    kind = EXCLUDED.kind,
                    evidence_text = EXCLUDED.evidence_text,
                    evidence_sha256 = EXCLUDED.evidence_sha256,
                    contextual_text = EXCLUDED.contextual_text,
                    contextual_sha256 = EXCLUDED.contextual_sha256,
                    section_path = EXCLUDED.section_path,
                    clause_reference = EXCLUDED.clause_reference,
                    page_start = EXCLUDED.page_start,
                    page_end = EXCLUDED.page_end,
                    page_numbers = EXCLUDED.page_numbers,
                    element_ids = EXCLUDED.element_ids,
                    table_ids = EXCLUDED.table_ids,
                    provenance = EXCLUDED.provenance,
                    character_count = EXCLUDED.character_count,
                    oversize = EXCLUDED.oversize
                """,
                (
                    chunk.chunk_id,
                    document_id,
                    chunk.ordinal,
                    artifact_id,
                    artifact.provenance.extraction_sha256,
                    chunk.strategy.value,
                    chunk.kind.value,
                    chunk.evidence_text,
                    chunk.evidence_sha256,
                    chunk.contextual_text,
                    chunk.contextual_sha256,
                    Jsonb(list(chunk.section_path)),
                    chunk.clause_reference,
                    chunk.page_start,
                    chunk.page_end,
                    list(chunk.page_numbers),
                    list(chunk.element_ids),
                    list(chunk.table_ids),
                    Jsonb([item.model_dump(mode="json") for item in chunk.provenance]),
                    chunk.character_count,
                    chunk.oversize,
                ),
            )

    def ingest(
        self,
        artifact: ChunkingArtifact,
        embeddings: Sequence[EmbeddedChunk],
        spec: EmbeddingModelSpec,
    ) -> SemanticIndexingResult:
        artifact_id = chunk_artifact_identity(artifact)
        embedded = {item.chunk_id: item for item in embeddings}
        expected_ids = {chunk.chunk_id for chunk in artifact.chunks}
        if not set(embedded).issubset(expected_ids):
            raise ValueError("embedding set references an unknown chunk")

        with self._connect() as connection, connection.transaction():
            document_id = self._upsert_document(connection, artifact)
            self._upsert_chunks(connection, artifact, document_id, artifact_id)
            for item in embeddings:
                connection.execute(
                    """
                    INSERT INTO chunk_embeddings (
                        chunk_id, model_id, model_revision, input_sha256,
                        dimensions, normalized, embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id, model_id, model_revision) DO UPDATE SET
                        input_sha256 = EXCLUDED.input_sha256,
                        dimensions = EXCLUDED.dimensions,
                        normalized = EXCLUDED.normalized,
                        embedding = EXCLUDED.embedding,
                        created_at = now()
                    """,
                    (
                        item.chunk_id,
                        spec.model_id,
                        spec.model_revision,
                        item.input_sha256,
                        spec.dimensions,
                        spec.normalized,
                        Vector(list(item.vector.values)),
                    ),
                )

            deleted = connection.execute(
                "DELETE FROM chunks WHERE document_id = %s AND artifact_id <> %s",
                (document_id, artifact_id),
            ).rowcount
            count_row = connection.execute(
                """
                SELECT count(*) AS count
                FROM chunk_embeddings ce
                JOIN chunks c ON c.id = ce.chunk_id
                WHERE c.document_id = %s
                  AND c.artifact_id = %s
                  AND ce.model_id = %s
                  AND ce.model_revision = %s
                  AND ce.input_sha256 = c.contextual_sha256
                """,
                (document_id, artifact_id, spec.model_id, spec.model_revision),
            ).fetchone()
            stored = int(count_row["count"]) if count_row is not None else 0
            if stored != len(artifact.chunks):
                raise RuntimeError(
                    f"stored embedding count mismatch: expected "
                    f"{len(artifact.chunks)}, got {stored}"
                )

        return SemanticIndexingResult(
            source_sha256=artifact.source.sha256,
            artifact_id=artifact_id,
            total_chunks=len(artifact.chunks),
            generated_embeddings=len(embeddings),
            reused_embeddings=len(artifact.chunks) - len(embeddings),
            removed_stale_chunks=max(deleted, 0),
        )

    def count(self, spec: EmbeddingModelSpec) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT count(*) AS count
                FROM chunk_embeddings
                WHERE model_id = %s AND model_revision = %s
                """,
                (spec.model_id, spec.model_revision),
            ).fetchone()
        return int(row["count"]) if row is not None else 0

    def search(
        self,
        request: SemanticSearchRequest,
        query_vector: Sequence[float],
    ) -> SemanticSearchResponse:
        values = request.filters.model_dump(exclude_none=True)
        conditions = [
            "ce.model_id = %s",
            "ce.model_revision = %s",
        ]
        parameters: list[object] = [request.model_id, request.model_revision]
        for name, value in values.items():
            conditions.append(FILTER_SQL[name])
            parameters.append(value)
        vector = Vector(list(query_vector))
        parameters.extend((vector, request.limit))
        where = " AND ".join(conditions)
        query = f"""
            SELECT
                c.id AS chunk_id, c.artifact_id, c.ordinal,
                1 - (ce.embedding <=> %s) AS score,
                c.evidence_text, c.evidence_sha256,
                c.contextual_text, c.contextual_sha256,
                d.source_path, d.filename AS source_filename,
                d.sha256 AS source_sha256, d.source_role,
                d.extra_metadata AS source_metadata,
                d.document_type::text AS document_class,
                c.strategy::text AS strategy, c.kind::text AS kind,
                c.section_path, c.clause_reference, c.page_start, c.page_end,
                c.page_numbers, c.element_ids, c.table_ids, c.provenance,
                c.character_count, c.oversize,
                ce.model_id, ce.model_revision
            FROM chunk_embeddings ce
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE {where}
            ORDER BY ce.embedding <=> %s, c.id
            LIMIT %s
        """
        # The vector is used for both the selected score and ordering.
        parameters.insert(0, vector)

        with self._connect() as connection, connection.transaction():
            connection.execute("SET LOCAL hnsw.iterative_scan = strict_order")
            rows = connection.execute(query, parameters).fetchall()
        hits = tuple(
            SemanticSearchHit.model_validate(cast(Mapping[str, object], row))
            for row in rows
        )
        return SemanticSearchResponse(query=request.query, hits=hits)
