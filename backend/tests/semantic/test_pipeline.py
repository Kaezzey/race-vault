from __future__ import annotations

from pathlib import Path

from racevault.extraction.io import write_json_atomic
from racevault.semantic.models import SemanticSearchRequest
from racevault.semantic.pipeline import index_chunk_artifact, semantic_search
from tests.lexical.factories import chunking_artifact
from tests.semantic.factories import FakeEmbedder, FakeStore


def test_index_pipeline_embeds_contextual_text_and_saves_input_hash(
    tmp_path: Path,
) -> None:
    artifact = chunking_artifact()
    path = tmp_path / "chunks.json"
    write_json_atomic(path, artifact)
    embedder = FakeEmbedder()
    store = FakeStore()

    result = index_chunk_artifact(
        path, embedder=embedder, store=store  # type: ignore[arg-type]
    )

    assert embedder.inputs == [artifact.chunks[0].contextual_text]
    assert store.saved[0].input_sha256 == artifact.chunks[0].contextual_sha256
    assert result.generated_embeddings == 1


def test_index_pipeline_reuses_matching_embedding(tmp_path: Path) -> None:
    artifact = chunking_artifact()
    path = tmp_path / "chunks.json"
    write_json_atomic(path, artifact)
    chunk = artifact.chunks[0]
    embedder = FakeEmbedder()
    store = FakeStore(existing={chunk.chunk_id: chunk.contextual_sha256})

    result = index_chunk_artifact(
        path, embedder=embedder, store=store  # type: ignore[arg-type]
    )

    assert embedder.inputs == []
    assert result.generated_embeddings == 0
    assert result.reused_embeddings == 1


def test_semantic_search_embeds_one_query() -> None:
    embedder = FakeEmbedder()
    store = FakeStore()
    request = SemanticSearchRequest(query="How is brake balance adjusted?")

    response = semantic_search(
        request,
        embedder=embedder,
        store=store,  # type: ignore[arg-type]
    )

    assert response.query == request.query
    assert embedder.inputs == [request.query]
    assert store.query_vector is not None
    assert len(store.query_vector) == 1024
