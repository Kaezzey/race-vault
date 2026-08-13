"""Resumable full-corpus extraction, chunking, and indexing."""

from __future__ import annotations

import enum
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from racevault.chunking.pipeline import ChunkingOptions, chunk_extraction
from racevault.corpus.models import CorpusDocument, CorpusManifest
from racevault.extraction.models import ArtifactModel
from racevault.extraction.pipeline import ExtractionOptions, extract_document
from racevault.lexical.client import OpenSearchClient
from racevault.semantic.embedder import DenseEmbedder
from racevault.semantic.pipeline import index_chunk_artifact
from racevault.semantic.store import SemanticStore


class IngestionStage(enum.StrEnum):
    EXTRACT = "extract"
    CHUNK = "chunk"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"


STAGE_ORDER = {
    IngestionStage.EXTRACT: 1,
    IngestionStage.CHUNK: 2,
    IngestionStage.LEXICAL: 3,
    IngestionStage.SEMANTIC: 4,
}


class DocumentIngestionResult(ArtifactModel):
    role: str
    path: str
    status: str
    completed_stage: IngestionStage | None = None
    extraction_reused: bool = False
    chunking_reused: bool = False
    chunks: int = Field(default=0, ge=0)
    generated_embeddings: int = Field(default=0, ge=0)
    reused_embeddings: int = Field(default=0, ge=0)
    error: str | None = None


class IngestionReport(ArtifactModel):
    schema_name: str = "racevault.corpus_ingestion"
    schema_version: int = 1
    started_at: datetime
    updated_at: datetime
    requested_stage: IngestionStage
    manifest_documents: int = Field(ge=1)
    selected_documents: int = Field(ge=1)
    completed_documents: int = Field(ge=0)
    failed_documents: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    generated_embeddings: int = Field(ge=0)
    reused_embeddings: int = Field(ge=0)
    documents: tuple[DocumentIngestionResult, ...]


ProgressCallback = Callable[[IngestionReport], None]


def _report(
    *,
    started_at: datetime,
    stage: IngestionStage,
    manifest_count: int,
    selected_count: int,
    results: list[DocumentIngestionResult],
) -> IngestionReport:
    return IngestionReport(
        started_at=started_at,
        updated_at=datetime.now(UTC),
        requested_stage=stage,
        manifest_documents=manifest_count,
        selected_documents=selected_count,
        completed_documents=sum(item.status == "complete" for item in results),
        failed_documents=sum(item.status == "failed" for item in results),
        total_chunks=sum(item.chunks for item in results),
        generated_embeddings=sum(item.generated_embeddings for item in results),
        reused_embeddings=sum(item.reused_embeddings for item in results),
        documents=tuple(results),
    )


def ingest_manifest(
    manifest: CorpusManifest,
    *,
    corpus_root: Path,
    extraction_root: Path,
    chunk_root: Path,
    through: IngestionStage,
    extraction_options: ExtractionOptions,
    chunking_options: ChunkingOptions,
    lexical: OpenSearchClient | None = None,
    semantic_embedder: DenseEmbedder | None = None,
    semantic_store: SemanticStore | None = None,
    roles: set[str] | None = None,
    continue_on_error: bool = True,
    progress: ProgressCallback | None = None,
) -> IngestionReport:
    selected = [
        document
        for document in manifest.documents
        if roles is None or document.role in roles
    ]
    if not selected:
        raise ValueError("no manifest documents match the selected roles")
    if STAGE_ORDER[through] >= STAGE_ORDER[IngestionStage.LEXICAL] and lexical is None:
        raise ValueError("lexical client is required for lexical ingestion")
    if (
        STAGE_ORDER[through] >= STAGE_ORDER[IngestionStage.SEMANTIC]
        and (semantic_embedder is None or semantic_store is None)
    ):
        raise ValueError("embedder and semantic store are required")

    started_at = datetime.now(UTC)
    results: list[DocumentIngestionResult] = []
    for document in selected:
        try:
            result = _ingest_document(
                document,
                corpus_root=corpus_root,
                extraction_root=extraction_root,
                chunk_root=chunk_root,
                through=through,
                extraction_options=extraction_options,
                chunking_options=chunking_options,
                lexical=lexical,
                semantic_embedder=semantic_embedder,
                semantic_store=semantic_store,
            )
        except Exception as error:
            result = DocumentIngestionResult(
                role=document.role,
                path=document.path,
                status="failed",
                error=f"{type(error).__name__}: {error}",
            )
            results.append(result)
            if progress is not None:
                progress(
                    _report(
                        started_at=started_at,
                        stage=through,
                        manifest_count=len(manifest.documents),
                        selected_count=len(selected),
                        results=results,
                    )
                )
            if not continue_on_error:
                raise
            continue
        results.append(result)
        if progress is not None:
            progress(
                _report(
                    started_at=started_at,
                    stage=through,
                    manifest_count=len(manifest.documents),
                    selected_count=len(selected),
                    results=results,
                )
            )
    return _report(
        started_at=started_at,
        stage=through,
        manifest_count=len(manifest.documents),
        selected_count=len(selected),
        results=results,
    )


def _ingest_document(
    document: CorpusDocument,
    *,
    corpus_root: Path,
    extraction_root: Path,
    chunk_root: Path,
    through: IngestionStage,
    extraction_options: ExtractionOptions,
    chunking_options: ChunkingOptions,
    lexical: OpenSearchClient | None,
    semantic_embedder: DenseEmbedder | None,
    semantic_store: SemanticStore | None,
) -> DocumentIngestionResult:
    extraction = extract_document(
        corpus_root=corpus_root,
        relative_path=document.path,
        output_root=extraction_root,
        options=extraction_options,
        role=document.role,
        metadata=document.extraction_metadata(),
    )
    if through is IngestionStage.EXTRACT:
        return DocumentIngestionResult(
            role=document.role,
            path=document.path,
            status="complete",
            completed_stage=through,
            extraction_reused=extraction.reused,
        )

    chunking = chunk_extraction(
        extraction_path=extraction.artifact_path,
        output_root=chunk_root,
        options=chunking_options,
    )
    chunks = len(chunking.artifact.chunks)
    if through is IngestionStage.CHUNK:
        return DocumentIngestionResult(
            role=document.role,
            path=document.path,
            status="complete",
            completed_stage=through,
            extraction_reused=extraction.reused,
            chunking_reused=chunking.reused,
            chunks=chunks,
        )

    if lexical is None:
        raise RuntimeError("lexical client is not configured")
    lexical.index_artifact(chunking.artifact)
    if through is IngestionStage.LEXICAL:
        return DocumentIngestionResult(
            role=document.role,
            path=document.path,
            status="complete",
            completed_stage=through,
            extraction_reused=extraction.reused,
            chunking_reused=chunking.reused,
            chunks=chunks,
        )

    if semantic_embedder is None or semantic_store is None:
        raise RuntimeError("semantic ingestion is not configured")
    semantic = index_chunk_artifact(
        chunking.artifact_path,
        embedder=semantic_embedder,
        store=semantic_store,
    )
    return DocumentIngestionResult(
        role=document.role,
        path=document.path,
        status="complete",
        completed_stage=through,
        extraction_reused=extraction.reused,
        chunking_reused=chunking.reused,
        chunks=chunks,
        generated_embeddings=semantic.generated_embeddings,
        reused_embeddings=semantic.reused_embeddings,
    )
