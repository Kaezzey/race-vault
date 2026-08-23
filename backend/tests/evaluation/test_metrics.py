from __future__ import annotations

from racevault.evaluation.metrics import (
    bootstrap_interval,
    evaluate_stage,
    paired_bootstrap_comparison,
    summarize,
)
from racevault.evaluation.models import EvaluationQuery, EvidenceLabel
from tests.fusion.factories import lexical_hit


def _query(*, expected_empty: bool = False) -> EvaluationQuery:
    return EvaluationQuery(
        query_id="tyre",
        query="N3R",
        category="exact_identifier",
        relevant=(
            ()
            if expected_empty
            else (
                EvidenceLabel(
                    source_path="Porsche Technical Manuals/manual.pdf",
                    page_number=2,
                    text_contains=("ABS M5",),
                ),
            )
        ),
        expected_empty=expected_empty,
    )


def test_stage_reports_first_relevant_rank() -> None:
    result = evaluate_stage(
        (lexical_hit(1, text="irrelevant"), lexical_hit(2)), _query()
    )

    assert result.first_relevant_rank == 2
    assert result.reciprocal_rank == 0.5
    assert result.passed is True


def test_negative_query_requires_no_results() -> None:
    empty = evaluate_stage((), _query(expected_empty=True))
    nonempty = evaluate_stage((lexical_hit(1),), _query(expected_empty=True))

    assert empty.passed is True
    assert nonempty.passed is False


def test_summary_separates_positive_and_negative_metrics() -> None:
    positive = _query()
    negative = _query(expected_empty=True).model_copy(
        update={"query_id": "wrong_revision"}
    )
    results = (
        evaluate_stage((lexical_hit(2),), positive),
        evaluate_stage((), negative),
    )

    summary = summarize((positive, negative), results)

    assert summary.positive_hit_rate == 1.0
    assert summary.mean_reciprocal_rank == 1.0
    assert summary.negative_accuracy == 1.0


def test_graded_relevance_reports_ndcg_recall_and_context_precision() -> None:
    first = lexical_hit(1, text="secondary relevant evidence")
    second = lexical_hit(2, text="best exact evidence")
    query = EvaluationQuery(
        query_id="graded",
        query="graded retrieval",
        category="graded",
        relevant=(
            EvidenceLabel(
                source_path=first.source_path,
                text_contains=("best exact",),
                relevance_grade=3,
            ),
            EvidenceLabel(
                source_path=first.source_path,
                text_contains=("secondary relevant",),
                relevance_grade=1,
            ),
        ),
    )

    result = evaluate_stage((first, second), query)

    assert 0 < result.ndcg_at_10 < 1
    assert result.recall_at_5 == 1
    assert result.context_precision_at_10 == 1


def test_bootstrap_and_paired_comparison_are_deterministic() -> None:
    assert bootstrap_interval((0.0, 0.5, 1.0), seed=9) == bootstrap_interval(
        (0.0, 0.5, 1.0), seed=9
    )
    query = _query()
    left = evaluate_stage((lexical_hit(1),), query)
    right = evaluate_stage((lexical_hit(1, text="irrelevant"),), query)

    comparison = paired_bootstrap_comparison(
        (query,),
        (left,),
        (right,),
        left_stage="left",
        right_stage="right",
        samples=100,
    )

    assert comparison.mean_difference == 1
    assert comparison.interval.low == 1
    assert comparison.probability_left_better == 1


def test_ndcg_stays_within_range_when_chunks_share_one_label() -> None:
    """Structure-aware chunking splits one labelled passage across chunks."""

    query = EvaluationQuery(
        query_id="shared_label",
        query="ABS M5",
        category="exact_identifier",
        relevant=(
            EvidenceLabel(
                source_path="Porsche Technical Manuals/manual.pdf",
                page_number=2,
                text_contains=("ABS M5",),
                relevance_grade=3,
            ),
        ),
    )

    result = evaluate_stage(
        tuple(lexical_hit(number) for number in range(1, 4)), query
    )

    # Every hit matches the one label, so paying for each would exceed the ideal.
    assert result.ndcg_at_10 == 1.0
    assert result.recall_at_10 == 1.0
