"""Conversion from chunk artifacts to OpenSearch documents."""

from __future__ import annotations

from racevault.chunking.identity import chunk_artifact_identity
from racevault.chunking.models import ChunkArtifact, ChunkingArtifact


def build_index_document(
    artifact: ChunkingArtifact, chunk: ChunkArtifact
) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "artifact_id": chunk_artifact_identity(artifact),
        "ordinal": chunk.ordinal,
        "source_sha256": artifact.source.sha256,
        "source_path": artifact.source.relative_path,
        "source_filename": artifact.source.filename,
        "source_role": artifact.source.role,
        "source_metadata": artifact.source.metadata,
        "document_class": chunk.document_class.value,
        "strategy": chunk.strategy.value,
        "kind": chunk.kind.value,
        "evidence_text": chunk.evidence_text,
        "evidence_sha256": chunk.evidence_sha256,
        "contextual_text": chunk.contextual_text,
        "contextual_sha256": chunk.contextual_sha256,
        "section_path": list(chunk.section_path),
        "section_text": " > ".join(chunk.section_path),
        "clause_reference": chunk.clause_reference,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "page_numbers": list(chunk.page_numbers),
        "element_ids": list(chunk.element_ids),
        "table_ids": list(chunk.table_ids),
        "provenance": [item.model_dump(mode="json") for item in chunk.provenance],
        "character_count": chunk.character_count,
        "oversize": chunk.oversize,
        "authority": artifact.source.metadata_string("authority"),
        "vehicle_generation": artifact.source.metadata_string("vehicle_generation"),
        "championship": artifact.source.metadata_string("championship"),
        "season": artifact.source.metadata_integer("season"),
        "revision": artifact.source.metadata_string("revision"),
    }
