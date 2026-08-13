"""Command-line interface for hybrid retrieval and reranking."""

from __future__ import annotations

import argparse
import sys

import psycopg

from racevault.config import get_settings
from racevault.fusion.models import HybridSearchRequest, RerankerSpec, RrfSettings
from racevault.fusion.pipeline import hybrid_search
from racevault.fusion.reranker import BgeReranker
from racevault.lexical.client import OpenSearchClient, OpenSearchError
from racevault.retrieval.models import SearchFilters
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.store import SemanticStore


def _parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="racevault-retrieve",
        description="Run BM25 and semantic retrieval, RRF, and BGE reranking.",
    )
    parser.add_argument("query")
    parser.add_argument("--channel-limit", type=int, default=50)
    parser.add_argument("--fusion-limit", type=int, default=30)
    parser.add_argument("--rerank-limit", type=int, default=15)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--source-sha256")
    parser.add_argument("--source-role")
    parser.add_argument("--document-class")
    parser.add_argument("--authority")
    parser.add_argument("--vehicle-generation")
    parser.add_argument("--championship")
    parser.add_argument("--season", type=int)
    parser.add_argument("--revision")
    parser.add_argument("--page", type=int)
    parser.add_argument("--chunk-kind")
    parser.add_argument("--oversize", action=argparse.BooleanOptionalAction)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--embedding-batch-size", type=int, default=1)
    parser.add_argument(
        "--reranker-batch-size", type=int, default=settings.reranker_batch_size
    )
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--opensearch-url", default=settings.opensearch_url)
    parser.add_argument("--opensearch-index", default=settings.opensearch_index_name)
    return parser


def _emit(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(value.encode(encoding, errors="replace").decode(encoding))


def _request(args: argparse.Namespace, reranker: RerankerSpec) -> HybridSearchRequest:
    settings = get_settings()
    return HybridSearchRequest(
        query=args.query,
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
        channel_limit=args.channel_limit,
        fusion_limit=args.fusion_limit,
        rerank_limit=args.rerank_limit,
        result_limit=args.limit,
        rrf=RrfSettings(rank_constant=args.rrf_k),
        embedding_model_id=settings.semantic_model_id,
        embedding_model_revision=settings.semantic_model_revision,
        reranker=reranker,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    reranker_spec = RerankerSpec(
        model_id=settings.reranker_model_id,
        model_revision=settings.reranker_model_revision,
        max_tokens=settings.reranker_max_tokens,
    )
    try:
        semantic_embedder = BgeM3Embedder(
            spec=EmbeddingModelSpec(
                model_id=settings.semantic_model_id,
                model_revision=settings.semantic_model_revision,
                max_tokens=settings.semantic_max_tokens,
            ),
            device=args.device,
            batch_size=args.embedding_batch_size,
            local_files_only=args.local_files_only,
        )
        reranker = BgeReranker(
            spec=reranker_spec,
            device=args.device,
            batch_size=args.reranker_batch_size,
            local_files_only=args.local_files_only,
        )
        with OpenSearchClient(
            base_url=args.opensearch_url,
            index_name=args.opensearch_index,
            timeout_seconds=settings.opensearch_timeout_seconds,
        ) as lexical:
            response = hybrid_search(
                _request(args, reranker_spec),
                lexical=lexical,
                semantic_embedder=semantic_embedder,
                semantic_store=SemanticStore(settings.psycopg_conninfo),
                reranker=reranker,
            )
        _emit(
            f"Candidates: lexical={response.lexical_hits}, "
            f"semantic={response.semantic_hits}, fused={response.fused_candidates}, "
            f"reranked={response.reranked_candidates}"
        )
        for result in response.results:
            reranker_score = result.reranker_score
            if reranker_score is None:
                raise RuntimeError("reranked result is missing a reranker score")
            location = f"pages {result.page_start}-{result.page_end}"
            if result.page_start == result.page_end:
                location = f"page {result.page_start}"
            _emit(
                f"{result.final_rank}. reranker={reranker_score:.4f} "
                f"rrf={result.rrf_score:.6f} {result.source_filename} ({location})"
            )
            _emit(
                f"   Channels: BM25={result.lexical_rank or '-'}, "
                f"semantic={result.semantic_rank or '-'}, fused={result.fused_rank}"
            )
            if result.section_path:
                _emit(f"   Section: {' > '.join(result.section_path)}")
            if result.clause_reference:
                _emit(f"   Clause: {result.clause_reference}")
            _emit(f"   {' '.join(result.evidence_text.split())[:240]}")
            _emit(f"   Chunk: {result.chunk_id}")
        return 0
    except (OpenSearchError, RuntimeError, ValueError, psycopg.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
