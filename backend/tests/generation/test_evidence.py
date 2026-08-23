from __future__ import annotations

import pytest

from racevault.api.models import RetrievalResult
from racevault.generation.evidence import (
    QueryFacet,
    classify_query_intent,
    decompose_query_facets,
    select_evidence,
)
from tests.api.factories import retrieval_response


def _result(
    rank: int,
    *,
    text: str,
    score: float,
    source_digit: str,
    championship: str | None = None,
) -> RetrievalResult:
    base = retrieval_response().results[0]
    metadata = dict(base.source_metadata)
    if championship is not None:
        metadata["championship"] = championship
    return base.model_copy(
        update={
            "rank": rank,
            "evidence_text": text,
            "source_metadata": metadata,
            "citation": base.citation.model_copy(
                update={
                    "chunk_id": f"chk_{rank:032x}",
                    "source_sha256": source_digit * 64,
                }
            ),
            "diagnostics": base.diagnostics.model_copy(
                update={"reranker_score": score, "lexical_rank": rank}
            ),
        }
    )


def test_query_intent_detects_identifiers_numbers_and_conflicts() -> None:
    assert classify_query_intent("What is rule 8.4.2?") == "exact_or_numeric"
    assert classify_query_intent("Is the pressure 2.4 bar?") == "exact_or_numeric"
    assert (
        classify_query_intent("Compare the conflicting revisions")
        == "comparison_or_conflict"
    )
    assert (
        classify_query_intent(
            "Race rule differences between Great Britain and Asia"
        )
        == "comparison_or_conflict"
    )
    assert classify_query_intent("Explain brake balance") == "concept"
    assert classify_query_intent("minimum cold pressure") == "exact_or_numeric"


def test_selector_covers_scopes_and_removes_near_duplicates() -> None:
    candidates = (
        _result(
            1,
            text="Brake pressure must be 10 bar for dry running.",
            score=0.95,
            source_digit="1",
            championship="Series A",
        ),
        _result(
            2,
            text="Brake pressure must be 10 bar for dry running.",
            score=0.94,
            source_digit="1",
            championship="Series A",
        ),
        _result(
            3,
            text="Series B specifies a maximum pedal ratio of 5.0.",
            score=0.85,
            source_digit="2",
            championship="Series B",
        ),
    )

    selection = select_evidence(
        "compare Series A and Series B",
        candidates,
        limit=3,
        required_scopes=("Series A", "Series B"),
    )

    assert [item.rank for item in selection.results] == [1, 3]
    assert selection.diagnostics.duplicates_removed == 1
    assert selection.diagnostics.covered_scopes == ("Series A", "Series B")
    assert selection.diagnostics.distinct_sources == 2


def test_comparison_intent_rewards_a_distinct_source() -> None:
    candidates = (
        _result(
            1,
            text="Revision A permits an adjustable front anti-roll bar.",
            score=0.90,
            source_digit="1",
        ),
        _result(
            2,
            text="The same manual defines the rear spring installation.",
            score=0.89,
            source_digit="1",
        ),
        _result(
            3,
            text="Revision B prohibits adjustable anti-roll bars.",
            score=0.87,
            source_digit="2",
        ),
    )

    selection = select_evidence(
        "compare the conflicting revisions", candidates, limit=2
    )

    assert [item.rank for item in selection.results] == [1, 3]
    assert selection.diagnostics.query_intent == "comparison_or_conflict"


def test_selector_rewards_passages_that_cover_the_question_topic() -> None:
    candidates = (
        _result(
            1,
            text="The rear spring installation uses the approved fastener.",
            score=0.90,
            source_digit="1",
        ),
        _result(
            2,
            text="Brake balance adjustment is made with the cockpit wheel.",
            score=0.82,
            source_digit="2",
        ),
    )

    selection = select_evidence(
        "Explain brake balance adjustment",
        candidates,
        limit=1,
    )

    assert [item.rank for item in selection.results] == [2]
    assert selection.diagnostics.policy == "facet_topic_mmr_scope_v3"


def test_decomposer_extracts_explicit_operating_summary_facets() -> None:
    query = (
        "For the 992.1 N3 and N3R tyres, build a practical operating summary "
        "covering tyre dimensions, recommended wheel widths, minimum cold "
        "pressures, shoulder-temperature balance, and what recommendation "
        "applies at unlisted tracks."
    )

    facets = decompose_query_facets(query)

    assert [facet.facet_id for facet in facets] == ["F1", "F2", "F3", "F4", "F5"]
    assert [facet.label for facet in facets] == [
        "tyre dimensions",
        "recommended wheel widths",
        "minimum cold pressures",
        "shoulder-temperature balance",
        "recommendation applies at unlisted tracks",
    ]
    # The subject names the tyres, so every facet search carries them.
    assert facets[0].retrieval_query == "992.1 n3 n3r tyre dimension"
    assert facets[2].retrieval_query == "992.1 n3 n3r minimum cold pressure"
    assert facets[-1].retrieval_query == (
        "992.1 n3 n3r recommendation apply unlisted track"
    )


def test_a_list_marker_splits_two_topics() -> None:
    """A two-item list is as much an enumeration as a three-item one."""

    facets = decompose_query_facets(
        "Summarise the rules including qualifying format and track limits"
    )

    assert [facet.label for facet in facets] == ["qualifying format", "track limits"]


def test_a_bare_conjunction_splits_two_substantial_topics() -> None:
    facets = decompose_query_facets(
        "What are the tyre pressures and camber settings for the 992.2?"
    )

    assert [facet.label for facet in facets] == [
        "tyre pressures",
        "camber settings for the 992.2",
    ]
    assert [facet.retrieval_query for facet in facets] == [
        "992.2 tyre pressure",
        "992.2 camber setting",
    ]


@pytest.mark.parametrize(
    "query",
    (
        # One quantity, described by two adjectives.
        "What is the maximum temperature difference between the inside and "
        "outside shoulder?",
        "What are the front and rear ride heights?",
        # "and" joins the two sides of a comparison, not two topics.
        "Compare the 2025 and 2026 minimum weight regulations",
        "Compare the qualifying-lap requirements in the PCC Great Britain and "
        "PCC Asia regulations",
    ),
)
def test_a_conjunction_inside_one_topic_is_not_a_list(query: str) -> None:
    assert decompose_query_facets(query) == ()


def test_plurals_fold_without_a_hand_written_word_list() -> None:
    facets = decompose_query_facets(
        "Summarise the rules including starting procedures, tyre pressures, "
        "and track-limits penalties"
    )

    assert [facet.retrieval_query for facet in facets] == [
        "starting procedure",
        "tyre pressure",
        "track limit penalty",
    ]


def test_facet_queries_do_not_inject_values_from_a_known_answer() -> None:
    facets = decompose_query_facets(
        "For the 991.2 X7 and X7R tyres, provide a summary covering tyre "
        "dimensions, recommended wheel widths, and minimum cold pressures."
    )

    assert [facet.retrieval_query for facet in facets] == [
        "991.2 x7 x7r tyre dimension",
        "991.2 x7 x7r recommended wheel width",
        "991.2 x7 x7r minimum cold pressure",
    ]
    assert all("12 j 18" not in facet.retrieval_query for facet in facets)
    assert all("13 j 18" not in facet.retrieval_query for facet in facets)


def test_pressure_evidence_diversity_is_not_fixed_to_18_inch_rims() -> None:
    facet = QueryFacet(
        facet_id="F1",
        label="minimum cold pressures",
        retrieval_query="x7 x7r minimum cold pressure start pressure ambient",
        evidence_target=2,
    )
    candidates = (
        _result(
            1,
            text="For a 10 J x 17 rim, use the listed cold pressure.",
            score=0.9,
            source_digit="1",
        ),
        _result(
            2,
            text="A second note for the same 10 J x 17 rim.",
            score=0.89,
            source_digit="1",
        ),
        _result(
            3,
            text="For an 11 J 19 rim, use its listed cold pressure.",
            score=0.88,
            source_digit="1",
        ),
    )

    selection = select_evidence(
        "Compare the minimum cold pressures",
        candidates,
        limit=2,
        requested_facets=(facet,),
        facet_candidate_ids={
            facet.label: tuple(item.citation.chunk_id for item in candidates)
        },
    )

    assert [item.rank for item in selection.results] == [1, 3]


def test_regulation_comparison_facets_use_intent_not_answer_values() -> None:
    facets = decompose_query_facets(
        "Compare PCC Great Britain and PCC Asia regulations, covering "
        "qualifying format, starting procedures, and track-limits penalties"
    )

    assert [facet.retrieval_query for facet in facets] == [
        "qualifying format",
        "starting procedure",
        "track limit penalty",
    ]


def test_comparison_selects_each_facet_from_each_requested_scope() -> None:
    facets = decompose_query_facets(
        "Compare Series A and Series B rules, covering qualifying format, "
        "starting procedures, and track-limits penalties"
    )
    candidates = tuple(
        _result(
            rank,
            text=f"{scope} {facet.label} rule.",
            score=1 - rank / 100,
            source_digit=str(rank),
            championship=scope,
        )
        for rank, (facet, scope) in enumerate(
            (
                (facets[0], "Series A"),
                (facets[0], "Series B"),
                (facets[1], "Series A"),
                (facets[1], "Series B"),
                (facets[2], "Series A"),
                (facets[2], "Series B"),
            ),
            start=1,
        )
    )
    facet_candidate_ids = {
        facet.label: tuple(
            item.citation.chunk_id
            for item in candidates
            if facet.label in item.evidence_text
        )
        for facet in facets
    }

    selection = select_evidence(
        "Compare Series A and Series B qualifying, starts, and track limits",
        candidates,
        limit=8,
        required_scopes=("Series A", "Series B"),
        requested_facets=facets,
        facet_candidate_ids=facet_candidate_ids,
    )

    for facet in facets:
        selected_scopes = {
            item.source_metadata["championship"]
            for item in selection.results
            if item.citation.chunk_id in facet_candidate_ids[facet.label]
        }
        assert selected_scopes == {"Series A", "Series B"}


def test_selector_guarantees_same_source_coverage_for_every_requested_facet() -> None:
    query = (
        "For the 992.1 N3 and N3R tyres, build a practical operating summary "
        "covering tyre dimensions, recommended wheel widths, minimum cold "
        "pressures, shoulder-temperature balance, and what recommendation "
        "applies at unlisted tracks."
    )
    facets = decompose_query_facets(query)
    candidates = (
        _result(
            1,
            text="N3 is 30/65-18 and N3R is 31/71-18.",
            score=0.88,
            source_digit="1",
        ),
        _result(
            2,
            text="The recommended wheel widths are 12 J 18 and 13 J 18.",
            score=0.87,
            source_digit="1",
        ),
        _result(
            3,
            text="The minimum cold pressures are 1.2 bar or 17.4 psi.",
            score=0.86,
            source_digit="1",
        ),
        _result(
            4,
            text="Shoulder temperature balance must be less than 20 C after a run.",
            score=0.85,
            source_digit="1",
        ),
        _result(
            5,
            text="At unlisted tracks apply the STANDARD recommendation.",
            score=0.84,
            source_digit="1",
        ),
    )

    selection = select_evidence(
        query,
        candidates,
        limit=5,
        requested_facets=facets,
        facet_candidate_ids={
            facet.label: (candidate.citation.chunk_id,)
            for facet, candidate in zip(facets, candidates, strict=True)
        },
        max_per_source=1,
    )

    assert [item.rank for item in selection.results] == [1, 2, 3, 4, 5]
    assert selection.diagnostics.covered_facets == tuple(
        facet.label for facet in facets
    )
    assert selection.diagnostics.missing_facets == ()


def test_comparison_balances_evidence_across_required_scopes() -> None:
    candidates = (
        _result(
            1,
            text="Series A start rule one.",
            score=0.99,
            source_digit="1",
            championship="Series A",
        ),
        _result(
            2,
            text="Series A start rule two.",
            score=0.98,
            source_digit="1",
            championship="Series A",
        ),
        _result(
            3,
            text="Series A start rule three.",
            score=0.97,
            source_digit="1",
            championship="Series A",
        ),
        _result(
            4,
            text="Series B start rule one.",
            score=0.80,
            source_digit="2",
            championship="Series B",
        ),
        _result(
            5,
            text="Series B start rule two.",
            score=0.79,
            source_digit="2",
            championship="Series B",
        ),
    )

    selection = select_evidence(
        "differences between Series A and Series B",
        candidates,
        limit=4,
        required_scopes=("Series A", "Series B"),
    )

    assert [item.source_metadata["championship"] for item in selection.results] == [
        "Series A",
        "Series A",
        "Series B",
        "Series B",
    ]


def test_broad_championship_comparison_requires_a_rule_area() -> None:
    candidates = (
        _result(
            1,
            text="Great Britain qualifying rule.",
            score=0.92,
            source_digit="1",
            championship="PCC Great Britain",
        ),
        _result(
            2,
            text="Asia qualifying rule.",
            score=0.91,
            source_digit="2",
            championship="PCC Asia",
        ),
    )

    selection = select_evidence(
        "Race rule differences between Great Britain and Asia",
        candidates,
        limit=4,
        required_scopes=("PCC Great Britain", "PCC Asia"),
    )

    assert selection.sufficient is False
    assert selection.diagnostics.reason == "comparison_topic_too_broad"


def test_specific_championship_comparison_can_generate() -> None:
    candidates = (
        _result(
            1,
            text="Great Britain qualifying rule.",
            score=0.92,
            source_digit="1",
            championship="PCC Great Britain",
        ),
        _result(
            2,
            text="Asia qualifying rule.",
            score=0.91,
            source_digit="2",
            championship="PCC Asia",
        ),
    )

    selection = select_evidence(
        "Qualifying lap requirements in Great Britain versus Asia",
        candidates,
        limit=4,
        required_scopes=("PCC Great Britain", "PCC Asia"),
    )

    assert selection.sufficient is True
    assert selection.diagnostics.reason == "selected"


def test_calibrated_threshold_marks_weak_evidence_insufficient() -> None:
    candidate = _result(
        1,
        text="A vaguely related setup note.",
        score=0.42,
        source_digit="1",
    )

    selection = select_evidence(
        "What is the required pressure?",
        (candidate,),
        limit=1,
        minimum_reranker_score=0.8,
    )

    assert selection.results == (candidate,)
    assert selection.sufficient is False
    assert selection.diagnostics.reason == "below_calibrated_threshold"


def test_comparison_requires_evidence_for_every_resolved_scope() -> None:
    candidate = _result(
        1,
        text="Series A requires a rolling start.",
        score=0.92,
        source_digit="1",
        championship="Series A",
    )

    selection = select_evidence(
        "compare Series A and Series B",
        (candidate,),
        limit=4,
        required_scopes=("Series A", "Series B"),
    )

    assert selection.sufficient is False
    assert selection.diagnostics.covered_scopes == ("Series A",)
    assert selection.diagnostics.reason == "missing_required_scope"
