"""Versioned contracts for reproducible retrieval and grounding evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from racevault.extraction.models import ArtifactModel
from racevault.retrieval.models import SearchFilters


class EvidenceLabel(ArtifactModel):
    label_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    source_path: str
    page_number: int | None = Field(default=None, ge=1)
    text_contains: tuple[str, ...] = ()
    relevance_grade: int = Field(default=1, ge=1, le=3)


class GoldClaim(ArtifactModel):
    """One atomic fact expected in a grounded answer."""

    claim_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    text: str = Field(min_length=1)
    supporting_label_ids: tuple[str, ...] = ()
    required: bool = True


class EvaluationQuery(ArtifactModel):
    query_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    query: str = Field(min_length=1)
    category: str = Field(min_length=1)
    split: Literal["development", "test"] = "development"
    slices: tuple[str, ...] = ()
    document_family: str | None = None
    filters: SearchFilters = Field(default_factory=SearchFilters)
    relevant: tuple[EvidenceLabel, ...] = ()
    expected_empty: bool = False
    gold_claims: tuple[GoldClaim, ...] = ()
    expects_conflict: bool = False
    minimum_distinct_sources: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_labels(self) -> Self:
        if self.expected_empty and self.relevant:
            raise ValueError("empty-result queries must not define relevant evidence")
        if not self.expected_empty and not self.relevant:
            raise ValueError("positive queries require relevant evidence")
        label_ids = [item.label_id for item in self.relevant if item.label_id]
        if len(label_ids) != len(set(label_ids)):
            raise ValueError("evidence label IDs must be unique within a query")
        known_ids = set(label_ids)
        for claim in self.gold_claims:
            unknown = set(claim.supporting_label_ids) - known_ids
            if unknown:
                raise ValueError(
                    f"gold claim references unknown evidence labels: {sorted(unknown)}"
                )
        return self


class EvaluationDataset(ArtifactModel):
    schema_name: str = "racevault.retrieval_evaluation"
    schema_version: Literal[1, 2] = 2
    dataset_id: str = "racevault-legacy-v1"
    dataset_version: str = "1.0.0"
    queries: tuple[EvaluationQuery, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_query_ids(self) -> Self:
        ids = [item.query_id for item in self.queries]
        if len(set(ids)) != len(ids):
            raise ValueError("evaluation query IDs must be unique")
        families_by_split: dict[str, set[str]] = {"development": set(), "test": set()}
        for item in self.queries:
            if item.document_family:
                families_by_split[item.split].add(item.document_family.casefold())
        overlap = families_by_split["development"] & families_by_split["test"]
        if overlap:
            raise ValueError(
                "document families must not cross development and test splits: "
                f"{sorted(overlap)}"
            )
        return self


class MetricInterval(ArtifactModel):
    low: float
    high: float
    confidence: float = Field(default=0.95, gt=0, lt=1)


class StageResult(ArtifactModel):
    returned: int = Field(ge=0)
    maximum_score: float | None = None
    first_relevant_rank: int | None = Field(default=None, ge=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    ndcg_at_10: float = Field(default=0, ge=0, le=1)
    recall_at_5: float = Field(default=0, ge=0, le=1)
    recall_at_10: float = Field(default=0, ge=0, le=1)
    recall_at_20: float = Field(default=0, ge=0, le=1)
    context_precision_at_10: float = Field(default=0, ge=0, le=1)
    distinct_relevant_sources: int = Field(ge=0)
    passed: bool


class QueryEvaluationResult(ArtifactModel):
    query_id: str
    category: str
    expected_empty: bool
    split: Literal["development", "test"] = "development"
    slices: tuple[str, ...] = ()
    elapsed_ms: float = Field(default=0, ge=0)
    lexical: StageResult
    semantic: StageResult
    fused: StageResult
    reranked: StageResult


class StageSummary(ArtifactModel):
    positive_hit_rate: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    mean_ndcg_at_10: float = Field(default=0, ge=0, le=1)
    mean_recall_at_5: float = Field(default=0, ge=0, le=1)
    mean_recall_at_10: float = Field(default=0, ge=0, le=1)
    mean_recall_at_20: float = Field(default=0, ge=0, le=1)
    mean_context_precision_at_10: float = Field(default=0, ge=0, le=1)
    negative_accuracy: float = Field(ge=0, le=1)
    passed_queries: int = Field(ge=0)
    confidence_intervals: dict[str, MetricInterval] = Field(default_factory=dict)


class PairedComparison(ArtifactModel):
    metric: str
    left_stage: str
    right_stage: str
    mean_difference: float
    interval: MetricInterval
    probability_left_better: float = Field(ge=0, le=1)


class ResourceMeasurements(ArtifactModel):
    elapsed_ms: float = Field(default=0, ge=0)
    queries_per_second: float = Field(default=0, ge=0)
    peak_rss_mb: float | None = Field(default=None, ge=0)
    peak_gpu_memory_mb: float | None = Field(default=None, ge=0)
    cold_query_ms: float | None = Field(default=None, ge=0)
    warm_query_p50_ms: float | None = Field(default=None, ge=0)
    warm_query_p95_ms: float | None = Field(default=None, ge=0)
    index_size_gb: float | None = Field(default=None, ge=0)


class ExperimentFingerprint(ArtifactModel):
    run_id: str
    commit_sha: str
    dirty_worktree: bool
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    python_version: str
    platform: str
    hardware: dict[str, str]
    random_seed: int
    model_revisions: dict[str, str]


class EvaluationReport(ArtifactModel):
    schema_name: str = "racevault.retrieval_evaluation_report"
    schema_version: int = 2
    created_at: datetime
    query_count: int = Field(ge=1)
    positive_queries: int = Field(ge=0)
    negative_queries: int = Field(ge=0)
    dataset_id: str = "racevault-engineering-v2"
    dataset_version: str = "2.0.0"
    split: Literal["all", "development", "test"] = "all"
    ablation_label: str = "hybrid_reranked"
    experiment: ExperimentFingerprint | None = None
    resources: ResourceMeasurements = Field(default_factory=ResourceMeasurements)
    lexical: StageSummary
    semantic: StageSummary
    fused: StageSummary
    reranked: StageSummary
    slices: dict[str, dict[str, StageSummary]] = Field(default_factory=dict)
    comparisons: tuple[PairedComparison, ...] = ()
    results: tuple[QueryEvaluationResult, ...]
