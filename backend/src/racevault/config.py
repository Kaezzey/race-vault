"""Application configuration loaded from environment variables."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from racevault.lexical.mapping import DEFAULT_INDEX_NAME


class Settings(BaseSettings):
    """RaceVault settings with safe local-development defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RACEVAULT_",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    postgres_db: str = "racevault"
    postgres_user: str = "racevault"
    postgres_password: str = "racevault-local-only"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    opensearch_url: str = "http://localhost:9200"
    opensearch_index_name: str = DEFAULT_INDEX_NAME
    opensearch_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    semantic_model_id: str = "BAAI/bge-m3"
    semantic_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    semantic_max_tokens: int = Field(default=8192, ge=1, le=8192)
    semantic_batch_size: int = Field(default=8, ge=1, le=128)
    reranker_model_id: str = "BAAI/bge-reranker-v2-m3"
    reranker_model_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    reranker_max_tokens: int = Field(default=8192, ge=1, le=8192)
    reranker_batch_size: int = Field(default=8, ge=1, le=128)
    api_model_device: Literal["auto", "cpu", "cuda"] = "auto"
    api_local_files_only: bool = False
    api_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    api_ingestion_enabled: bool = False
    retrieval_prefer_latest_edition: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout_seconds: float = Field(default=300.0, gt=0, le=900)
    ollama_context_tokens: int = Field(default=16384, ge=2048, le=32768)
    ollama_max_output_tokens: int = Field(default=3072, ge=64, le=4096)
    # Unloading between requests costs about seven seconds on the next
    # answer. Holding the model resident needs roughly 6.5 GB of VRAM on
    # top of the retrieval models; set "0" to evict it on a smaller GPU.
    ollama_keep_alive: str = "5m"
    answer_retrieval_candidate_limit: int = Field(default=20, ge=1, le=20)
    answer_facet_candidate_limit: int = Field(default=8, ge=1, le=10)
    answer_max_query_facets: int = Field(default=6, ge=3, le=8)
    answer_evidence_limit: int = Field(default=8, ge=1, le=10)
    answer_max_evidence_limit: int = Field(default=10, ge=1, le=10)
    answer_evidence_character_budget: int = Field(
        default=24000, ge=4000, le=60000
    )
    answer_evidence_topic_weight: float = Field(default=0.15, ge=0, le=1)
    answer_evidence_diversity_weight: float = Field(default=0.2, ge=0, le=1)
    answer_evidence_duplicate_threshold: float = Field(
        default=0.9, gt=0, le=1
    )
    answer_evidence_max_per_source: int = Field(default=3, ge=1, le=10)
    answer_minimum_reranker_score: float | None = Field(
        default=None, ge=0, le=1
    )
    # Releasing the embedder and reranker after every answer frees 2.3 GB
    # but costs about 6.5 seconds reloading them on the next request. Both
    # fit alongside the generation model on a 12 GB card; enable this only
    # where they do not.
    answer_release_retrieval_models: bool = False
    generation_max_concurrency: int = Field(default=1, ge=1, le=4)
    generation_queue_depth: int = Field(default=4, ge=0, le=32)
    generation_retry_after_seconds: int = Field(default=5, ge=1, le=300)
    metrics_enabled: bool = True
    json_logging: bool = False
    otel_exporter_endpoint: str | None = None
    otel_service_name: str = "racevault-api"
    corpus_manifest_path: str = "corpus/full_documents.json"
    corpus_root_path: str = "AI & ML Reference File Database"
    extraction_root_path: str = ".artifacts/extracted"
    chunk_root_path: str = ".artifacts/chunks"
    upload_root_path: str = ".artifacts/uploads"
    upload_max_bytes: int = Field(default=250 * 1024 * 1024, ge=1024, le=2**31)
    ingestion_extraction_device: Literal["auto", "cpu", "cuda"] = "auto"
    ingestion_threads: int = Field(default=8, ge=1, le=64)
    ingestion_report_path: str = ".artifacts/reports/full-ingestion.json"
    dependency_timeout_seconds: float = Field(default=2.0, gt=0, le=30)

    @property
    def database_url(self) -> str:
        """Return a SQLAlchemy-compatible psycopg connection URL."""

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{user}:{password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def psycopg_conninfo(self) -> str:
        """Return a libpq connection string for async readiness checks."""

        return (
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password} host={self.postgres_host} "
            f"port={self.postgres_port}"
        )

    @property
    def pipeline_fingerprint(self) -> str:
        """Hash quality-affecting settings without including credentials."""

        values = {
            "semantic_model": [self.semantic_model_id, self.semantic_model_revision],
            "semantic_max_tokens": self.semantic_max_tokens,
            "reranker_model": [self.reranker_model_id, self.reranker_model_revision],
            "reranker_max_tokens": self.reranker_max_tokens,
            "generation_model": self.ollama_model,
            "generation_context_tokens": self.ollama_context_tokens,
            "generation_max_output_tokens": self.ollama_max_output_tokens,
            "retrieval_candidate_limit": self.answer_retrieval_candidate_limit,
            "facet_candidate_limit": self.answer_facet_candidate_limit,
            "maximum_query_facets": self.answer_max_query_facets,
            "evidence_limit": self.answer_evidence_limit,
            "max_evidence_limit": self.answer_max_evidence_limit,
            "evidence_character_budget": self.answer_evidence_character_budget,
            "evidence_topic_weight": self.answer_evidence_topic_weight,
            "evidence_diversity_weight": self.answer_evidence_diversity_weight,
            "evidence_duplicate_threshold": (
                self.answer_evidence_duplicate_threshold
            ),
            "evidence_max_per_source": self.answer_evidence_max_per_source,
            "minimum_reranker_score": self.answer_minimum_reranker_score,
            "prefer_latest_edition": self.retrieval_prefer_latest_edition,
            "opensearch_index": self.opensearch_index_name,
        }
        encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
