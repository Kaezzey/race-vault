"""Embedding generation and semantic retrieval orchestration."""

from __future__ import annotations

from pathlib import Path

from racevault.chunking.models import ChunkingArtifact
from racevault.extraction.io import load_json
from racevault.semantic.embedder import DenseEmbedder
from racevault.semantic.models import (
    EmbeddedChunk,
    SemanticIndexingResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from racevault.semantic.store import SemanticStore


def index_chunk_artifact(
    artifact_path: Path,
    *,
    embedder: DenseEmbedder,
    store: SemanticStore,
) -> SemanticIndexingResult:
    artifact = ChunkingArtifact.model_validate(load_json(artifact_path))
    chunk_ids = [chunk.chunk_id for chunk in artifact.chunks]
    existing = store.existing_inputs(chunk_ids, embedder.spec)
    missing = [
        chunk
        for chunk in artifact.chunks
        if existing.get(chunk.chunk_id) != chunk.contextual_sha256
    ]
    vectors = embedder.encode([chunk.contextual_text for chunk in missing])
    if len(vectors) != len(missing):
        raise RuntimeError("embedder returned an unexpected vector count")
    embedded = tuple(
        EmbeddedChunk(
            chunk_id=chunk.chunk_id,
            input_sha256=chunk.contextual_sha256,
            vector=vector,
        )
        for chunk, vector in zip(missing, vectors, strict=True)
    )
    return store.ingest(artifact, embedded, embedder.spec)


def semantic_search(
    request: SemanticSearchRequest,
    *,
    embedder: DenseEmbedder,
    store: SemanticStore,
) -> SemanticSearchResponse:
    if request.model_id != embedder.spec.model_id:
        raise ValueError("search model ID does not match the embedder")
    if request.model_revision != embedder.spec.model_revision:
        raise ValueError("search model revision does not match the embedder")
    vectors = embedder.encode((request.query,))
    if len(vectors) != 1:
        raise RuntimeError("embedder did not return one query vector")
    return store.search(request, vectors[0].values)
