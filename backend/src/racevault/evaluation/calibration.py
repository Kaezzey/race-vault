"""Development-only calibration for evidence-sufficiency abstention."""

from __future__ import annotations

import itertools
import math

from pydantic import Field

from racevault.evaluation.models import EvaluationReport, QueryEvaluationResult
from racevault.extraction.models import ArtifactModel


class SufficiencyCalibration(ArtifactModel):
    schema_name: str = "racevault.sufficiency_calibration"
    schema_version: int = 1
    threshold: float = Field(ge=0, le=1)
    development_queries: int = Field(ge=1)
    answerable_queries: int = Field(ge=1)
    unanswerable_queries: int = Field(ge=1)
    answerable_recall: float = Field(ge=0, le=1)
    unanswerable_recall: float = Field(ge=0, le=1)
    balanced_accuracy: float = Field(ge=0, le=1)
    source_run_id: str | None = None
    source_dataset_id: str
    source_dataset_version: str


def calibrate_sufficiency_threshold(
    report: EvaluationReport,
    *,
    minimum_answerable_recall: float = 0.8,
    minimum_unanswerable_recall: float = 0.9,
) -> SufficiencyCalibration:
    """Choose a threshold on development queries and reject held-out tuning."""

    if not 0 <= minimum_answerable_recall <= 1:
        raise ValueError("minimum_answerable_recall must be between zero and one")
    if not 0 <= minimum_unanswerable_recall <= 1:
        raise ValueError("minimum_unanswerable_recall must be between zero and one")
    development = [item for item in report.results if item.split == "development"]
    if report.split == "test" or not development:
        raise ValueError("sufficiency calibration requires development results")
    if len(development) != len(report.results):
        raise ValueError(
            "calibration input must contain only development results; "
            "do not tune on a report that includes held-out queries"
        )
    answerable = [item for item in development if not item.expected_empty]
    unanswerable = [item for item in development if item.expected_empty]
    if not answerable or not unanswerable:
        raise ValueError("calibration requires answerable and unanswerable queries")

    def score(item: QueryEvaluationResult) -> float:
        value = item.reranked.maximum_score
        return float(value) if value is not None else 0.0

    observed = sorted({score(item) for item in development})
    # Midpoints between adjacent observations keep the boundary off any single
    # development query. Without them the only candidates are the observed
    # scores themselves, so a separating threshold lands exactly on the
    # lowest-scoring answerable query and any drift flips its verdict.
    midpoints = {
        (low + high) / 2
        for low, high in itertools.pairwise(observed)
    }
    thresholds = sorted(
        {0.0, *observed, *midpoints, math.nextafter(max(observed), 1.0)}
    )
    feasible: list[tuple[float, float, float, float]] = []
    for threshold in thresholds:
        answerable_recall = sum(
            score(item) >= threshold for item in answerable
        ) / len(answerable)
        unanswerable_recall = sum(
            score(item) < threshold for item in unanswerable
        ) / len(unanswerable)
        balanced = (answerable_recall + unanswerable_recall) / 2
        if (
            answerable_recall >= minimum_answerable_recall
            and unanswerable_recall >= minimum_unanswerable_recall
        ):
            feasible.append(
                (
                    balanced,
                    answerable_recall,
                    unanswerable_recall,
                    threshold,
                )
            )
    if not feasible:
        raise ValueError(
            "no threshold satisfies both recall constraints; improve retrieval "
            "or revisit development-only constraints"
        )
    balanced, answerable_recall, unanswerable_recall, threshold = max(
        feasible,
        key=lambda item: (item[0], item[1], item[2], -item[3]),
    )
    return SufficiencyCalibration(
        threshold=threshold,
        development_queries=len(development),
        answerable_queries=len(answerable),
        unanswerable_queries=len(unanswerable),
        answerable_recall=answerable_recall,
        unanswerable_recall=unanswerable_recall,
        balanced_accuracy=balanced,
        source_run_id=(report.experiment.run_id if report.experiment else None),
        source_dataset_id=report.dataset_id,
        source_dataset_version=report.dataset_version,
    )
