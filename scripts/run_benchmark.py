"""Cross-platform quick validation and full RaceVault benchmark entry point."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend" / "src"))

from racevault.evaluation.runner import load_dataset

from scripts.build_public_fixture_pdfs import build_fixtures


def _hashes(root: Path) -> dict[str, str]:
    return {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in root.glob("*.pdf")
    }


def quick() -> int:
    source = REPOSITORY_ROOT / "evaluation" / "public" / "fixture_sources.json"
    dataset = REPOSITORY_ROOT / "evaluation" / "public" / "queries-v2.example.json"
    with tempfile.TemporaryDirectory(prefix="racevault-benchmark-") as directory:
        root = Path(directory)
        first = root / "first"
        second = root / "second"
        build_fixtures(source, first)
        build_fixtures(source, second)
        if _hashes(first) != _hashes(second):
            raise RuntimeError("public fixture generation is not deterministic")
    loaded = load_dataset(dataset)
    print(
        f"Validated dataset {loaded.dataset_id} {loaded.dataset_version}: "
        f"{len(loaded.queries)} example queries"
    )
    return 0


def full(arguments: list[str]) -> int:
    command = [
        sys.executable,
        "-m",
        "racevault.evaluation.cli",
        "--dataset",
        str(REPOSITORY_ROOT / "evaluation" / "queries.json"),
        *arguments,
    ]
    return subprocess.run(command, cwd=REPOSITORY_ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_benchmark.py")
    parser.add_argument("mode", choices=("quick", "full"))
    args, extra = parser.parse_known_args(argv)
    return quick() if args.mode == "quick" else full(extra)


if __name__ == "__main__":
    raise SystemExit(main())
