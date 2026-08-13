"""Deterministic weighted Reciprocal Rank Fusion."""

from __future__ import annotations

from dataclasses import dataclass

from racevault.fusion.models import FusedCandidate, RrfSettings
from racevault.lexical.models import LexicalSearchHit
from racevault.retrieval.models import EvidenceHit
from racevault.semantic.models import SemanticSearchHit


@dataclass
class _Accumulated:
    evidence: EvidenceHit
    lexical_rank: int | None = None
    lexical_score: float | None = None
    semantic_rank: int | None = None
    semantic_score: float | None = None
    rrf_score: float = 0.0


def _evidence(hit: EvidenceHit) -> EvidenceHit:
    fields = EvidenceHit.model_fields
    return EvidenceHit.model_validate(
        {name: value for name, value in hit.model_dump().items() if name in fields}
    )


def reciprocal_rank_fusion(
    lexical_hits: tuple[LexicalSearchHit, ...],
    semantic_hits: tuple[SemanticSearchHit, ...],
    *,
    settings: RrfSettings,
    limit: int,
) -> tuple[FusedCandidate, ...]:
    accumulated: dict[str, _Accumulated] = {}

    for rank, lexical_hit in enumerate(lexical_hits, start=1):
        item = accumulated.setdefault(
            lexical_hit.chunk_id, _Accumulated(_evidence(lexical_hit))
        )
        item.lexical_rank = rank
        item.lexical_score = lexical_hit.score
        item.rrf_score += settings.lexical_weight / (settings.rank_constant + rank)

    for rank, semantic_hit in enumerate(semantic_hits, start=1):
        item = accumulated.setdefault(
            semantic_hit.chunk_id, _Accumulated(_evidence(semantic_hit))
        )
        if item.evidence.contextual_sha256 != semantic_hit.contextual_sha256:
            raise ValueError(
                f"retrieval channels disagree for chunk {semantic_hit.chunk_id}"
            )
        item.semantic_rank = rank
        item.semantic_score = semantic_hit.score
        item.rrf_score += settings.semantic_weight / (
            settings.rank_constant + rank
        )

    ordered = sorted(
        accumulated.values(),
        key=lambda item: (-item.rrf_score, item.evidence.chunk_id),
    )[:limit]
    return tuple(
        FusedCandidate(
            **item.evidence.model_dump(),
            lexical_rank=item.lexical_rank,
            lexical_score=item.lexical_score,
            semantic_rank=item.semantic_rank,
            semantic_score=item.semantic_score,
            rrf_score=item.rrf_score,
            fused_rank=rank,
        )
        for rank, item in enumerate(ordered, start=1)
    )
