"""Run labelled queries through every hybrid retrieval stage."""

from __future__ import annotations

import importlib
import math
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from racevault.evaluation.metrics import (
    evaluate_stage,
    paired_bootstrap_comparison,
    summarize,
)
from racevault.evaluation.models import (
    EvaluationDataset,
    EvaluationReport,
    ExperimentFingerprint,
    QueryEvaluationResult,
    ResourceMeasurements,
    StageSummary,
)
from racevault.extraction.io import load_json
from racevault.fusion.models import HybridSearchRequest, RerankerSpec, RrfSettings
from racevault.fusion.pipeline import LexicalSearcher, hybrid_search_stages
from racevault.fusion.reranker import CandidateReranker
from racevault.retrieval.models import SearchFilters
from racevault.semantic.embedder import DenseEmbedder
from racevault.semantic.store import SemanticStore


def load_dataset(path: Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate(load_json(path))


def _reset_gpu_peak() -> object | None:
    try:
        torch = importlib.import_module("torch")
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            return torch
    except (ImportError, RuntimeError):
        pass
    return None


def _peak_gpu_memory_mb(torch: object | None) -> float | None:
    if torch is None:
        return None
    try:
        return float(torch.cuda.max_memory_allocated()) / (1024 * 1024)  # type: ignore[attr-defined]
    except RuntimeError:
        return None


def _peak_rss_mb() -> float | None:
    try:
        resource = importlib.import_module("resource")
    except ImportError:
        return None
    maximum = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    divisor = 1024 * 1024 if platform.system() == "Darwin" else 1024
    return maximum / divisor


def run_evaluation(
    dataset: EvaluationDataset,
    *,
    lexical: LexicalSearcher,
    semantic_embedder: DenseEmbedder,
    semantic_store: SemanticStore,
    reranker: CandidateReranker,
    channel_limit: int = 50,
    fusion_limit: int = 30,
    rerank_limit: int = 15,
    split: Literal["all", "development", "test"] = "all",
    bootstrap_samples: int = 1000,
    random_seed: int = 17,
    experiment: ExperimentFingerprint | None = None,
    use_metadata_filters: bool = True,
    rrf: RrfSettings | None = None,
    ablation_label: str = "hybrid_reranked",
    index_size_gb: float | None = None,
) -> EvaluationReport:
    torch = _reset_gpu_peak()
    started = time.perf_counter()
    results = []
    queries = tuple(
        query
        for query in dataset.queries
        if split == "all" or query.split == split
    )
    if not queries:
        raise ValueError(f"evaluation split contains no queries: {split}")
    for query in queries:
        query_started = time.perf_counter()
        stages = hybrid_search_stages(
            HybridSearchRequest(
                query=query.query,
                filters=query.filters if use_metadata_filters else SearchFilters(),
                channel_limit=channel_limit,
                fusion_limit=fusion_limit,
                rerank_limit=rerank_limit,
                result_limit=rerank_limit,
                embedding_model_id=semantic_embedder.spec.model_id,
                embedding_model_revision=semantic_embedder.spec.model_revision,
                reranker=RerankerSpec.model_validate(reranker.spec),
                rrf=rrf or RrfSettings(),
            ),
            lexical=lexical,
            semantic_embedder=semantic_embedder,
            semantic_store=semantic_store,
            reranker=reranker,
        )
        results.append(
            QueryEvaluationResult(
                query_id=query.query_id,
                category=query.category,
                expected_empty=query.expected_empty,
                split=query.split,
                slices=tuple(dict.fromkeys((query.category, *query.slices))),
                elapsed_ms=(time.perf_counter() - query_started) * 1000,
                lexical=evaluate_stage(stages.lexical.hits, query),
                semantic=evaluate_stage(stages.semantic.hits, query),
                fused=evaluate_stage(stages.fused, query),
                reranked=evaluate_stage(stages.reranked, query),
            )
        )

    stage_names = ("lexical", "semantic", "fused", "reranked")

    def stage_summary(name: str) -> StageSummary:
        return summarize(
            queries,
            [getattr(item, name) for item in results],
            bootstrap_samples=bootstrap_samples,
            random_seed=random_seed,
        )

    slice_names = sorted(
        {slice_name for item in results for slice_name in item.slices}
    )
    slices = {}
    for slice_name in slice_names:
        selected = [
            (query, result)
            for query, result in zip(queries, results, strict=True)
            if slice_name in result.slices
        ]
        slice_queries = [item[0] for item in selected]
        slice_results = [item[1] for item in selected]
        slices[slice_name] = {
            stage_name: summarize(
                slice_queries,
                [getattr(item, stage_name) for item in slice_results],
                bootstrap_samples=bootstrap_samples,
                random_seed=random_seed,
            )
            for stage_name in stage_names
        }

    elapsed_ms = (time.perf_counter() - started) * 1000
    query_latencies = [item.elapsed_ms for item in results]
    warm_latencies = sorted(query_latencies[1:])

    def percentile(values: list[float], probability: float) -> float | None:
        if not values:
            return None
        position = math.ceil(probability * len(values)) - 1
        return values[max(0, min(position, len(values) - 1))]
    return EvaluationReport(
        created_at=datetime.now(UTC),
        query_count=len(queries),
        positive_queries=sum(not item.expected_empty for item in queries),
        negative_queries=sum(item.expected_empty for item in queries),
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        split=split,
        ablation_label=ablation_label,
        experiment=experiment,
        resources=ResourceMeasurements(
            elapsed_ms=elapsed_ms,
            queries_per_second=(len(queries) / (elapsed_ms / 1000)),
            peak_rss_mb=_peak_rss_mb(),
            peak_gpu_memory_mb=_peak_gpu_memory_mb(torch),
            cold_query_ms=query_latencies[0] if query_latencies else None,
            warm_query_p50_ms=percentile(warm_latencies, 0.5),
            warm_query_p95_ms=percentile(warm_latencies, 0.95),
            index_size_gb=index_size_gb,
        ),
        lexical=stage_summary("lexical"),
        semantic=stage_summary("semantic"),
        fused=stage_summary("fused"),
        reranked=stage_summary("reranked"),
        slices=slices,
        comparisons=(
            paired_bootstrap_comparison(
                queries,
                [item.reranked for item in results],
                [item.fused for item in results],
                left_stage="reranked",
                right_stage="fused",
                samples=bootstrap_samples,
                seed=random_seed,
            ),
            paired_bootstrap_comparison(
                queries,
                [item.fused for item in results],
                [item.lexical for item in results],
                left_stage="fused",
                right_stage="lexical",
                samples=bootstrap_samples,
                seed=random_seed + 1,
            ),
        ),
        results=tuple(results),
    )
