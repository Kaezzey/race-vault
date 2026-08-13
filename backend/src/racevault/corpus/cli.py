"""Command-line interface for corpus inventory management."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import ExitStack
from pathlib import Path

import psycopg

from racevault.chunking.pipeline import ChunkingOptions
from racevault.config import get_settings
from racevault.corpus.ingestion import IngestionReport, IngestionStage, ingest_manifest
from racevault.corpus.manifest import (
    apply_curated_metadata,
    discover_manifest,
    load_manifest,
    validate_manifest_coverage,
)
from racevault.extraction.io import write_json_atomic
from racevault.extraction.pipeline import ExtractionOptions
from racevault.lexical.client import OpenSearchClient, OpenSearchError
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.store import SemanticStore

DEFAULT_CORPUS_ROOT = Path("AI & ML Reference File Database")
DEFAULT_MANIFEST = Path("corpus/full_documents.json")
DEFAULT_CURATED = Path("corpus/representative_documents.json")
DEFAULT_EXTRACTION_ROOT = Path(".artifacts/extracted")
DEFAULT_CHUNK_ROOT = Path(".artifacts/chunks")
DEFAULT_REPORT = Path(".artifacts/reports/full-ingestion.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="racevault-corpus",
        description="Generate and validate the RaceVault full-corpus inventory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate the full manifest.")
    generate.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    generate.add_argument("--curated", type=Path, default=DEFAULT_CURATED)
    generate.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)

    audit = commands.add_parser("audit", help="Validate complete PDF coverage.")
    audit.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    audit.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)

    ingest = commands.add_parser("ingest", help="Run resumable corpus ingestion.")
    ingest.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ingest.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    ingest.add_argument("--extraction-root", type=Path, default=DEFAULT_EXTRACTION_ROOT)
    ingest.add_argument("--chunk-root", type=Path, default=DEFAULT_CHUNK_ROOT)
    ingest.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ingest.add_argument(
        "--through",
        type=IngestionStage,
        choices=tuple(IngestionStage),
        default=IngestionStage.SEMANTIC,
    )
    ingest.add_argument("--role", action="append")
    ingest.add_argument(
        "--extraction-device", default="cpu" if os.name == "nt" else "auto"
    )
    ingest.add_argument(
        "--embedding-device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
    )
    ingest.add_argument("--threads", type=int, default=8)
    ingest.add_argument("--embedding-batch-size", type=int)
    ingest.add_argument("--local-files-only", action="store_true")
    ingest.add_argument("--fail-fast", action="store_true")
    return parser


def _run_ingestion(args: argparse.Namespace) -> int:
    settings = get_settings()
    manifest = load_manifest(args.manifest)
    validate_manifest_coverage(manifest, args.corpus_root)
    through = IngestionStage(args.through)

    with ExitStack() as stack:
        lexical = None
        if through in {IngestionStage.LEXICAL, IngestionStage.SEMANTIC}:
            lexical = stack.enter_context(
                OpenSearchClient(
                    base_url=settings.opensearch_url,
                    index_name=settings.opensearch_index_name,
                    timeout_seconds=settings.opensearch_timeout_seconds,
                )
            )
        embedder = None
        store = None
        if through is IngestionStage.SEMANTIC:
            embedder = BgeM3Embedder(
                spec=EmbeddingModelSpec(
                    model_id=settings.semantic_model_id,
                    model_revision=settings.semantic_model_revision,
                    max_tokens=settings.semantic_max_tokens,
                ),
                device=args.embedding_device,
                batch_size=args.embedding_batch_size or settings.semantic_batch_size,
                local_files_only=args.local_files_only,
            )
            store = SemanticStore(settings.psycopg_conninfo)

        def checkpoint(report: IngestionReport) -> None:
            write_json_atomic(args.report, report)
            latest = report.documents[-1]
            print(
                f"[{len(report.documents)}/{report.selected_documents}] "
                f"{latest.status}: {latest.path}"
            )
            if latest.error:
                print(f"  {latest.error}", file=sys.stderr)

        report = ingest_manifest(
            manifest,
            corpus_root=args.corpus_root,
            extraction_root=args.extraction_root,
            chunk_root=args.chunk_root,
            through=through,
            extraction_options=ExtractionOptions(
                device=args.extraction_device,
                num_threads=args.threads,
            ),
            chunking_options=ChunkingOptions(),
            lexical=lexical,
            semantic_embedder=embedder,
            semantic_store=store,
            roles=set(args.role) if args.role else None,
            continue_on_error=not args.fail_fast,
            progress=checkpoint,
        )
    write_json_atomic(args.report, report)
    print(
        f"Completed: {report.completed_documents}; failed: "
        f"{report.failed_documents}; chunks: {report.total_chunks}"
    )
    return 1 if report.failed_documents else 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            manifest = discover_manifest(args.corpus_root)
            if args.curated.is_file():
                manifest = apply_curated_metadata(manifest, args.curated)
            write_json_atomic(args.output, manifest)
            print(f"Wrote {len(manifest.documents)} documents: {args.output}")
            return 0

        if args.command == "ingest":
            return _run_ingestion(args)

        manifest = load_manifest(args.manifest)
        paths = validate_manifest_coverage(manifest, args.corpus_root)
        total_bytes = sum(path.stat().st_size for path in paths)
        by_type: dict[str, int] = {}
        for document in manifest.documents:
            name = document.document_type.value
            by_type[name] = by_type.get(name, 0) + 1
        print(f"Valid: {len(paths)} PDFs; {total_bytes / 1024 / 1024:.1f} MB")
        for name, count in sorted(by_type.items()):
            print(f"{name}: {count}")
        return 0
    except (
        FileNotFoundError,
        KeyError,
        OpenSearchError,
        RuntimeError,
        ValueError,
        psycopg.Error,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
