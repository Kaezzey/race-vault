"""Shared retrieval request fields."""

from __future__ import annotations

from pydantic import Field

from racevault.extraction.models import ArtifactModel, ProvenanceRef


class SearchFilters(ArtifactModel):
    source_sha256: str | None = None
    source_role: str | None = None
    document_class: str | None = None
    authority: str | None = None
    vehicle_generation: str | None = None
    championship: str | None = None
    season: int | None = Field(default=None, ge=1900, le=2200)
    revision: str | None = None
    page_number: int | None = Field(default=None, ge=1, le=32767)
    chunk_kind: str | None = None
    oversize: bool | None = None


# SQL predicates for each SearchFilters field, shared by every reader that
# queries PostgreSQL. Document predicates apply to a source; chunk predicates
# additionally need the chunks table in scope.
DOCUMENT_FILTER_SQL: dict[str, str] = {
    "source_sha256": "d.sha256 = %s",
    "source_role": "d.source_role = %s",
    "document_class": "d.document_type::text = %s",
    "authority": "d.authority::text = %s",
    "vehicle_generation": "d.vehicle_generation = %s",
    "championship": "d.championship = %s",
    "season": "d.season = %s",
    "revision": "d.revision = %s",
}
CHUNK_FILTER_SQL: dict[str, str] = {
    "page_number": "c.page_numbers @> ARRAY[%s]::smallint[]",
    "chunk_kind": "c.kind::text = %s",
    "oversize": "c.oversize = %s",
}


class EvidenceHit(ArtifactModel):
    """Citation-ready evidence fields shared by retrieval channels."""

    chunk_id: str
    artifact_id: str
    ordinal: int
    evidence_text: str
    evidence_sha256: str
    contextual_text: str
    contextual_sha256: str
    source_path: str
    source_filename: str
    source_sha256: str
    source_role: str | None
    source_metadata: dict[str, object]
    document_class: str
    strategy: str
    kind: str
    section_path: tuple[str, ...]
    clause_reference: str | None
    page_start: int
    page_end: int
    page_numbers: tuple[int, ...]
    element_ids: tuple[str, ...]
    table_ids: tuple[str, ...]
    provenance: tuple[ProvenanceRef, ...]
    character_count: int
    oversize: bool
