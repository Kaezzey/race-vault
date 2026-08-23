"""Edition narrowing as the retrieval service applies it."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from racevault.api.services import HybridRetrievalService
from racevault.catalog.store import CatalogStore
from racevault.config import Settings
from racevault.retrieval.editions import DocumentEdition
from racevault.retrieval.models import SearchFilters

CORPUS_EDITIONS = (
    DocumentEdition(championship="PCC Asia", season=2025, revision="Final"),
    DocumentEdition(championship="PCC Asia", season=2026, revision="Final"),
    DocumentEdition(championship="PCC Australia", season=2025, revision="V1"),
    DocumentEdition(championship="PCC Australia", season=2026, revision="Version 2"),
    DocumentEdition(championship="PCC France", season=2025),
    DocumentEdition(championship="PCC France", season=2026),
)


def _service(*, prefer_latest: bool = True) -> HybridRetrievalService:
    catalog = Mock(spec=CatalogStore)
    catalog.list_document_editions.return_value = CORPUS_EDITIONS
    catalog.list_vehicle_generations.return_value = ("992.1", "992.2")
    return HybridRetrievalService(
        Settings(retrieval_prefer_latest_edition=prefer_latest),
        cast(CatalogStore, catalog),
    )


def test_unqualified_question_is_scoped_to_the_current_season() -> None:
    scopes = _service().resolve_scopes(
        "What is the minimum car weight in PCC Australia?", SearchFilters()
    )

    assert [(item.championship, item.season) for item in scopes] == [
        ("PCC Australia", 2026)
    ]


def test_a_season_named_in_the_question_wins() -> None:
    scopes = _service().resolve_scopes(
        "What was the minimum car weight in PCC Australia in 2025?", SearchFilters()
    )

    assert [(item.championship, item.season) for item in scopes] == [
        ("PCC Australia", 2025)
    ]


def test_an_explicit_api_filter_wins() -> None:
    scopes = _service().resolve_scopes(
        "What is the minimum car weight in PCC Australia?",
        SearchFilters(season=2025),
    )

    assert [item.season for item in scopes] == [2025]


def test_each_side_of_a_comparison_is_narrowed_independently() -> None:
    scopes = _service().resolve_scopes(
        "Compare track limits between PCC Asia and PCC France", SearchFilters()
    )

    assert [(item.championship, item.season) for item in scopes] == [
        ("PCC Asia", 2026),
        ("PCC France", 2026),
    ]


def test_narrowing_can_be_disabled() -> None:
    scopes = _service(prefer_latest=False).resolve_scopes(
        "What is the minimum car weight in PCC Australia?", SearchFilters()
    )

    assert [item.season for item in scopes] == [None]


def test_questions_without_a_championship_are_untouched() -> None:
    scopes = _service().resolve_scopes(
        "What is the ABS calibration procedure?", SearchFilters()
    )

    assert scopes == (SearchFilters(),)


def test_search_clients_are_built_once_per_service() -> None:
    """Every facet runs its own search; building a client each time dominates."""

    service = _service()

    first_lexical, first_store = service._clients()
    second_lexical, second_store = service._clients()

    assert first_lexical is second_lexical
    assert first_store is second_store

    service.close()
    assert service._lexical is None
