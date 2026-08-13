from __future__ import annotations

from racevault.lexical.documents import artifact_identity, build_index_document
from tests.lexical.factories import chunking_artifact


def test_index_document_preserves_evidence_provenance_and_filters() -> None:
    artifact = chunking_artifact()
    chunk = artifact.chunks[0]

    document = build_index_document(artifact, chunk)

    assert document["evidence_text"] == chunk.evidence_text
    assert document["contextual_text"] == chunk.contextual_text
    assert document["provenance"] == [
        item.model_dump(mode="json") for item in chunk.provenance
    ]
    assert document["vehicle_generation"] == "992.2"
    assert document["season"] == 2026
    assert document["revision"] == "Version 2"
    assert document["authority"] == "manufacturer_document"
    assert document["artifact_id"] == artifact_identity(artifact)
