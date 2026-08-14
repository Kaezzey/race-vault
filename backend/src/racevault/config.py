"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RaceVault settings with safe local-development defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RACEVAULT_",
        case_sensitive=False,
        extra="ignore",
    )

    postgres_db: str = "racevault"
    postgres_user: str = "racevault"
    postgres_password: str = "racevault-local-only"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    opensearch_url: str = "http://localhost:9200"
    opensearch_index_name: str = "racevault-chunks-v1"
    opensearch_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    semantic_model_id: str = "BAAI/bge-m3"
    semantic_model_revision: str = "5617a9f61b028005a4858fdac845db406aefb181"
    semantic_max_tokens: int = Field(default=8192, ge=1, le=8192)
    semantic_batch_size: int = Field(default=8, ge=1, le=128)
    reranker_model_id: str = "BAAI/bge-reranker-v2-m3"
    reranker_model_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    reranker_max_tokens: int = Field(default=8192, ge=1, le=8192)
    reranker_batch_size: int = Field(default=4, ge=1, le=128)
    api_model_device: Literal["auto", "cpu", "cuda"] = "auto"
    api_local_files_only: bool = False
    api_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    api_ingestion_enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout_seconds: float = Field(default=300.0, gt=0, le=900)
    ollama_context_tokens: int = Field(default=8192, ge=2048, le=32768)
    ollama_max_output_tokens: int = Field(default=1024, ge=64, le=4096)
    ollama_keep_alive: str = "0"
    answer_evidence_limit: int = Field(default=3, ge=1, le=10)
    answer_max_evidence_limit: int = Field(default=10, ge=1, le=10)
    answer_evidence_character_budget: int = Field(
        default=12000, ge=4000, le=60000
    )
    answer_release_retrieval_models: bool = True
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
