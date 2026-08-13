"""Factories for lexical retrieval tests."""

from __future__ import annotations

from racevault.chunking.classifier import classify_document
from racevault.chunking.models import (
    ChunkingArtifact,
    ChunkingProvenance,
    ChunkingSettings,
    ChunkingStatistics,
)
from racevault.chunking.strategy import build_chunks
from tests.chunking.factories import element, extraction_artifact


def chunking_artifact() -> ChunkingArtifact:
    extraction = extraction_artifact(
        (
            element(
                1,
                "ABS M5 brake pressure requirement.",
                page=2,
                section_path=("Brakes", "Pressure"),
            ),
        ),
        document_type="technical_manual",
    )
    source = extraction.source.model_copy(
        update={
            "role": "technical_manual_current_generation",
            "metadata": {
                "document_type": "technical_manual",
                "vehicle_generation": "992.2",
                "season": 2026,
                "revision": "Version 2",
                "authority": "manufacturer_document",
            },
        }
    )
    extraction = extraction.model_copy(update={"source": source})
    classification = classify_document(extraction)
    settings = ChunkingSettings()
    chunks = build_chunks(extraction, classification, settings)
    return ChunkingArtifact(
        source=source,
        classification=classification,
        provenance=ChunkingProvenance(
            pipeline="test",
            pipeline_version="1",
            extraction_file="extraction.json",
            extraction_sha256="c" * 64,
            settings=settings,
        ),
        chunks=chunks,
        statistics=ChunkingStatistics(
            chunks=len(chunks),
            table_chunks=0,
            oversize_chunks=0,
            evidence_characters=sum(len(chunk.evidence_text) for chunk in chunks),
        ),
    )
