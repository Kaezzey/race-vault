from __future__ import annotations

from datetime import UTC, datetime

import pytest

from racevault.evaluation.calibration import calibrate_sufficiency_threshold
from racevault.evaluation.models import (
    EvaluationReport,
    QueryEvaluationResult,
    StageResult,
    StageSummary,
)


def _stage(score: float) -> StageResult:
    return StageResult(
        returned=1,
        maximum_score=score,
        first_relevant_rank=1,
        reciprocal_rank=1,
        ndcg_at_10=1,
        recall_at_5=1,
        recall_at_10=1,
        recall_at_20=1,
        context_precision_at_10=1,
        distinct_relevant_sources=1,
        passed=True,
    )


def _summary() -> StageSummary:
    return StageSummary(
        positive_hit_rate=1,
        mean_reciprocal_rank=1,
        mean_ndcg_at_10=1,
        mean_recall_at_5=1,
        mean_recall_at_10=1,
        mean_recall_at_20=1,
        mean_context_precision_at_10=1,
        negative_accuracy=1,
        passed_queries=4,
    )


def _report(*, include_test: bool = False) -> EvaluationReport:
    values = (
        ("p1", False, 0.9),
        ("p2", False, 0.8),
        ("n1", True, 0.2),
        ("n2", True, 0.3),
    )
    results = tuple(
        QueryEvaluationResult(
            query_id=query_id,
            category="calibration",
            expected_empty=empty,
            split="test" if include_test and query_id == "n2" else "development",
            lexical=_stage(score),
            semantic=_stage(score),
            fused=_stage(score),
            reranked=_stage(score),
        )
        for query_id, empty, score in values
    )
    summary = _summary()
    return EvaluationReport(
        created_at=datetime.now(UTC),
        query_count=4,
        positive_queries=2,
        negative_queries=2,
        split="all" if include_test else "development",
        lexical=summary,
        semantic=summary,
        fused=summary,
        reranked=summary,
        results=results,
    )


def test_calibration_finds_separating_development_threshold() -> None:
    calibration = calibrate_sufficiency_threshold(_report())

    # Answerable queries score 0.8 and 0.9, unanswerable ones 0.2 and 0.3. The
    # boundary sits midway through the gap rather than on the 0.8 query, so a
    # small drift in that query's score does not flip its verdict.
    assert calibration.threshold == 0.55
    assert calibration.answerable_recall == 1
    assert calibration.unanswerable_recall == 1
    assert calibration.balanced_accuracy == 1


def test_calibration_rejects_report_containing_held_out_results() -> None:
    with pytest.raises(ValueError, match="only development"):
        calibrate_sufficiency_threshold(_report(include_test=True))
