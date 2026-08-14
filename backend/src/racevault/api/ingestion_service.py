"""Single-run background coordinator for resumable corpus ingestion."""

from __future__ import annotations

import math
import threading
import uuid
from contextlib import ExitStack
from pathlib import Path
from typing import Protocol

from racevault.chunking.pipeline import ChunkingOptions
from racevault.config import Settings
from racevault.corpus.ingestion import (
    IngestionReport,
    IngestionStage,
    ingest_manifest,
)
from racevault.corpus.manifest import load_manifest, validate_manifest_coverage
from racevault.extraction.io import load_json, write_json_atomic
from racevault.extraction.pipeline import ExtractionOptions
from racevault.lexical.client import OpenSearchClient
from racevault.semantic.embedder import BgeM3Embedder
from racevault.semantic.models import EmbeddingModelSpec
from racevault.semantic.store import SemanticStore


class IngestionCoordinator(Protocol):
    def start(
        self,
        *,
        roles: set[str] | None,
        through: IngestionStage,
    ) -> str: ...

    def snapshot(
        self,
    ) -> tuple[str | None, bool, str | None, IngestionReport | None]: ...


class LocalIngestionCoordinator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._active = False
        self._run_id: str | None = None
        self._detail: str | None = None

    def _report(self) -> IngestionReport | None:
        path = Path(self._settings.ingestion_report_path)
        if not path.is_file():
            return None
        return IngestionReport.model_validate(load_json(path))

    def snapshot(
        self,
    ) -> tuple[str | None, bool, str | None, IngestionReport | None]:
        with self._lock:
            return self._run_id, self._active, self._detail, self._report()

    def start(
        self,
        *,
        roles: set[str] | None,
        through: IngestionStage,
    ) -> str:
        if not self._settings.api_ingestion_enabled:
            raise PermissionError("API-triggered ingestion is disabled")
        manifest = load_manifest(Path(self._settings.corpus_manifest_path))
        validate_manifest_coverage(
            manifest, Path(self._settings.corpus_root_path)
        )
        available_roles = {item.role for item in manifest.documents}
        if roles is not None and not roles.issubset(available_roles):
            raise ValueError(
                f"unknown corpus roles: {sorted(roles - available_roles)}"
            )
        with self._lock:
            if self._active:
                raise RuntimeError("an ingestion run is already active")
            run_id = uuid.uuid4().hex
            self._run_id = run_id
            self._active = True
            self._detail = None
        thread = threading.Thread(
            target=self._run,
            kwargs={"roles": roles, "through": through},
            name=f"racevault-ingestion-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return run_id

    def _run(self, *, roles: set[str] | None, through: IngestionStage) -> None:
        try:
            self._execute(roles=roles, through=through)
        except Exception as error:
            with self._lock:
                self._detail = f"{type(error).__name__}: {error}"
        finally:
            with self._lock:
                self._active = False

    def _execute(self, *, roles: set[str] | None, through: IngestionStage) -> None:
        settings = self._settings
        manifest = load_manifest(Path(settings.corpus_manifest_path))
        embedding_spec = EmbeddingModelSpec(
            model_id=settings.semantic_model_id,
            model_revision=settings.semantic_model_revision,
            max_tokens=settings.semantic_max_tokens,
        )
        report_path = Path(settings.ingestion_report_path)
        with ExitStack() as stack:
            lexical = None
            if through in {IngestionStage.LEXICAL, IngestionStage.SEMANTIC}:
                lexical = stack.enter_context(
                    OpenSearchClient(
                        base_url=settings.opensearch_url,
                        index_name=settings.opensearch_index_name,
                        timeout_seconds=settings.opensearch_timeout_seconds,
                    )
                )
            embedder = None
            store = None
            if through is IngestionStage.SEMANTIC:
                embedder = BgeM3Embedder(
                    spec=embedding_spec,
                    device=settings.api_model_device,
                    batch_size=settings.semantic_batch_size,
                    local_files_only=settings.api_local_files_only,
                )
                store = SemanticStore(
                    settings.psycopg_conninfo
                    + " connect_timeout="
                    + str(max(1, math.ceil(settings.dependency_timeout_seconds)))
                )
            report = ingest_manifest(
                manifest,
                corpus_root=Path(settings.corpus_root_path),
                extraction_root=Path(settings.extraction_root_path),
                chunk_root=Path(settings.chunk_root_path),
                through=through,
                extraction_options=ExtractionOptions(
                    device=settings.ingestion_extraction_device,
                    num_threads=settings.ingestion_threads,
                ),
                chunking_options=ChunkingOptions(),
                lexical=lexical,
                semantic_embedder=embedder,
                semantic_store=store,
                roles=roles,
                continue_on_error=True,
                progress=lambda checkpoint: write_json_atomic(
                    report_path, checkpoint
                ),
            )
        write_json_atomic(report_path, report)
