from __future__ import annotations

from collections.abc import Sequence

from racevault.fusion.models import RerankerSpec, RrfSettings
from racevault.fusion.reranker import rerank_candidates
from racevault.fusion.rrf import reciprocal_rank_fusion
from tests.fusion.factories import lexical_hit


class FakeReranker:
    spec = RerankerSpec()

    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]:
        assert query == "brake adjustment"
        assert len(passages) == 2
        return (0.1, 0.9)


def test_reranker_reorders_fused_candidates_and_preserves_rrf_rank() -> None:
    first = lexical_hit(1, text="less relevant")
    second = lexical_hit(2, text="brake adjustment wheel")
    fused = reciprocal_rank_fusion(
        (first, second), (), settings=RrfSettings(), limit=2
    )

    results = rerank_candidates(
        "brake adjustment", fused, reranker=FakeReranker(), limit=2
    )

    assert [result.chunk_id for result in results] == [second.chunk_id, first.chunk_id]
    assert results[0].fused_rank == 2
    assert results[0].final_rank == 1
    assert results[0].reranker_score == 0.9
