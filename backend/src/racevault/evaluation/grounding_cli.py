"""Summarize claim-level grounded-answer judgements."""

from __future__ import annotations

import argparse
from pathlib import Path

from racevault.evaluation.grounding import (
    GroundingJudgementDataset,
    summarize_grounding,
)
from racevault.extraction.io import load_json, write_json_atomic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="racevault-grounding-evaluate")
    parser.add_argument("judgements", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    dataset = GroundingJudgementDataset.model_validate(load_json(args.judgements))
    summary = summarize_grounding(dataset.judgements)
    write_json_atomic(args.output, summary)
    print(f"answers={summary.answer_count} claims={summary.claim_count}")
    print(
        f"claim_f1={summary.answer_f1:.3f} "
        f"unsupported={summary.unsupported_claim_rate:.3f} "
        f"abstention_recall={summary.abstention_recall:.3f}"
    )
    passed = (
        summary.citation_validity == 1
        and summary.abstention_recall >= 0.9
        and summary.unsupported_claim_rate <= 0.05
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
