"""Classification and chunk artifact pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from racevault import __version__
from racevault.chunking.classifier import classify_document
from racevault.chunking.models import (
    ChunkingArtifact,
    ChunkingProvenance,
    ChunkingSettings,
    ChunkingStatistics,
)
from racevault.chunking.strategy import build_chunks, eligible_elements
from racevault.extraction.io import (
    canonical_json_bytes,
    load_json,
    sha256_file,
    write_json_atomic,
)
from racevault.extraction.models import ExtractionArtifact


@dataclass(frozen=True)
class ChunkingOptions:
    max_characters: int = 2400
    include_section_context: bool = True
    force: bool = False


@dataclass(frozen=True)
class ChunkingResult:
    artifact: ChunkingArtifact
    artifact_path: Path
    reused: bool


def chunk_extraction(
    *,
    extraction_path: Path,
    output_root: Path,
    options: ChunkingOptions | None = None,
) -> ChunkingResult:
    configured = options or ChunkingOptions()
    extraction = ExtractionArtifact.model_validate(load_json(extraction_path))
    extraction_sha256 = sha256_file(extraction_path)
    classification = classify_document(extraction)
    settings = ChunkingSettings(
        max_characters=configured.max_characters,
        include_section_context=configured.include_section_context,
    )
    configuration_id = hashlib.sha256(canonical_json_bytes(settings)).hexdigest()[:12]
    output_directory = (
        output_root.resolve()
        / extraction.source.sha256
        / extraction_sha256
        / configuration_id
    )
    artifact_path = output_directory / "chunks.json"

    if artifact_path.is_file() and not configured.force:
        artifact = validate_chunking_artifact(
            artifact_path, extraction_path=extraction_path
        )
        return ChunkingResult(
            artifact=artifact, artifact_path=artifact_path, reused=True
        )

    chunks = build_chunks(extraction, classification, settings)
    eligible_ids = {element.element_id for element in eligible_elements(extraction)}
    chunked_ids = {element_id for chunk in chunks for element_id in chunk.element_ids}
    if chunked_ids != eligible_ids:
        missing = sorted(eligible_ids - chunked_ids)
        extra = sorted(chunked_ids - eligible_ids)
        raise ValueError(
            f"chunk element coverage mismatch; missing={missing}, extra={extra}"
        )

    artifact = ChunkingArtifact(
        source=extraction.source,
        classification=classification,
        provenance=ChunkingProvenance(
            pipeline="racevault.document_chunking",
            pipeline_version=__version__,
            extraction_file=extraction_path.name,
            extraction_sha256=extraction_sha256,
            settings=settings,
        ),
        chunks=chunks,
        statistics=ChunkingStatistics(
            chunks=len(chunks),
            table_chunks=sum(chunk.kind.value == "table" for chunk in chunks),
            oversize_chunks=sum(chunk.oversize for chunk in chunks),
            evidence_characters=sum(len(chunk.evidence_text) for chunk in chunks),
        ),
    )
    write_json_atomic(artifact_path, artifact)
    return ChunkingResult(artifact=artifact, artifact_path=artifact_path, reused=False)


def validate_chunking_artifact(
    artifact_path: Path, extraction_path: Path | None = None
) -> ChunkingArtifact:
    artifact = ChunkingArtifact.model_validate(load_json(artifact_path))
    if extraction_path is not None:
        if sha256_file(extraction_path) != artifact.provenance.extraction_sha256:
            raise ValueError("extraction hash does not match the chunk artifact")
        extraction = ExtractionArtifact.model_validate(load_json(extraction_path))
        if extraction.source.sha256 != artifact.source.sha256:
            raise ValueError("source hash does not match the extraction artifact")
        eligible_ids = {element.element_id for element in eligible_elements(extraction)}
        chunked_ids = {
            element_id for chunk in artifact.chunks for element_id in chunk.element_ids
        }
        if chunked_ids != eligible_ids:
            raise ValueError(
                "chunk artifact does not cover eligible extraction elements"
            )
    return artifact
