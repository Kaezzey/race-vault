"""Calibrate the runtime evidence threshold from a development report."""

from __future__ import annotations

import argparse
from pathlib import Path

from racevault.evaluation.calibration import calibrate_sufficiency_threshold
from racevault.evaluation.models import EvaluationReport
from racevault.extraction.io import load_json, write_json_atomic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="racevault-calibrate-sufficiency")
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-answerable-recall", type=float, default=0.8)
    parser.add_argument("--minimum-unanswerable-recall", type=float, default=0.9)
    args = parser.parse_args(argv)
    report = EvaluationReport.model_validate(load_json(args.report))
    calibration = calibrate_sufficiency_threshold(
        report,
        minimum_answerable_recall=args.minimum_answerable_recall,
        minimum_unanswerable_recall=args.minimum_unanswerable_recall,
    )
    write_json_atomic(args.output, calibration)
    print(f"threshold={calibration.threshold:.6f}")
    print(
        f"answerable_recall={calibration.answerable_recall:.3f} "
        f"unanswerable_recall={calibration.unanswerable_recall:.3f} "
        f"balanced_accuracy={calibration.balanced_accuracy:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
