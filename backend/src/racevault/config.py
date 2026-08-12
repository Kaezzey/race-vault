"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
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
