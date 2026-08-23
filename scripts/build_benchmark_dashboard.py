"""Render a self-contained benchmark dashboard from v2 report artifacts."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def _cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return html.escape(str(value))


def build_dashboard(reports: list[dict[str, object]]) -> str:
    rows = []
    for report in reports:
        summary = report["reranked"]
        resources = report.get("resources", {})
        experiment = report.get("experiment") or {}
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{_cell(value)}</td>"
                for value in (
                    report.get("ablation_label", "unknown"),
                    report.get("split", "all"),
                    report.get("query_count", 0),
                    summary.get("mean_ndcg_at_10", 0),
                    summary.get("mean_recall_at_10", 0),
                    summary.get("mean_reciprocal_rank", 0),
                    summary.get("negative_accuracy", 0),
                    resources.get("warm_query_p95_ms", "n/a"),
                    resources.get("index_size_gb", "n/a"),
                    str(experiment.get("commit_sha", "unknown"))[:12],
                )
            )
            + "</tr>"
        )
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>RaceVault benchmark</title>
<style>
body{{font:16px system-ui;margin:2rem;background:#0d1117;color:#e6edf3}}
table{{border-collapse:collapse;width:100%}}
th,td{{padding:.7rem;border:1px solid #30363d;text-align:right}}
th:first-child,td:first-child{{text-align:left}}th{{background:#161b22}}
caption{{text-align:left;font-size:1.5rem;margin-bottom:1rem}}
.note{{color:#9da7b3;max-width:70rem}}
</style>
<p class="note">Every row is generated from a machine-readable,
commit-fingerprinted report. No scores are embedded in this dashboard
generator.</p>
<table><caption>Held-out quality and systems trade-offs</caption><thead><tr>
<th>Configuration</th><th>Split</th><th>Queries</th><th>nDCG@10</th>
<th>R@10</th><th>MRR</th><th>Negative accuracy</th><th>Warm p95 ms</th>
<th>Index GB</th><th>Commit</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_dashboard(reports), encoding="utf-8")
    print(f"Dashboard: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
