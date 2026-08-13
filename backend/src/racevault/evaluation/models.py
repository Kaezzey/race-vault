"""Contracts for labelled queries and retrieval-quality reports."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from racevault.extraction.models import ArtifactModel
from racevault.retrieval.models import SearchFilters


class EvidenceLabel(ArtifactModel):
    source_path: str
    page_number: int | None = Field(default=None, ge=1)
    text_contains: tuple[str, ...] = ()


class EvaluationQuery(ArtifactModel):
    query_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    query: str = Field(min_length=1)
    category: str = Field(min_length=1)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    relevant: tuple[EvidenceLabel, ...] = ()
    expected_empty: bool = False
    minimum_distinct_sources: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_labels(self) -> Self:
        if self.expected_empty and self.relevant:
            raise ValueError("empty-result queries must not define relevant evidence")
        if not self.expected_empty and not self.relevant:
            raise ValueError("positive queries require relevant evidence")
        return self


class EvaluationDataset(ArtifactModel):
    schema_name: str = "racevault.retrieval_evaluation"
    schema_version: int = 1
    queries: tuple[EvaluationQuery, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_query_ids(self) -> Self:
        ids = [item.query_id for item in self.queries]
        if len(set(ids)) != len(ids):
            raise ValueError("evaluation query IDs must be unique")
        return self


class StageResult(ArtifactModel):
    returned: int = Field(ge=0)
    first_relevant_rank: int | None = Field(default=None, ge=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    distinct_relevant_sources: int = Field(ge=0)
    passed: bool


class QueryEvaluationResult(ArtifactModel):
    query_id: str
    category: str
    expected_empty: bool
    lexical: StageResult
    semantic: StageResult
    fused: StageResult
    reranked: StageResult


class StageSummary(ArtifactModel):
    positive_hit_rate: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    negative_accuracy: float = Field(ge=0, le=1)
    passed_queries: int = Field(ge=0)


class EvaluationReport(ArtifactModel):
    schema_name: str = "racevault.retrieval_evaluation_report"
    schema_version: int = 1
    created_at: datetime
    query_count: int = Field(ge=1)
    positive_queries: int = Field(ge=0)
    negative_queries: int = Field(ge=0)
    lexical: StageSummary
    semantic: StageSummary
    fused: StageSummary
    reranked: StageSummary
    results: tuple[QueryEvaluationResult, ...]
