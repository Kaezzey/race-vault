"""Evaluate the frozen visual-retrieval promotion gate."""

from __future__ import annotations

import argparse
from pathlib import Path

from racevault.evaluation.visual import VisualGateInput, evaluate_visual_gate
from racevault.extraction.io import load_json, write_json_atomic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="racevault-visual-gate")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    gate_input = VisualGateInput.model_validate(load_json(args.input))
    decision = evaluate_visual_gate(gate_input)
    if args.output:
        write_json_atomic(args.output, decision)
    print("enabled" if decision.enabled else "not enabled")
    for reason in decision.reasons:
        print(f"- {reason}")
    return 0 if decision.enabled else 1


if __name__ == "__main__":
    raise SystemExit(main())
