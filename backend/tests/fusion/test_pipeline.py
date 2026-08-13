from __future__ import annotations

from collections.abc import Sequence

from racevault.fusion.models import HybridSearchRequest, RerankerSpec
from racevault.fusion.pipeline import hybrid_search
from racevault.lexical.models import LexicalSearchRequest, LexicalSearchResponse
from racevault.semantic.models import (
    DenseVector,
    EmbeddingModelSpec,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from tests.fusion.factories import lexical_hit, semantic_hit
from tests.semantic.factories import unit_vector


class FakeLexical:
    def __init__(self, response: LexicalSearchResponse) -> None:
        self.response = response

    def search(self, request: LexicalSearchRequest) -> LexicalSearchResponse:
        assert request.limit == 10
        return self.response


class FakeEmbedder:
    spec = EmbeddingModelSpec()

    def encode(self, texts: Sequence[str]) -> tuple[DenseVector, ...]:
        return tuple(unit_vector() for _ in texts)


class FakeStore:
    def __init__(self, response: SemanticSearchResponse) -> None:
        self.response = response

    def search(
        self, request: SemanticSearchRequest, query_vector: Sequence[float]
    ) -> SemanticSearchResponse:
        assert request.limit == 10
        assert len(query_vector) == 1024
        return self.response


class FakeReranker:
    spec = RerankerSpec()

    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]:
        del query
        return tuple(0.9 - index * 0.1 for index in range(len(passages)))


def test_hybrid_pipeline_reports_each_stage() -> None:
    lexical = lexical_hit(1)
    semantic = semantic_hit(lexical)
    request = HybridSearchRequest(
        query="brake balance",
        channel_limit=10,
        fusion_limit=5,
        rerank_limit=5,
        result_limit=3,
    )

    lexical_response = LexicalSearchResponse(
        query=request.query,
        total=1,
        hits=(lexical,),
    )
    semantic_response = SemanticSearchResponse(
        query=request.query,
        hits=(semantic,),
    )
    response = hybrid_search(
        request,
        lexical=FakeLexical(lexical_response),
        semantic_embedder=FakeEmbedder(),
        semantic_store=FakeStore(semantic_response),  # type: ignore[arg-type]
        reranker=FakeReranker(),
    )

    assert response.lexical_hits == 1
    assert response.semantic_hits == 1
    assert response.fused_candidates == 1
    assert response.reranked_candidates == 1
    assert response.results[0].lexical_rank == 1
    assert response.results[0].semantic_rank == 1
