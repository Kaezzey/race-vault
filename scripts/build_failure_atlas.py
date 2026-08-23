"""Render failed benchmark queries as an auditable Markdown failure atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    queries = {item["query_id"]: item for item in dataset["queries"]}
    sections = [
        "# RaceVault failure atlas",
        "",
        f"Report run: `{(report.get('experiment') or {}).get('run_id', 'unknown')}`",
        "",
        "Failures are retained rather than removed from aggregate reporting.",
    ]
    failures = 0
    for result in report["results"]:
        if result["reranked"]["passed"]:
            continue
        failures += 1
        query = queries[result["query_id"]]
        sections.extend(
            (
                "",
                f"## {result['query_id']}",
                "",
                f"- Query: {query['query']}",
                f"- Category: {result['category']}",
                f"- Split: {result.get('split', 'unknown')}",
                f"- Returned: {result['reranked']['returned']}",
                "- First relevant rank: "
                f"{result['reranked'].get('first_relevant_rank')}",
                f"- nDCG@10: {result['reranked'].get('ndcg_at_10', 0):.3f}",
                "- Root cause: _adjudication required_",
                "- Proposed action: _adjudication required_",
            )
        )
    sections.extend(("", f"Total failed queries: {failures}", ""))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Failure atlas: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
