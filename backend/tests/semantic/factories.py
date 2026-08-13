"""Fakes for semantic pipeline tests."""

from __future__ import annotations

from collections.abc import Sequence

from racevault.semantic.models import (
    DenseVector,
    EmbeddingModelSpec,
    SemanticIndexingResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
)


def unit_vector(position: int = 0) -> DenseVector:
    values = [0.0] * 1024
    values[position] = 1.0
    return DenseVector(values=tuple(values))


class FakeEmbedder:
    def __init__(self) -> None:
        self.spec = EmbeddingModelSpec()
        self.inputs: list[str] = []

    def encode(self, texts: Sequence[str]) -> tuple[DenseVector, ...]:
        self.inputs.extend(texts)
        return tuple(unit_vector() for _ in texts)


class FakeStore:
    def __init__(self, existing: dict[str, str] | None = None) -> None:
        self.existing = existing or {}
        self.saved = ()
        self.query_vector: Sequence[float] | None = None

    def existing_inputs(
        self, chunk_ids: Sequence[str], spec: EmbeddingModelSpec
    ) -> dict[str, str]:
        del chunk_ids, spec
        return self.existing

    def ingest(self, artifact, embeddings, spec):
        del spec
        self.saved = tuple(embeddings)
        return SemanticIndexingResult(
            source_sha256=artifact.source.sha256,
            artifact_id="d" * 64,
            total_chunks=len(artifact.chunks),
            generated_embeddings=len(embeddings),
            reused_embeddings=len(artifact.chunks) - len(embeddings),
            removed_stale_chunks=0,
        )

    def search(
        self, request: SemanticSearchRequest, query_vector: Sequence[float]
    ) -> SemanticSearchResponse:
        self.query_vector = query_vector
        return SemanticSearchResponse(query=request.query, hits=())
