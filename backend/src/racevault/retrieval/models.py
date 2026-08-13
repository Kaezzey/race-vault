"""Shared retrieval request fields."""

from __future__ import annotations

from pydantic import Field

from racevault.extraction.models import ArtifactModel


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
