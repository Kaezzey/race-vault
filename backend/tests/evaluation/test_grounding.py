from __future__ import annotations

from racevault.evaluation.grounding import (
    AnswerJudgement,
    ClaimJudgement,
    summarize_grounding,
)


def test_claim_level_grounding_summary_separates_support_and_correctness() -> None:
    summary = summarize_grounding(
        (
            AnswerJudgement(
                query_id="answerable",
                expected_claim_ids=("mass", "tyre"),
                claims=(
                    ClaimJudgement(
                        claim_id="mass",
                        correct=True,
                        supported_by_context=True,
                        has_citation=True,
                        citation_entails_claim=True,
                        context_used=True,
                    ),
                    ClaimJudgement(
                        claim_id="invented",
                        correct=False,
                        supported_by_context=False,
                        has_citation=True,
                        citation_entails_claim=False,
                        context_used=False,
                    ),
                ),
            ),
            AnswerJudgement(
                query_id="empty",
                expected_empty=True,
                predicted_insufficient=True,
            ),
        )
    )

    assert summary.answer_correctness == 0.5
    assert summary.answer_completeness == 0.5
    assert summary.unsupported_claim_rate == 0.5
    assert summary.citation_entailment_precision == 0.5
    assert summary.abstention_recall == 1
