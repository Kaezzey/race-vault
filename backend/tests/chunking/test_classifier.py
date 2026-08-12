from __future__ import annotations

from racevault.chunking.classifier import classify_document
from racevault.chunking.models import ChunkStrategy, DocumentClass
from tests.chunking.factories import extraction_artifact


def test_declared_document_type_takes_precedence() -> None:
    artifact = extraction_artifact(
        (), document_type="regulation", relative_path="ECU/manual.pdf"
    )

    result = classify_document(artifact)

    assert result.document_class is DocumentClass.REGULATION
    assert result.strategy is ChunkStrategy.CLAUSE
    assert result.method == "declared_metadata"


def test_path_rule_classifies_missing_metadata() -> None:
    artifact = extraction_artifact(
        (), document_type=None, relative_path="Tyre Data/992.1/book.pdf"
    )

    result = classify_document(artifact)

    assert result.document_class is DocumentClass.TYRE_DATA
    assert result.strategy is ChunkStrategy.PAGE_TABLE


def test_large_unclassified_document_uses_hierarchical_passages() -> None:
    artifact = extraction_artifact(
        (),
        document_type=None,
        relative_path="Other/reference.pdf",
        page_count=300,
    )

    result = classify_document(artifact)

    assert result.document_class is DocumentClass.ENGINEERING_REFERENCE
    assert result.strategy is ChunkStrategy.HIERARCHICAL_PASSAGE
    assert result.method == "page_count_rule"

