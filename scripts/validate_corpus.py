"""Validate the representative corpus manifest without modifying source files."""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "corpus" / "representative_documents.json"


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    corpus_root = (REPOSITORY_ROOT / manifest["corpus_root"]).resolve()
    roles: set[str] = set()
    errors: list[str] = []

    for document in manifest["documents"]:
        role = document["role"]
        if role in roles:
            errors.append(f"duplicate role: {role}")
        roles.add(role)

        relative_path = PurePosixPath(document["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"unsafe path for {role}: {relative_path}")
            continue

        source_path = corpus_root.joinpath(*relative_path.parts).resolve()
        if not source_path.is_relative_to(corpus_root):
            errors.append(f"path escapes corpus for {role}: {relative_path}")
        elif not source_path.is_file():
            errors.append(f"missing source for {role}: {relative_path}")
        elif source_path.suffix.lower() != ".pdf":
            errors.append(f"source is not a PDF for {role}: {relative_path}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        f"Validated {len(manifest['documents'])} representative PDFs "
        f"under {corpus_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

