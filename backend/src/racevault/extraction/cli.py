"""Command-line interface for PDF extraction and artifact validation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from racevault.extraction.pipeline import (
    ExtractionOptions,
    extract_document,
    validate_extraction_artifact,
)

DEFAULT_CORPUS_ROOT = Path("AI & ML Reference File Database")
DEFAULT_OUTPUT_ROOT = Path(".artifacts/extracted")
DEFAULT_MANIFEST = Path("corpus/representative_documents.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="racevault-extract",
        description="Extract versioned, page-aware evidence from RaceVault PDFs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Extract one PDF.")
    source_group = extract.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", help="Corpus-relative PDF path.")
    source_group.add_argument("--role", help="Role in the representative manifest.")
    extract.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    extract.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    extract.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    extract.add_argument("--page-start", type=int, default=1)
    extract.add_argument("--page-end", type=int)
    extract.add_argument(
        "--device", default="cpu" if os.name == "nt" else "auto"
    )
    extract.add_argument("--threads", type=int, default=8)
    extract.add_argument("--ocr", action="store_true")
    extract.add_argument("--no-tables", action="store_true")
    extract.add_argument("--compile-models", action="store_true")
    extract.add_argument("--force", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate an artifact.")
    validate.add_argument("artifact", type=Path)
    validate.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    validate.add_argument("--verify-source", action="store_true")
    return parser


def _manifest_source(
    manifest_path: Path, role: str
) -> tuple[str, dict[str, object]]:
    with manifest_path.open("r", encoding="utf-8") as source:
        manifest: dict[str, Any] = json.load(source)
    matches = [item for item in manifest["documents"] if item["role"] == role]
    if len(matches) != 1:
        raise ValueError(f"manifest role must match exactly one document: {role}")
    item = dict(matches[0])
    relative_path = str(item.pop("path"))
    item.pop("role", None)
    return relative_path, item


def _extract(args: argparse.Namespace) -> int:
    if args.role:
        relative_path, metadata = _manifest_source(args.manifest, args.role)
        role = str(args.role)
    else:
        relative_path = str(args.source)
        metadata = {}
        role = None

    result = extract_document(
        corpus_root=args.corpus_root,
        relative_path=relative_path,
        output_root=args.output_root,
        role=role,
        metadata=metadata,
        options=ExtractionOptions(
            page_start=args.page_start,
            page_end=args.page_end,
            device=args.device,
            num_threads=args.threads,
            ocr_enabled=args.ocr,
            table_structure_enabled=not args.no_tables,
            model_compilation_enabled=args.compile_models,
            force=args.force,
        ),
    )
    artifact = result.artifact
    state = "Reused" if result.reused else "Created"
    print(f"{state}: {result.artifact_path}")
    print(f"Source SHA-256: {artifact.source.sha256}")
    print(
        f"Pages: {artifact.statistics.extracted_pages}; "
        f"elements: {artifact.statistics.elements}; "
        f"tables: {artifact.statistics.tables}"
    )
    return 0


def _validate(args: argparse.Namespace) -> int:
    artifact = validate_extraction_artifact(
        args.artifact,
        corpus_root=args.corpus_root,
        verify_source_hash=args.verify_source,
    )
    print(f"Valid: {args.artifact}")
    print(f"Source SHA-256: {artifact.source.sha256}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            return _extract(args)
        return _validate(args)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

