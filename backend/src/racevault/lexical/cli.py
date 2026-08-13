"""Command-line interface for OpenSearch lexical retrieval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from racevault.chunking.models import ChunkingArtifact
from racevault.config import get_settings
from racevault.extraction.io import load_json
from racevault.lexical.client import OpenSearchClient, OpenSearchError
from racevault.lexical.models import LexicalSearchRequest, SearchFilters


def _add_connection_options(parser: argparse.ArgumentParser) -> None:
    settings = get_settings()
    parser.add_argument("--url", default=settings.opensearch_url)
    parser.add_argument("--index", default=settings.opensearch_index_name)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="racevault-lexical",
        description="Index and search RaceVault chunks with OpenSearch BM25.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure = subparsers.add_parser("ensure-index", help="Create or validate the index.")
    _add_connection_options(ensure)

    index = subparsers.add_parser("index", help="Index one chunks.json artifact.")
    index.add_argument("artifact", type=Path)
    _add_connection_options(index)

    search = subparsers.add_parser("search", help="Run a filtered BM25 query.")
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
    _add_connection_options(search)

    count = subparsers.add_parser("count", help="Count indexed chunks.")
    count.add_argument("--source-sha256")
    _add_connection_options(count)
    return parser


def _client(args: argparse.Namespace) -> OpenSearchClient:
    settings = get_settings()
    return OpenSearchClient(
        base_url=str(args.url),
        index_name=str(args.index),
        timeout_seconds=settings.opensearch_timeout_seconds,
    )


def _emit(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(value.encode(encoding, errors="replace").decode(encoding))


def _search(args: argparse.Namespace, client: OpenSearchClient) -> int:
    response = client.search(
        LexicalSearchRequest(
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
        )
    )
    _emit(f"Matches: {response.total}")
    for rank, hit in enumerate(response.hits, start=1):
        location = f"pages {hit.page_start}-{hit.page_end}"
        if hit.page_start == hit.page_end:
            location = f"page {hit.page_start}"
        _emit(f"{rank}. score={hit.score:.4f} {hit.source_filename} ({location})")
        if hit.section_path:
            _emit(f"   Section: {' > '.join(hit.section_path)}")
        if hit.clause_reference:
            _emit(f"   Clause: {hit.clause_reference}")
        preview = " ".join(hit.evidence_text.split())[:240]
        _emit(f"   {preview}")
        _emit(f"   Chunk: {hit.chunk_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with _client(args) as client:
            if args.command == "ensure-index":
                created = client.ensure_index()
                print(f"{'Created' if created else 'Valid'}: {client.index_name}")
                return 0
            if args.command == "index":
                artifact = ChunkingArtifact.model_validate(load_json(args.artifact))
                result = client.index_artifact(artifact)
                print(f"Index: {result.index_name}")
                print(f"Indexed chunks: {result.indexed_chunks}")
                print(f"Replaced chunks: {result.removed_chunks}")
                return 0
            if args.command == "count":
                print(client.count(source_sha256=args.source_sha256))
                return 0
            return _search(args, client)
    except (FileNotFoundError, OpenSearchError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
