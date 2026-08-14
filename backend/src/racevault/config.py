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
    corpus_manifest_path: str = "corpus/full_documents.json"
    corpus_root_path: str = "AI & ML Reference File Database"
    extraction_root_path: str = ".artifacts/extracted"
    chunk_root_path: str = ".artifacts/chunks"
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
