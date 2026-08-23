"""Dependency-free late-interaction scoring for visual retrieval experiments."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Vector = Sequence[float]
MultiVector = Sequence[Vector]


def _dot(left: Vector, right: Vector) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    value = sum(a * b for a, b in zip(left, right, strict=True))
    if not math.isfinite(value):
        raise ValueError("embedding score must be finite")
    return value


def maxsim_score(query: MultiVector, document: MultiVector) -> float:
    """Compute ColBERT/ColPali MaxSim: sum_q(max_d(q dot d))."""

    if not query or not document:
        raise ValueError("query and document embeddings must contain tokens")
    dimensions = len(query[0])
    if dimensions == 0:
        raise ValueError("embedding vectors must contain dimensions")
    if any(len(vector) != dimensions for vector in (*query, *document)):
        raise ValueError("all embedding vectors must have the same dimensions")
    return sum(
        max(_dot(query_token, token) for token in document)
        for query_token in query
    )


@dataclass(frozen=True)
class RankedVisualPage:
    page_id: str
    rank: int
    maxsim_score: float


def rank_pages(
    query: MultiVector,
    pages: Mapping[str, MultiVector],
    *,
    limit: int,
) -> tuple[RankedVisualPage, ...]:
    if limit < 1:
        raise ValueError("visual result limit must be positive")
    scored = sorted(
        (
            (page_id, maxsim_score(query, embedding))
            for page_id, embedding in pages.items()
        ),
        key=lambda item: (-item[1], item[0]),
    )[:limit]
    return tuple(
        RankedVisualPage(page_id=page_id, rank=rank, maxsim_score=score)
        for rank, (page_id, score) in enumerate(scored, start=1)
    )
