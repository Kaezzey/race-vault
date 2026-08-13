"""Run labelled queries through every hybrid retrieval stage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from racevault.evaluation.metrics import evaluate_stage, summarize
from racevault.evaluation.models import (
    EvaluationDataset,
    EvaluationReport,
    QueryEvaluationResult,
)
from racevault.extraction.io import load_json
from racevault.fusion.models import HybridSearchRequest, RerankerSpec
from racevault.fusion.pipeline import LexicalSearcher, hybrid_search_stages
from racevault.fusion.reranker import CandidateReranker
from racevault.semantic.embedder import DenseEmbedder
from racevault.semantic.store import SemanticStore


def load_dataset(path: Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate(load_json(path))


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
) -> EvaluationReport:
    results = []
    for query in dataset.queries:
        stages = hybrid_search_stages(
            HybridSearchRequest(
                query=query.query,
                filters=query.filters,
                channel_limit=channel_limit,
                fusion_limit=fusion_limit,
                rerank_limit=rerank_limit,
                result_limit=rerank_limit,
                embedding_model_id=semantic_embedder.spec.model_id,
                embedding_model_revision=semantic_embedder.spec.model_revision,
                reranker=RerankerSpec.model_validate(reranker.spec),
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
                lexical=evaluate_stage(stages.lexical.hits, query),
                semantic=evaluate_stage(stages.semantic.hits, query),
                fused=evaluate_stage(stages.fused, query),
                reranked=evaluate_stage(stages.reranked, query),
            )
        )

    queries = dataset.queries
    return EvaluationReport(
        created_at=datetime.now(UTC),
        query_count=len(queries),
        positive_queries=sum(not item.expected_empty for item in queries),
        negative_queries=sum(item.expected_empty for item in queries),
        lexical=summarize(queries, [item.lexical for item in results]),
        semantic=summarize(queries, [item.semantic for item in results]),
        fused=summarize(queries, [item.fused for item in results]),
        reranked=summarize(queries, [item.reranked for item in results]),
        results=tuple(results),
    )
