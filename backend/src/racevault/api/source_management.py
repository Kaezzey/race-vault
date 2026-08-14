"""Managed source upload, ingestion, and removal."""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
import uuid
from contextlib import ExitStack
from pathlib import Path
from typing import BinaryIO, Literal, Protocol

from pydantic import Field

from racevault.chunking.models import DocumentClass
from racevault.chunking.pipeline import ChunkingOptions, chunk_extraction
from racevault.config import Settings
from racevault.extraction.models import ArtifactModel
from racevault.extraction.pipeline import ExtractionOptions, extract_document
from racevault.lexical.client import OpenSearchClient
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.pipeline import index_chunk_artifact
from racevault.semantic.store import SemanticStore

UploadState = Literal[
    "queued",
    "extracting",
    "chunking",
    "indexing",
    "complete",
    "failed",
]


class SourceUploadStatus(ArtifactModel):
    run_id: str
    filename: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: UploadState
    chunks: int = Field(default=0, ge=0)
    generated_embeddings: int = Field(default=0, ge=0)
    reused_embeddings: int = Field(default=0, ge=0)
    error: str | None = None


class SourceDeletionResult(ArtifactModel):
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    removed_documents: int = Field(ge=0)
    removed_chunks: int = Field(ge=0)
    removed_opensearch_chunks: int = Field(ge=0)


class SourceManager(Protocol):
    def start_upload(
        self,
        *,
        filename: str,
        file: BinaryIO,
        document_type: DocumentClass | None,
        authority: str,
    ) -> SourceUploadStatus: ...

    def upload_status(self, run_id: str) -> SourceUploadStatus | None: ...

    def delete_source(self, source_sha256: str) -> SourceDeletionResult: ...


def _safe_filename(filename: str) -> str:
    leaf = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", leaf).strip(" .")
    if not safe or not safe.lower().endswith(".pdf"):
        raise ValueError("upload must be a PDF file")
    return safe


class LocalSourceManager:
    """Store uploads locally and run one ingestion pipeline at a time."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._processing_lock = threading.Lock()
        self._jobs: dict[str, SourceUploadStatus] = {}

    def _set_status(self, run_id: str, **changes: object) -> None:
        with self._lock:
            self._jobs[run_id] = self._jobs[run_id].model_copy(update=changes)

    def _store_upload(self, filename: str, file: BinaryIO) -> tuple[Path, str]:
        upload_root = Path(self._settings.upload_root_path).resolve()
        incoming = upload_root / ".incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        temporary = incoming / f"{uuid.uuid4().hex}.part"
        digest = hashlib.sha256()
        size = 0
        header = b""
        try:
            with temporary.open("xb") as output:
                while block := file.read(1024 * 1024):
                    if not header:
                        header = block[:5]
                    size += len(block)
                    if size > self._settings.upload_max_bytes:
                        raise ValueError(
                            "PDF exceeds the configured upload size limit"
                        )
                    digest.update(block)
                    output.write(block)
            if header != b"%PDF-":
                raise ValueError("uploaded file does not contain a PDF header")
            source_sha256 = digest.hexdigest()
            target = upload_root / source_sha256 / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                temporary.unlink()
            else:
                os.replace(temporary, target)
            return target, source_sha256
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def start_upload(
        self,
        *,
        filename: str,
        file: BinaryIO,
        document_type: DocumentClass | None,
        authority: str,
    ) -> SourceUploadStatus:
        safe_name = _safe_filename(filename)
        source_path, source_sha256 = self._store_upload(safe_name, file)
        run_id = uuid.uuid4().hex
        status = SourceUploadStatus(
            run_id=run_id,
            filename=safe_name,
            source_sha256=source_sha256,
            status="queued",
        )
        with self._lock:
            active = next(
                (
                    job
                    for job in self._jobs.values()
                    if job.source_sha256 == source_sha256
                    and job.status not in {"complete", "failed"}
                ),
                None,
            )
            if active is not None:
                return active
            self._jobs[run_id] = status
        thread = threading.Thread(
            target=self._run_upload,
            kwargs={
                "run_id": run_id,
                "source_path": source_path,
                "document_type": document_type,
                "authority": authority,
            },
            name=f"racevault-source-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return status

    def upload_status(self, run_id: str) -> SourceUploadStatus | None:
        with self._lock:
            return self._jobs.get(run_id)

    def _source_sha256(self, run_id: str) -> str:
        with self._lock:
            return self._jobs[run_id].source_sha256

    def _run_upload(
        self,
        *,
        run_id: str,
        source_path: Path,
        document_type: DocumentClass | None,
        authority: str,
    ) -> None:
        with self._processing_lock:
            source_sha256 = self._source_sha256(run_id)
            existed_before_upload = False
            try:
                existed_before_upload = self._semantic_store().source_exists(
                    source_sha256
                )
                self._ingest_upload(
                    run_id=run_id,
                    source_path=source_path,
                    document_type=document_type,
                    authority=authority,
                )
            except Exception as error:
                self._set_status(
                    run_id,
                    status="failed",
                    error=f"{type(error).__name__}: {error}",
                )
                if not existed_before_upload:
                    try:
                        with self._lexical_client() as lexical:
                            lexical.delete_source(source_sha256)
                        self._semantic_store().delete_source(source_sha256)
                    except Exception:
                        pass

    def _lexical_client(self) -> OpenSearchClient:
        return OpenSearchClient(
            base_url=self._settings.opensearch_url,
            index_name=self._settings.opensearch_index_name,
            timeout_seconds=self._settings.opensearch_timeout_seconds,
        )

    def _semantic_store(self) -> SemanticStore:
        settings = self._settings
        return SemanticStore(
            settings.psycopg_conninfo
            + " connect_timeout="
            + str(max(1, math.ceil(settings.dependency_timeout_seconds)))
        )

    def _ingest_upload(
        self,
        *,
        run_id: str,
        source_path: Path,
        document_type: DocumentClass | None,
        authority: str,
    ) -> None:
        settings = self._settings
        upload_root = Path(settings.upload_root_path).resolve()
        relative_path = source_path.relative_to(upload_root).as_posix()
        source_sha256 = self._source_sha256(run_id)
        metadata: dict[str, object] = {
            "authority": authority,
            "uploaded": True,
        }
        if document_type is not None:
            metadata["document_type"] = document_type.value

        self._set_status(run_id, status="extracting")
        extraction = extract_document(
            corpus_root=upload_root,
            relative_path=relative_path,
            output_root=Path(settings.extraction_root_path),
            options=ExtractionOptions(
                device=settings.ingestion_extraction_device,
                num_threads=settings.ingestion_threads,
            ),
            role=f"uploaded_{source_sha256[:12]}",
            metadata=metadata,
        )

        self._set_status(run_id, status="chunking")
        chunking = chunk_extraction(
            extraction_path=extraction.artifact_path,
            output_root=Path(settings.chunk_root_path),
            options=ChunkingOptions(),
        )
        self._set_status(
            run_id,
            status="indexing",
            chunks=len(chunking.artifact.chunks),
        )

        spec = EmbeddingModelSpec(
            model_id=settings.semantic_model_id,
            model_revision=settings.semantic_model_revision,
            max_tokens=settings.semantic_max_tokens,
        )
        with ExitStack() as stack:
            lexical = stack.enter_context(self._lexical_client())
            lexical.index_artifact(chunking.artifact)
            embedder = BgeM3Embedder(
                spec=spec,
                device=settings.api_model_device,
                batch_size=settings.semantic_batch_size,
                local_files_only=settings.api_local_files_only,
            )
            semantic = index_chunk_artifact(
                chunking.artifact_path,
                embedder=embedder,
                store=self._semantic_store(),
            )
        self._set_status(
            run_id,
            status="complete",
            generated_embeddings=semantic.generated_embeddings,
            reused_embeddings=semantic.reused_embeddings,
        )

    def delete_source(self, source_sha256: str) -> SourceDeletionResult:
        with self._lock:
            active = any(
                job.source_sha256 == source_sha256
                and job.status not in {"complete", "failed"}
                for job in self._jobs.values()
            )
        if active:
            raise RuntimeError("source ingestion is still active")
        with self._processing_lock, self._lexical_client() as lexical:
            removed_opensearch = lexical.delete_source(source_sha256)
            removed_documents, removed_chunks = self._semantic_store().delete_source(
                source_sha256
            )
        return SourceDeletionResult(
            source_sha256=source_sha256,
            removed_documents=removed_documents,
            removed_chunks=removed_chunks,
            removed_opensearch_chunks=removed_opensearch,
        )
