"""Claim-level grounded-answer evaluation from human or calibrated judgements."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field, model_validator

from racevault.extraction.models import ArtifactModel


class ClaimJudgement(ArtifactModel):
    claim_id: str
    correct: bool
    supported_by_context: bool
    has_citation: bool
    citation_entails_claim: bool
    context_used: bool


class AnswerJudgement(ArtifactModel):
    query_id: str
    expected_claim_ids: tuple[str, ...] = ()
    claims: tuple[ClaimJudgement, ...] = ()
    expected_empty: bool = False
    predicted_insufficient: bool = False
    expected_conflict: bool = False
    predicted_conflict: bool = False
    citation_ids_valid: bool = True
    schema_valid: bool = True

    @model_validator(mode="after")
    def claim_ids_are_unique(self) -> AnswerJudgement:
        ids = [item.claim_id for item in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("judged claim IDs must be unique within an answer")
        return self


class GroundingSummary(ArtifactModel):
    answer_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)
    answer_correctness: float = Field(ge=0, le=1)
    answer_completeness: float = Field(ge=0, le=1)
    answer_f1: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    citation_entailment_precision: float = Field(ge=0, le=1)
    unsupported_claim_rate: float = Field(ge=0, le=1)
    context_utilization: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    abstention_precision: float = Field(ge=0, le=1)
    abstention_recall: float = Field(ge=0, le=1)
    conflict_f1: float = Field(ge=0, le=1)
    schema_failure_rate: float = Field(ge=0, le=1)


class GroundingJudgementDataset(ArtifactModel):
    schema_name: str = "racevault.grounding_judgements"
    schema_version: int = 1
    dataset_id: str
    evaluator: str
    evaluator_kind: str
    judgements: tuple[AnswerJudgement, ...]


def _ratio(numerator: int, denominator: int, *, empty: float = 1.0) -> float:
    return numerator / denominator if denominator else empty


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0


def summarize_grounding(
    judgements: Sequence[AnswerJudgement],
) -> GroundingSummary:
    claims = [claim for answer in judgements for claim in answer.claims]
    expected = {
        (answer.query_id, claim_id)
        for answer in judgements
        for claim_id in answer.expected_claim_ids
    }
    correct_ids = {
        (answer.query_id, claim.claim_id)
        for answer in judgements
        for claim in answer.claims
        if claim.correct
    }
    correct = sum(claim.correct for claim in claims)
    supported = sum(claim.supported_by_context for claim in claims)
    cited = sum(claim.has_citation for claim in claims)
    entailed = sum(
        claim.has_citation and claim.citation_entails_claim for claim in claims
    )
    context_used = sum(claim.context_used for claim in claims)
    precision = _ratio(correct, len(claims))
    recall = _ratio(len(expected & correct_ids), len(expected))

    predicted_empty = [item for item in judgements if item.predicted_insufficient]
    actual_empty = [item for item in judgements if item.expected_empty]
    true_empty = sum(
        item.expected_empty and item.predicted_insufficient for item in judgements
    )
    abstention_precision = _ratio(true_empty, len(predicted_empty))
    abstention_recall = _ratio(true_empty, len(actual_empty))

    predicted_conflict = [item for item in judgements if item.predicted_conflict]
    actual_conflict = [item for item in judgements if item.expected_conflict]
    true_conflict = sum(
        item.expected_conflict and item.predicted_conflict for item in judgements
    )
    conflict_precision = _ratio(true_conflict, len(predicted_conflict))
    conflict_recall = _ratio(true_conflict, len(actual_conflict))

    return GroundingSummary(
        answer_count=len(judgements),
        claim_count=len(claims),
        answer_correctness=precision,
        answer_completeness=recall,
        answer_f1=_f1(precision, recall),
        citation_coverage=_ratio(cited, len(claims)),
        citation_entailment_precision=_ratio(entailed, cited),
        unsupported_claim_rate=1 - _ratio(supported, len(claims)),
        context_utilization=_ratio(context_used, len(claims)),
        citation_validity=_ratio(
            sum(item.citation_ids_valid for item in judgements), len(judgements)
        ),
        abstention_precision=abstention_precision,
        abstention_recall=abstention_recall,
        conflict_f1=_f1(conflict_precision, conflict_recall),
        schema_failure_rate=1
        - _ratio(sum(item.schema_valid for item in judgements), len(judgements)),
    )
