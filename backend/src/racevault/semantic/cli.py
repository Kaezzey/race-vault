"""Command-line interface for dense embedding and semantic search."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from racevault.config import get_settings
from racevault.retrieval.models import SearchFilters
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec, SemanticSearchRequest
from racevault.semantic.pipeline import index_chunk_artifact, semantic_search
from racevault.semantic.store import SemanticStore


def _add_model_options(parser: argparse.ArgumentParser) -> None:
    settings = get_settings()
    parser.add_argument("--model-id", default=settings.semantic_model_id)
    parser.add_argument("--model-revision", default=settings.semantic_model_revision)
    parser.add_argument("--max-tokens", type=int, default=settings.semantic_max_tokens)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=settings.semantic_batch_size)
    parser.add_argument("--local-files-only", action="store_true")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="racevault-semantic",
        description="Generate BGE-M3 embeddings and search them with pgvector.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    embed = subparsers.add_parser("embed", help="Embed one chunks.json artifact.")
    embed.add_argument("artifact", type=Path)
    _add_model_options(embed)

    search = subparsers.add_parser("search", help="Run filtered semantic search.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--source-sha256")
    search.add_argument("--source-role")
    search.add_argument("--document-class")
    search.add_argument("--authority")
    search.add_argument("--vehicle-generation")
    search.add_argument("--championship")
    search.add_argument("--season", type=int)
    search.add_argument("--revision")
    search.add_argument("--page", type=int)
    search.add_argument("--chunk-kind")
    search.add_argument("--oversize", action=argparse.BooleanOptionalAction)
    _add_model_options(search)

    count = subparsers.add_parser("count", help="Count stored dense embeddings.")
    settings = get_settings()
    count.add_argument("--model-id", default=settings.semantic_model_id)
    count.add_argument("--model-revision", default=settings.semantic_model_revision)
    return parser


def _spec(args: argparse.Namespace) -> EmbeddingModelSpec:
    return EmbeddingModelSpec(
        model_id=str(args.model_id),
        model_revision=str(args.model_revision),
        max_tokens=int(args.max_tokens),
    )


def _embedder(args: argparse.Namespace) -> BgeM3Embedder:
    return BgeM3Embedder(
        spec=_spec(args),
        device=str(args.device),
        batch_size=int(args.batch_size),
        local_files_only=bool(args.local_files_only),
    )


def _emit(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(value.encode(encoding, errors="replace").decode(encoding))


def _search(args: argparse.Namespace, store: SemanticStore) -> int:
    embedder = _embedder(args)
    response = semantic_search(
        SemanticSearchRequest(
            query=args.query,
            limit=args.limit,
            filters=SearchFilters(
                source_sha256=args.source_sha256,
                source_role=args.source_role,
                document_class=args.document_class,
                authority=args.authority,
                vehicle_generation=args.vehicle_generation,
                championship=args.championship,
                season=args.season,
                revision=args.revision,
                page_number=args.page,
                chunk_kind=args.chunk_kind,
                oversize=args.oversize,
            ),
            model_id=embedder.spec.model_id,
            model_revision=embedder.spec.model_revision,
        ),
        embedder=embedder,
        store=store,
    )
    _emit(f"Matches: {len(response.hits)}")
    for rank, hit in enumerate(response.hits, start=1):
        location = f"pages {hit.page_start}-{hit.page_end}"
        if hit.page_start == hit.page_end:
            location = f"page {hit.page_start}"
        _emit(f"{rank}. score={hit.score:.4f} {hit.source_filename} ({location})")
        if hit.section_path:
            _emit(f"   Section: {' > '.join(hit.section_path)}")
        if hit.clause_reference:
            _emit(f"   Clause: {hit.clause_reference}")
        _emit(f"   {' '.join(hit.evidence_text.split())[:240]}")
        _emit(f"   Chunk: {hit.chunk_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    store = SemanticStore(settings.psycopg_conninfo)
    try:
        if args.command == "count":
            spec = EmbeddingModelSpec(
                model_id=str(args.model_id),
                model_revision=str(args.model_revision),
            )
            print(store.count(spec))
            return 0
        if args.command == "embed":
            embedder = _embedder(args)
            result = index_chunk_artifact(
                args.artifact, embedder=embedder, store=store
            )
            print(f"Source SHA-256: {result.source_sha256}")
            print(f"Chunks: {result.total_chunks}")
            print(f"Generated embeddings: {result.generated_embeddings}")
            print(f"Reused embeddings: {result.reused_embeddings}")
            print(f"Removed stale chunks: {result.removed_stale_chunks}")
            return 0
        return _search(args, store)
    except (FileNotFoundError, RuntimeError, ValueError, psycopg.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
