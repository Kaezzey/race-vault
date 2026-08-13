"""Relevance matching and aggregate retrieval metrics."""

from __future__ import annotations

from collections.abc import Sequence

from racevault.evaluation.models import (
    EvaluationQuery,
    EvidenceLabel,
    StageResult,
    StageSummary,
)
from racevault.retrieval.models import EvidenceHit


def _matches(hit: EvidenceHit, label: EvidenceLabel) -> bool:
    if hit.source_path.casefold() != label.source_path.casefold():
        return False
    if label.page_number is not None and label.page_number not in hit.page_numbers:
        return False
    text = hit.evidence_text.casefold()
    return all(value.casefold() in text for value in label.text_contains)


def evaluate_stage(
    hits: Sequence[EvidenceHit], query: EvaluationQuery
) -> StageResult:
    if query.expected_empty:
        return StageResult(
            returned=len(hits),
            reciprocal_rank=1.0 if not hits else 0.0,
            distinct_relevant_sources=0,
            passed=not hits,
        )
    relevant = [
        (rank, hit)
        for rank, hit in enumerate(hits, start=1)
        if any(_matches(hit, label) for label in query.relevant)
    ]
    first_rank = relevant[0][0] if relevant else None
    sources = {hit.source_path.casefold() for _, hit in relevant}
    passed = first_rank is not None and len(sources) >= query.minimum_distinct_sources
    return StageResult(
        returned=len(hits),
        first_relevant_rank=first_rank,
        reciprocal_rank=1 / first_rank if first_rank is not None else 0,
        distinct_relevant_sources=len(sources),
        passed=passed,
    )


def summarize(
    queries: Sequence[EvaluationQuery], results: Sequence[StageResult]
) -> StageSummary:
    if len(queries) != len(results):
        raise ValueError("query and result counts must match")
    positives = [
        result
        for query, result in zip(queries, results, strict=True)
        if not query.expected_empty
    ]
    negatives = [
        result
        for query, result in zip(queries, results, strict=True)
        if query.expected_empty
    ]
    return StageSummary(
        positive_hit_rate=(
            sum(item.first_relevant_rank is not None for item in positives)
            / len(positives)
            if positives
            else 1.0
        ),
        mean_reciprocal_rank=(
            sum(item.reciprocal_rank for item in positives) / len(positives)
            if positives
            else 1.0
        ),
        negative_accuracy=(
            sum(item.passed for item in negatives) / len(negatives)
            if negatives
            else 1.0
        ),
        passed_queries=sum(item.passed for item in results),
    )
