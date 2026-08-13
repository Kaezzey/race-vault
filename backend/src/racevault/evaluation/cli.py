"""Command-line interface for labelled hybrid retrieval evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

from racevault.config import get_settings
from racevault.evaluation.runner import load_dataset, run_evaluation
from racevault.extraction.io import write_json_atomic
from racevault.fusion.models import RerankerSpec
from racevault.fusion.reranker import BgeReranker
from racevault.lexical.client import OpenSearchClient, OpenSearchError
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.store import SemanticStore


def _parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="racevault-evaluate",
        description="Measure each retrieval stage with labelled engineering queries.",
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("evaluation/queries.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path(".artifacts/evaluation/report.json")
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--embedding-batch-size", type=int, default=1)
    parser.add_argument(
        "--reranker-batch-size", type=int, default=settings.reranker_batch_size
    )
    parser.add_argument("--channel-limit", type=int, default=50)
    parser.add_argument("--fusion-limit", type=int, default=30)
    parser.add_argument("--rerank-limit", type=int, default=15)
    parser.add_argument("--minimum-hit-rate", type=float, default=0.8)
    parser.add_argument("--minimum-mrr", type=float, default=0.5)
    parser.add_argument("--local-files-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    try:
        embedder = BgeM3Embedder(
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
            spec=RerankerSpec(
                model_id=settings.reranker_model_id,
                model_revision=settings.reranker_model_revision,
                max_tokens=settings.reranker_max_tokens,
            ),
            device=args.device,
            batch_size=args.reranker_batch_size,
            local_files_only=args.local_files_only,
        )
        with OpenSearchClient(
            base_url=settings.opensearch_url,
            index_name=settings.opensearch_index_name,
            timeout_seconds=settings.opensearch_timeout_seconds,
        ) as lexical:
            report = run_evaluation(
                load_dataset(args.dataset),
                lexical=lexical,
                semantic_embedder=embedder,
                semantic_store=SemanticStore(settings.psycopg_conninfo),
                reranker=reranker,
                channel_limit=args.channel_limit,
                fusion_limit=args.fusion_limit,
                rerank_limit=args.rerank_limit,
            )
        write_json_atomic(args.output, report)
        print(
            "stage      hit-rate  MRR    negative-accuracy  passed\n"
            "---------- --------- ------ ------------------ ------"
        )
        for name in ("lexical", "semantic", "fused", "reranked"):
            summary = getattr(report, name)
            print(
                f"{name:<10} {summary.positive_hit_rate:>9.3f} "
                f"{summary.mean_reciprocal_rank:>6.3f} "
                f"{summary.negative_accuracy:>18.3f} "
                f"{summary.passed_queries:>6}"
            )
        print(f"Report: {args.output}")
        passed = (
            report.reranked.positive_hit_rate >= args.minimum_hit_rate
            and report.reranked.mean_reciprocal_rank >= args.minimum_mrr
            and report.reranked.negative_accuracy == 1.0
        )
        return 0 if passed else 1
    except (
        FileNotFoundError,
        OpenSearchError,
        RuntimeError,
        ValueError,
        psycopg.Error,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
