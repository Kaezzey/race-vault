"""Graded retrieval metrics, uncertainty estimates, and paired comparisons."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence

from racevault.evaluation.models import (
    EvaluationQuery,
    EvidenceLabel,
    MetricInterval,
    PairedComparison,
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


def _matched_label_indices(
    hit: EvidenceHit, labels: Sequence[EvidenceLabel]
) -> tuple[int, ...]:
    return tuple(index for index, label in enumerate(labels) if _matches(hit, label))


def _graded_ranking(
    matched_by_rank: Sequence[tuple[int, ...]],
    labels: Sequence[EvidenceLabel],
) -> list[int]:
    """Grade each rank, crediting every label at most once.

    Structure-aware chunking often splits one labelled passage across several
    chunks, so a single label can match at more than one rank. Paying for it
    each time makes the observed DCG exceed the ideal DCG and pushes nDCG above
    1. Each label is therefore credited at its earliest rank only.
    """

    credited: set[int] = set()
    grades: list[int] = []
    for matches in matched_by_rank:
        fresh = [index for index in matches if index not in credited]
        credited.update(fresh)
        grades.append(
            max((labels[index].relevance_grade for index in fresh), default=0)
        )
    return grades


def _dcg(grades: Sequence[int]) -> float:
    return float(
        sum(
            ((2**grade) - 1) / math.log2(rank + 1)
            for rank, grade in enumerate(grades, start=1)
        )
    )


def _recall_at(
    matched_by_rank: Sequence[tuple[int, ...]], *, label_count: int, limit: int
) -> float:
    if label_count == 0:
        return 1.0
    matched = {
        label_index
        for indices in matched_by_rank[:limit]
        for label_index in indices
    }
    return len(matched) / label_count


def evaluate_stage(
    hits: Sequence[EvidenceHit], query: EvaluationQuery
) -> StageResult:
    scores = []
    for hit in hits:
        score = getattr(hit, "reranker_score", None)
        if score is None:
            score = getattr(hit, "score", None)
        if score is not None:
            scores.append(float(score))
    maximum_score = max(scores, default=None)
    if query.expected_empty:
        return StageResult(
            returned=len(hits),
            maximum_score=maximum_score,
            reciprocal_rank=1.0 if not hits else 0.0,
            distinct_relevant_sources=0,
            passed=not hits,
        )

    matched_by_rank = [_matched_label_indices(hit, query.relevant) for hit in hits]
    relevant = [
        (rank, hit)
        for rank, (hit, matches) in enumerate(
            zip(hits, matched_by_rank, strict=True), start=1
        )
        if matches
    ]
    first_rank = relevant[0][0] if relevant else None
    sources = {hit.source_path.casefold() for _, hit in relevant}
    passed = first_rank is not None and len(sources) >= query.minimum_distinct_sources

    grades = _graded_ranking(matched_by_rank[:10], query.relevant)
    ideal_grades = sorted(
        (label.relevance_grade for label in query.relevant), reverse=True
    )[:10]
    ideal_dcg = _dcg(ideal_grades)
    top_ten = matched_by_rank[:10]
    relevant_hits = sum(bool(matches) for matches in top_ten)
    precision_denominator = min(10, len(hits))

    return StageResult(
        returned=len(hits),
        maximum_score=maximum_score,
        first_relevant_rank=first_rank,
        reciprocal_rank=1 / first_rank if first_rank is not None else 0,
        ndcg_at_10=_dcg(grades) / ideal_dcg if ideal_dcg else 1.0,
        recall_at_5=_recall_at(
            matched_by_rank, label_count=len(query.relevant), limit=5
        ),
        recall_at_10=_recall_at(
            matched_by_rank, label_count=len(query.relevant), limit=10
        ),
        recall_at_20=_recall_at(
            matched_by_rank, label_count=len(query.relevant), limit=20
        ),
        context_precision_at_10=(
            relevant_hits / precision_denominator if precision_denominator else 0
        ),
        distinct_relevant_sources=len(sources),
        passed=passed,
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 1.0


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        return 0.0
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def bootstrap_interval(
    values: Sequence[float],
    *,
    samples: int = 1000,
    seed: int = 17,
    confidence: float = 0.95,
) -> MetricInterval:
    """Return a deterministic percentile bootstrap interval for a sample mean."""

    if not values:
        return MetricInterval(low=1.0, high=1.0, confidence=confidence)
    if samples < 1:
        value = _mean(values)
        return MetricInterval(low=value, high=value, confidence=confidence)
    generator = random.Random(seed)
    size = len(values)
    estimates = sorted(
        _mean([values[generator.randrange(size)] for _ in range(size)])
        for _ in range(samples)
    )
    tail = (1 - confidence) / 2
    return MetricInterval(
        low=_quantile(estimates, tail),
        high=_quantile(estimates, 1 - tail),
        confidence=confidence,
    )


_POSITIVE_METRICS: dict[str, Callable[[StageResult], float]] = {
    "positive_hit_rate": lambda item: float(item.first_relevant_rank is not None),
    "mean_reciprocal_rank": lambda item: item.reciprocal_rank,
    "mean_ndcg_at_10": lambda item: item.ndcg_at_10,
    "mean_recall_at_5": lambda item: item.recall_at_5,
    "mean_recall_at_10": lambda item: item.recall_at_10,
    "mean_recall_at_20": lambda item: item.recall_at_20,
    "mean_context_precision_at_10": lambda item: item.context_precision_at_10,
}


def summarize(
    queries: Sequence[EvaluationQuery],
    results: Sequence[StageResult],
    *,
    bootstrap_samples: int = 0,
    random_seed: int = 17,
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
    metric_values = {
        name: [extractor(item) for item in positives]
        for name, extractor in _POSITIVE_METRICS.items()
    }
    negative_values = [float(item.passed) for item in negatives]
    intervals: dict[str, MetricInterval] = {}
    if bootstrap_samples:
        for offset, (name, values) in enumerate(metric_values.items()):
            intervals[name] = bootstrap_interval(
                values,
                samples=bootstrap_samples,
                seed=random_seed + offset,
            )
        intervals["negative_accuracy"] = bootstrap_interval(
            negative_values,
            samples=bootstrap_samples,
            seed=random_seed + len(metric_values),
        )
    return StageSummary(
        positive_hit_rate=_mean(metric_values["positive_hit_rate"]),
        mean_reciprocal_rank=_mean(metric_values["mean_reciprocal_rank"]),
        mean_ndcg_at_10=_mean(metric_values["mean_ndcg_at_10"]),
        mean_recall_at_5=_mean(metric_values["mean_recall_at_5"]),
        mean_recall_at_10=_mean(metric_values["mean_recall_at_10"]),
        mean_recall_at_20=_mean(metric_values["mean_recall_at_20"]),
        mean_context_precision_at_10=_mean(
            metric_values["mean_context_precision_at_10"]
        ),
        negative_accuracy=_mean(negative_values),
        passed_queries=sum(item.passed for item in results),
        confidence_intervals=intervals,
    )


def paired_bootstrap_comparison(
    queries: Sequence[EvaluationQuery],
    left: Sequence[StageResult],
    right: Sequence[StageResult],
    *,
    left_stage: str,
    right_stage: str,
    metric: str = "ndcg_at_10",
    samples: int = 1000,
    seed: int = 17,
) -> PairedComparison:
    """Compare two stages with paired query-level bootstrap resampling."""

    if len(queries) != len(left) or len(left) != len(right):
        raise ValueError("paired comparison inputs must have matching lengths")
    pairs = [
        (getattr(left_item, metric), getattr(right_item, metric))
        for query, left_item, right_item in zip(queries, left, right, strict=True)
        if not query.expected_empty
    ]
    if not pairs:
        differences = [0.0]
    else:
        generator = random.Random(seed)
        differences = []
        for _ in range(samples):
            drawn = [pairs[generator.randrange(len(pairs))] for _ in pairs]
            differences.append(_mean([a - b for a, b in drawn]))
    ordered = sorted(differences)
    return PairedComparison(
        metric=metric,
        left_stage=left_stage,
        right_stage=right_stage,
        mean_difference=_mean([a - b for a, b in pairs]) if pairs else 0.0,
        interval=MetricInterval(
            low=_quantile(ordered, 0.025),
            high=_quantile(ordered, 0.975),
        ),
        probability_left_better=sum(value > 0 for value in differences)
        / len(differences),
    )
