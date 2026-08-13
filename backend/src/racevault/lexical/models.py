"""Contracts for lexical indexing and search."""

from __future__ import annotations

from pydantic import Field, field_validator

from racevault.extraction.models import ArtifactModel
from racevault.retrieval.models import EvidenceHit
from racevault.retrieval.models import SearchFilters as SearchFilters


class LexicalSearchRequest(ArtifactModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value


class LexicalSearchHit(EvidenceHit):
    score: float
    highlights: tuple[str, ...] = ()


class LexicalSearchResponse(ArtifactModel):
    query: str
    total: int = Field(ge=0)
    hits: tuple[LexicalSearchHit, ...]


class IndexingResult(ArtifactModel):
    index_name: str
    source_sha256: str
    indexed_chunks: int = Field(ge=0)
    removed_chunks: int = Field(ge=0)
