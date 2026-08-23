from __future__ import annotations

import pytest

from racevault.config import Settings


def test_database_credentials_are_url_encoded() -> None:
    settings = Settings(postgres_user="race vault", postgres_password="p@ss/word")

    assert "race+vault:p%40ss%2Fword@" in settings.database_url


def test_dependency_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Settings(dependency_timeout_seconds=0)


def test_empty_optional_setting_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RACEVAULT_ANSWER_MINIMUM_RERANKER_SCORE", "")

    settings = Settings(_env_file=None)

    assert settings.answer_minimum_reranker_score is None


def test_pipeline_fingerprint_excludes_credentials() -> None:
    first = Settings(postgres_password="first-secret")
    second = Settings(postgres_password="second-secret")

    assert first.pipeline_fingerprint == second.pipeline_fingerprint
    assert "first-secret" not in first.pipeline_fingerprint


def test_grounded_answer_defaults_allow_analytical_responses() -> None:
    settings = Settings(_env_file=None)

    assert settings.answer_retrieval_candidate_limit == 20
    assert settings.answer_facet_candidate_limit == 8
    assert settings.answer_max_query_facets == 6
    assert settings.answer_evidence_limit == 8
    assert settings.answer_evidence_character_budget == 24000
    assert settings.ollama_context_tokens == 16384
    assert settings.ollama_max_output_tokens == 3072
