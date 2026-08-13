"""Validated full-corpus manifest contracts."""

from __future__ import annotations

from typing import Self

from pydantic import Field, field_validator, model_validator

from racevault.chunking.models import DocumentClass
from racevault.extraction.models import ArtifactModel

SOURCE_AUTHORITIES = {
    "official_regulation",
    "manufacturer_document",
    "component_supplier_document",
    "engineering_reference",
    "team_document",
    "unknown",
}


class CorpusDocument(ArtifactModel):
    role: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    path: str = Field(min_length=1)
    document_type: DocumentClass
    authority: str
    title: str | None = None
    vehicle_generation: str | None = None
    championship: str | None = None
    season: int | None = Field(default=None, ge=1900, le=2200)
    revision: str | None = None
    language: str | None = None

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value: object) -> object:
        return value.replace("\\", "/") if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        normalized = self.path
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("document path must be corpus-relative")
        if not normalized.lower().endswith(".pdf"):
            raise ValueError("document path must identify a PDF")
        if self.authority not in SOURCE_AUTHORITIES:
            raise ValueError(f"unsupported source authority: {self.authority}")
        return self

    def extraction_metadata(self) -> dict[str, object]:
        values = self.model_dump(exclude={"role", "path"}, exclude_none=True)
        values["document_type"] = self.document_type.value
        return values


class CorpusManifest(ArtifactModel):
    schema_name: str = "racevault.corpus_manifest"
    schema_version: int = Field(default=1, ge=1)
    corpus_root: str = "AI & ML Reference File Database"
    documents: tuple[CorpusDocument, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_identity(self) -> Self:
        roles = [item.role for item in self.documents]
        paths = [item.path.casefold() for item in self.documents]
        if len(set(roles)) != len(roles):
            raise ValueError("manifest roles must be unique")
        if len(set(paths)) != len(paths):
            raise ValueError("manifest paths must be unique")
        if paths != sorted(paths):
            raise ValueError("manifest documents must be sorted by path")
        return self
