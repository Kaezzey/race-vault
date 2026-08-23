from __future__ import annotations

from racevault.evaluation.models import MetricInterval
from racevault.evaluation.visual import VisualGateInput, evaluate_visual_gate
from racevault.visual.maxsim import maxsim_score, rank_pages


def test_maxsim_ranks_page_with_matching_patches_first() -> None:
    query = ((1.0, 0.0), (0.0, 1.0))
    pages = {
        "matching": ((1.0, 0.0), (0.0, 1.0)),
        "weak": ((0.5, 0.5),),
    }

    ranked = rank_pages(query, pages, limit=2)

    assert ranked[0].page_id == "matching"
    assert maxsim_score(query, pages["matching"]) == 2


def test_visual_gate_requires_quality_confidence_latency_and_storage() -> None:
    decision = evaluate_visual_gate(
        VisualGateInput(
            text_ndcg_at_10=0.70,
            fused_ndcg_at_10=0.76,
            improvement_interval=MetricInterval(low=0.01, high=0.10),
            added_latency_p95_seconds=2.5,
            index_size_gb=7.5,
            query_count=40,
        )
    )

    assert decision.enabled is True


def test_visual_gate_explains_rejection() -> None:
    decision = evaluate_visual_gate(
        VisualGateInput(
            text_ndcg_at_10=0.70,
            fused_ndcg_at_10=0.72,
            improvement_interval=MetricInterval(low=-0.01, high=0.05),
            added_latency_p95_seconds=3,
            index_size_gb=8,
            query_count=20,
        )
    )

    assert decision.enabled is False
    assert len(decision.reasons) == 5
