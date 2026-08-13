"""Factories for fusion tests."""

from __future__ import annotations

from racevault.lexical.documents import build_index_document
from racevault.lexical.models import LexicalSearchHit
from racevault.semantic.models import (
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_REVISION,
    SemanticSearchHit,
)
from tests.lexical.factories import chunking_artifact


def lexical_hit(
    number: int,
    *,
    score: float = 1.0,
    text: str | None = None,
) -> LexicalSearchHit:
    artifact = chunking_artifact()
    document = build_index_document(artifact, artifact.chunks[0])
    document["chunk_id"] = f"chk_{number:032x}"
    if text is not None:
        document["evidence_text"] = text
        document["contextual_text"] = text
    fields = LexicalSearchHit.model_fields
    values = {name: value for name, value in document.items() if name in fields}
    values["score"] = score
    values["highlights"] = []
    return LexicalSearchHit.model_validate(values)


def semantic_hit(hit: LexicalSearchHit, *, score: float = 0.5) -> SemanticSearchHit:
    fields = SemanticSearchHit.model_fields
    values = {name: value for name, value in hit.model_dump().items() if name in fields}
    values.update(
        score=score,
        model_id=DEFAULT_MODEL_ID,
        model_revision=DEFAULT_MODEL_REVISION,
    )
    return SemanticSearchHit.model_validate(values)
