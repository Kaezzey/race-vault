from __future__ import annotations

from racevault.evaluation.metrics import evaluate_stage, summarize
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
