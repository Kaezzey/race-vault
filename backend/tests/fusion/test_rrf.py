from __future__ import annotations

import pytest

from racevault.fusion.models import RrfSettings
from racevault.fusion.rrf import reciprocal_rank_fusion
from tests.fusion.factories import lexical_hit, semantic_hit


def test_rrf_combines_channel_ranks_and_deduplicates_chunks() -> None:
    shared = lexical_hit(1, score=10.0)
    lexical_only = lexical_hit(2, score=9.0)
    semantic_shared = semantic_hit(shared, score=0.8)

    results = reciprocal_rank_fusion(
        (shared, lexical_only),
        (semantic_shared,),
        settings=RrfSettings(rank_constant=60),
        limit=10,
    )

    assert [result.chunk_id for result in results] == [
        shared.chunk_id,
        lexical_only.chunk_id,
    ]
    assert results[0].lexical_rank == 1
    assert results[0].semantic_rank == 1
    assert results[0].rrf_score == pytest.approx(2 / 61)
    assert results[1].rrf_score == pytest.approx(1 / 62)


def test_rrf_uses_chunk_id_for_stable_ties() -> None:
    higher_id = lexical_hit(2)
    lower_id = lexical_hit(1)

    results = reciprocal_rank_fusion(
        (higher_id,),
        (semantic_hit(lower_id),),
        settings=RrfSettings(),
        limit=10,
    )

    assert [result.chunk_id for result in results] == [
        lower_id.chunk_id,
        higher_id.chunk_id,
    ]


def test_rrf_rejects_channel_evidence_mismatch() -> None:
    lexical = lexical_hit(1)
    semantic = semantic_hit(lexical).model_copy(
        update={"contextual_sha256": "f" * 64}
    )

    with pytest.raises(ValueError, match="disagree"):
        reciprocal_rank_fusion(
            (lexical,),
            (semantic,),
            settings=RrfSettings(),
            limit=10,
        )
