"""Annotation agreement measurements for graded relevance labels."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from racevault.extraction.models import ArtifactModel


class AnnotationPair(ArtifactModel):
    item_id: str
    first_grade: int = Field(ge=0, le=3)
    second_grade: int = Field(ge=0, le=3)


class AgreementSummary(ArtifactModel):
    item_count: int = Field(ge=0)
    exact_agreement: float = Field(ge=0, le=1)
    quadratic_weighted_kappa: float = Field(ge=-1, le=1)


def annotation_agreement(pairs: Sequence[AnnotationPair]) -> AgreementSummary:
    if not pairs:
        return AgreementSummary(
            item_count=0, exact_agreement=1, quadratic_weighted_kappa=1
        )
    categories = 4
    observed = [[0.0] * categories for _ in range(categories)]
    first_counts = [0.0] * categories
    second_counts = [0.0] * categories
    for pair in pairs:
        observed[pair.first_grade][pair.second_grade] += 1
        first_counts[pair.first_grade] += 1
        second_counts[pair.second_grade] += 1
    count = len(pairs)
    weighted_observed = 0.0
    weighted_expected = 0.0
    for first in range(categories):
        for second in range(categories):
            weight = ((first - second) / (categories - 1)) ** 2
            weighted_observed += weight * observed[first][second] / count
            expected = first_counts[first] * second_counts[second] / (count * count)
            weighted_expected += weight * expected
    kappa = (
        1 - weighted_observed / weighted_expected
        if weighted_expected
        else 1.0
    )
    return AgreementSummary(
        item_count=count,
        exact_agreement=sum(pair.first_grade == pair.second_grade for pair in pairs)
        / count,
        quadratic_weighted_kappa=kappa,
    )
