"""Report agreement for independently graded relevance annotations."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from racevault.evaluation.annotation import AnnotationPair, annotation_agreement
from racevault.extraction.io import load_json, write_json_atomic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="racevault-annotation-agreement")
    parser.add_argument("pairs", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    pairs = TypeAdapter(tuple[AnnotationPair, ...]).validate_python(
        load_json(args.pairs)
    )
    summary = annotation_agreement(pairs)
    write_json_atomic(args.output, summary)
    print(
        f"items={summary.item_count} exact={summary.exact_agreement:.3f} "
        f"weighted_kappa={summary.quadratic_weighted_kappa:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
