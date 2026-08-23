from __future__ import annotations

from racevault.evaluation.annotation import AnnotationPair, annotation_agreement


def test_annotation_agreement_reports_exact_and_weighted_values() -> None:
    summary = annotation_agreement(
        (
            AnnotationPair(item_id="a", first_grade=3, second_grade=3),
            AnnotationPair(item_id="b", first_grade=2, second_grade=2),
            AnnotationPair(item_id="c", first_grade=0, second_grade=1),
        )
    )

    assert summary.item_count == 3
    assert summary.exact_agreement == 2 / 3
    assert 0 < summary.quadratic_weighted_kappa < 1
