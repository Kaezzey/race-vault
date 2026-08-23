"""V2 grounded-answer contracts."""

from __future__ import annotations

import re
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from racevault.api.models import CandidateCounts, Citation, RetrievalResult
from racevault.extraction.models import ArtifactModel
from racevault.retrieval.models import SearchFilters


class GroundedAnswerRequest(ArtifactModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: SearchFilters = Field(default_factory=SearchFilters)

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value


class GeneratedStatement(ArtifactModel):
    """One model-generated statement with explicit supporting evidence."""

    text: str = Field(
        min_length=1,
        max_length=4000,
        description=(
            "One self-contained statement. Do not include citation markers in "
            "this text."
        ),
    )
    citations: tuple[str, ...] = Field(
        min_length=1,
        max_length=10,
        description=(
            "Evidence identifiers that directly support this statement, without "
            "brackets."
        ),
    )
    facet_id: str | None = Field(
        default=None,
        pattern=r"^F[1-9][0-9]*$",
        description=(
            "Requested facet answered by this statement. Omit only when the "
            "user question has no explicit facet list."
        ),
    )

    @field_validator("text")
    @classmethod
    def text_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("statement text must contain text")
        return value

    @field_validator("citations")
    @classmethod
    def citations_must_be_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("citations must be unique")
        if any(not re.fullmatch(r"E[1-9][0-9]*", item) for item in value):
            raise ValueError("citations must be evidence identifiers")
        return value


class GeneratedAnswer(ArtifactModel):
    """Schema supplied to the local model and validated after generation."""

    answer: tuple[GeneratedStatement, ...] = Field(min_length=1, max_length=10)
    conflicts: tuple[GeneratedStatement, ...] = Field(max_length=3)
    limitations: tuple[GeneratedStatement, ...] = Field(max_length=6)
    insufficient_evidence: bool


class GenerationModelIdentity(ArtifactModel):
    model: str
    digest: str
    parameter_size: str | None
    quantization_level: str | None


class GenerationStatus(ArtifactModel):
    available: bool
    ollama_version: str
    model: GenerationModelIdentity
    capabilities: tuple[str, ...]


class GenerationUsage(ArtifactModel):
    total_duration_ms: int = Field(ge=0)
    load_duration_ms: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class AnswerTimings(ArtifactModel):
    retrieval_ms: int = Field(ge=0)
    generation_ms: int = Field(ge=0)


class GroundedCitation(ArtifactModel):
    evidence_id: str = Field(pattern=r"^E[1-9][0-9]*$")
    citation: Citation


class EvidenceSelectionDiagnostics(ArtifactModel):
    """Content-free explanation of the evidence controller's decision."""

    policy: str
    query_intent: Literal[
        "concept", "exact_or_numeric", "comparison_or_conflict"
    ]
    candidates_considered: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    duplicates_removed: int = Field(ge=0)
    distinct_sources: int = Field(ge=0)
    required_scopes: tuple[str, ...] = ()
    covered_scopes: tuple[str, ...] = ()
    requested_facets: tuple[str, ...] = ()
    covered_facets: tuple[str, ...] = ()
    missing_facets: tuple[str, ...] = ()
    maximum_reranker_score: float | None = Field(default=None, ge=0, le=1)
    minimum_score_threshold: float | None = Field(default=None, ge=0, le=1)
    sufficient: bool
    reason: Literal[
        "selected",
        "no_candidates",
        "below_calibrated_threshold",
        "missing_required_scope",
        "comparison_topic_too_broad",
    ]


class GroundedAnswerResponse(ArtifactModel):
    request_id: str | None = None
    pipeline_fingerprint: str | None = None
    query: str
    filters: SearchFilters
    resolved_scopes: tuple[SearchFilters, ...] = ()
    answer: str
    insufficient_evidence: bool
    conflicts: tuple[str, ...]
    limitations: tuple[str, ...]
    citations: tuple[GroundedCitation, ...]
    evidence: tuple[RetrievalResult, ...]
    retrieval_counts: CandidateCounts
    generation_model: GenerationModelIdentity
    generation_usage: GenerationUsage
    timings: AnswerTimings
    evidence_selection: EvidenceSelectionDiagnostics | None = None

    @model_validator(mode="after")
    def citations_must_reference_returned_evidence(self) -> Self:
        evidence_ids = {f"E{index}" for index in range(1, len(self.evidence) + 1)}
        citation_ids = {item.evidence_id for item in self.citations}
        if not citation_ids.issubset(evidence_ids):
            raise ValueError("citations reference evidence outside the response")
        return self
