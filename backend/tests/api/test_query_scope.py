from __future__ import annotations

from racevault.api.services import _interleave_scoped_results
from racevault.fusion.models import FusedCandidate, HybridSearchResponse
from racevault.retrieval.models import SearchFilters
from racevault.retrieval.query_scope import (
    remove_query_scope_terms,
    resolve_query_filter_scopes,
)
from tests.fusion.factories import lexical_hit

CHAMPIONSHIPS = (
    "PCC Asia",
    "PCC Australia",
    "PCC Benelux",
    "PCC France",
    "PCC Great Britain",
    "PCC Scandinavia",
)
VEHICLE_GENERATIONS = ("992.1", "992.2")


def _response(*numbers: int) -> HybridSearchResponse:
    candidates = []
    for rank, number in enumerate(numbers, start=1):
        hit = lexical_hit(number)
        values = {
            name: getattr(hit, name)
            for name in FusedCandidate.model_fields
            if hasattr(hit, name)
        }
        values.update(
            lexical_rank=rank,
            lexical_score=hit.score,
            semantic_rank=rank,
            semantic_score=0.8,
            rrf_score=0.03,
            fused_rank=rank,
            reranker_score=0.9,
            final_rank=rank,
        )
        candidates.append(FusedCandidate.model_validate(values))
    return HybridSearchResponse(
        query="weight comparison",
        lexical_hits=len(candidates),
        semantic_hits=len(candidates),
        fused_candidates=len(candidates),
        reranked_candidates=len(candidates),
        results=tuple(candidates),
    )


def test_query_championship_is_applied_as_a_filter() -> None:
    scopes = resolve_query_filter_scopes(
        "What is the car weight for pcc australia?",
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    assert [item.championship for item in scopes] == ["PCC Australia"]


def test_explicit_filter_takes_precedence_over_query_scope() -> None:
    explicit = SearchFilters(championship="PCC Scandinavia")

    scopes = resolve_query_filter_scopes(
        "Compare with PCC Australia",
        explicit,
        championships=CHAMPIONSHIPS,
    )

    assert scopes == (explicit,)


def test_query_vehicle_generation_is_applied_as_a_filter() -> None:
    scopes = resolve_query_filter_scopes(
        "What are the minimum cold pressures for the 992.1 N3 tyres?",
        SearchFilters(),
        championships=CHAMPIONSHIPS,
        vehicle_generations=VEHICLE_GENERATIONS,
    )

    assert scopes == (SearchFilters(vehicle_generation="992.1"),)


def test_explicit_vehicle_filter_takes_precedence_over_query_scope() -> None:
    explicit = SearchFilters(vehicle_generation="992.2")

    scopes = resolve_query_filter_scopes(
        "Compare with the 992.1 car",
        explicit,
        championships=CHAMPIONSHIPS,
        vehicle_generations=VEHICLE_GENERATIONS,
    )

    assert scopes == (explicit,)


def test_single_query_season_is_applied_to_each_championship_scope() -> None:
    scopes = resolve_query_filter_scopes(
        "Compare the 2026 PCC Great Britain and PCC Asia regulations",
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    assert scopes == (
        SearchFilters(championship="PCC Great Britain", season=2026),
        SearchFilters(championship="PCC Asia", season=2026),
    )


def test_explicit_season_filter_takes_precedence_over_query_year() -> None:
    scopes = resolve_query_filter_scopes(
        "Compare the 2026 PCC Great Britain regulations",
        SearchFilters(season=2025),
        championships=CHAMPIONSHIPS,
    )

    assert scopes == (
        SearchFilters(championship="PCC Great Britain", season=2025),
    )


def test_multiple_championship_mentions_create_ordered_scopes() -> None:
    scopes = resolve_query_filter_scopes(
        "Compare PCC Australia with PCC Great Britain",
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    assert [item.championship for item in scopes] == [
        "PCC Australia",
        "PCC Great Britain",
    ]


def test_natural_pcc_suffixes_create_ordered_scopes() -> None:
    scopes = resolve_query_filter_scopes(
        "Race rule differences between Great Britain and Asia",
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    assert [item.championship for item in scopes] == [
        "PCC Great Britain",
        "PCC Asia",
    ]


def test_partial_championship_name_is_not_inferred() -> None:
    scopes = resolve_query_filter_scopes(
        "What is the Australian car weight?",
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    assert scopes == (SearchFilters(),)


def test_scoped_results_are_interleaved_for_comparison_coverage() -> None:
    results = _interleave_scoped_results(
        (_response(1, 2), _response(3, 4)),
        limit=4,
    )

    assert [item.chunk_id for item in results] == [
        f"chk_{number:032x}" for number in (1, 3, 2, 4)
    ]
    assert [item.final_rank for item in results] == [1, 2, 3, 4]


def test_scope_terms_are_removed_from_the_content_query() -> None:
    query = "Compare car weights for PCC Australia and PCC Great Britain"
    scopes = resolve_query_filter_scopes(
        query,
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    content_query = remove_query_scope_terms(query, scopes)

    assert content_query == "car weights"


def test_comparison_language_is_removed_from_the_content_query() -> None:
    query = (
        "What are the requirements for car weights for PCC Australia, "
        "PCC Great Britain, PCC France, and PCC Benelux? "
        "How do they differ from each other?"
    )
    scopes = resolve_query_filter_scopes(
        query,
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    content_query = remove_query_scope_terms(query, scopes)

    assert content_query == "requirements car weights"


def test_natural_scope_aliases_are_removed_from_the_content_query() -> None:
    query = "Race rule differences between Great Britain and Asia"
    scopes = resolve_query_filter_scopes(
        query,
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    content_query = remove_query_scope_terms(query, scopes)

    assert content_query == "Race rule"


def test_vehicle_generation_is_removed_after_becoming_a_filter() -> None:
    query = "What is the minimum cold pressure for the 992.1 N3 tyre?"
    scopes = resolve_query_filter_scopes(
        query,
        SearchFilters(),
        championships=CHAMPIONSHIPS,
        vehicle_generations=VEHICLE_GENERATIONS,
    )

    content_query = remove_query_scope_terms(query, scopes)

    assert content_query == "minimum cold pressure N3 tyre"


def test_season_is_removed_after_becoming_a_filter() -> None:
    query = "Compare the 2026 PCC Great Britain and PCC Asia qualifying rules"
    scopes = resolve_query_filter_scopes(
        query,
        SearchFilters(),
        championships=CHAMPIONSHIPS,
    )

    content_query = remove_query_scope_terms(query, scopes)

    assert content_query == "qualifying rules"
