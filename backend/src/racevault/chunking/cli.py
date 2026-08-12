"""Command-line interface for classification and chunking."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from racevault.chunking.classifier import classify_document
from racevault.chunking.pipeline import (
    ChunkingOptions,
    chunk_extraction,
    validate_chunking_artifact,
)
from racevault.extraction.io import load_json
from racevault.extraction.models import ExtractionArtifact

DEFAULT_OUTPUT_ROOT = Path(".artifacts/chunks")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="racevault-chunk",
        description="Classify and chunk a RaceVault extraction artifact.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify = subparsers.add_parser("classify", help="Classify an extraction.")
    classify.add_argument("extraction", type=Path)

    chunk = subparsers.add_parser("chunk", help="Create chunks from an extraction.")
    chunk.add_argument("extraction", type=Path)
    chunk.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    chunk.add_argument("--max-characters", type=int, default=2400)
    chunk.add_argument("--no-section-context", action="store_true")
    chunk.add_argument("--force", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate chunk output.")
    validate.add_argument("artifact", type=Path)
    validate.add_argument("--extraction", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "classify":
            extraction = ExtractionArtifact.model_validate(load_json(args.extraction))
            classification = classify_document(extraction)
            print(f"Document class: {classification.document_class.value}")
            print(f"Strategy: {classification.strategy.value}")
            print(f"Method: {classification.method} ({classification.rule})")
            return 0
        if args.command == "chunk":
            result = chunk_extraction(
                extraction_path=args.extraction,
                output_root=args.output_root,
                options=ChunkingOptions(
                    max_characters=args.max_characters,
                    include_section_context=not args.no_section_context,
                    force=args.force,
                ),
            )
            state = "Reused" if result.reused else "Created"
            print(f"{state}: {result.artifact_path}")
            print(
                f"Class: {result.artifact.classification.document_class.value}; "
                f"strategy: {result.artifact.classification.strategy.value}"
            )
            print(
                f"Chunks: {result.artifact.statistics.chunks}; "
                f"tables: {result.artifact.statistics.table_chunks}; "
                f"oversize: {result.artifact.statistics.oversize_chunks}"
            )
            return 0

        artifact = validate_chunking_artifact(
            args.artifact, extraction_path=args.extraction
        )
        print(f"Valid: {args.artifact}")
        print(f"Chunks: {artifact.statistics.chunks}")
        return 0
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
