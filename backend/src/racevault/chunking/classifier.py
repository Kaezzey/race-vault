"""Deterministic document classification rules."""

from __future__ import annotations

from racevault.chunking.models import (
    ChunkStrategy,
    ClassificationArtifact,
    DocumentClass,
)
from racevault.extraction.models import ExtractionArtifact

STRATEGIES: dict[DocumentClass, ChunkStrategy] = {
    DocumentClass.REGULATION: ChunkStrategy.CLAUSE,
    DocumentClass.TECHNICAL_MANUAL: ChunkStrategy.SECTION_EVIDENCE,
    DocumentClass.TYRE_DATA: ChunkStrategy.PAGE_TABLE,
    DocumentClass.PART_CATALOGUE: ChunkStrategy.PAGE_TABLE,
    DocumentClass.COMPONENT_MANUAL: ChunkStrategy.SECTION_EVIDENCE,
    DocumentClass.ENGINEERING_REFERENCE: ChunkStrategy.HIERARCHICAL_PASSAGE,
    DocumentClass.UNKNOWN: ChunkStrategy.GENERIC_EVIDENCE,
}

PATH_RULES: tuple[tuple[str, DocumentClass], ...] = (
    ("rules and regulations/", DocumentClass.REGULATION),
    ("porsche technical manuals/", DocumentClass.TECHNICAL_MANUAL),
    ("tyre data/", DocumentClass.TYRE_DATA),
    ("part catalogues/", DocumentClass.PART_CATALOGUE),
    ("abs/", DocumentClass.COMPONENT_MANUAL),
    ("cosworth/", DocumentClass.COMPONENT_MANUAL),
    ("ecu/", DocumentClass.COMPONENT_MANUAL),
    ("pmrsi other/", DocumentClass.COMPONENT_MANUAL),
)


def _result(
    document_class: DocumentClass, method: str, rule: str
) -> ClassificationArtifact:
    return ClassificationArtifact(
        document_class=document_class,
        strategy=STRATEGIES[document_class],
        method=method,
        rule=rule,
    )


def classify_document(artifact: ExtractionArtifact) -> ClassificationArtifact:
    declared = artifact.source.metadata.get("document_type")
    if isinstance(declared, str):
        try:
            document_class = DocumentClass(declared)
        except ValueError:
            pass
        else:
            return _result(
                document_class,
                "declared_metadata",
                "source.metadata.document_type",
            )

    path = artifact.source.relative_path.lower().replace("\\", "/")
    for prefix, document_class in PATH_RULES:
        if path.startswith(prefix):
            return _result(document_class, "path_rule", prefix)

    if artifact.source.page_count >= 300:
        return _result(
            DocumentClass.ENGINEERING_REFERENCE,
            "page_count_rule",
            "page_count >= 300",
        )

    return _result(DocumentClass.UNKNOWN, "fallback", "no matching rule")

