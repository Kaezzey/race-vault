from __future__ import annotations

from racevault.config import Settings


def test_database_credentials_are_url_encoded() -> None:
    settings = Settings(postgres_user="race vault", postgres_password="p@ss/word")

    assert "race+vault:p%40ss%2Fword@" in settings.database_url


def test_dependency_timeout_must_be_positive() -> None:
    try:
        Settings(dependency_timeout_seconds=0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero timeout should fail validation")

