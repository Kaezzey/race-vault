from __future__ import annotations

import pytest

from racevault.lexical.models import LexicalSearchRequest, SearchFilters
from racevault.lexical.query import build_search_body


def test_search_query_uses_bm25_fields_and_exact_filters() -> None:
    body = build_search_body(
        LexicalSearchRequest(
            query="ABS M5",
            limit=5,
            filters=SearchFilters(
                vehicle_generation="992.2",
                season=2026,
                revision="Version 2",
                page_number=8,
            ),
        )
    )

    assert body["size"] == 5
    query = body["query"]
    assert isinstance(query, dict)
    boolean = query["bool"]
    assert isinstance(boolean, dict)
    filters = boolean["filter"]
    assert {"term": {"vehicle_generation": "992.2"}} in filters
    assert {"term": {"season": 2026}} in filters
    assert {"term": {"revision": "Version 2"}} in filters
    assert {"term": {"page_numbers": 8}} in filters
    multi_match = boolean["must"][0]["multi_match"]
    assert "contextual_text.codes^6" in multi_match["fields"]
    assert multi_match["operator"] == "or"


def test_recall_clause_requires_more_than_one_incidental_term() -> None:
    """A long question must not be answered by a single shared common word."""

    body = build_search_body(LexicalSearchRequest(query="what is the joker tyre"))

    recall = body["query"]["bool"]["must"][0]["multi_match"]
    assert recall["minimum_should_match"] == "2<2"


def test_phrase_and_complete_matches_boost_without_narrowing() -> None:
    body = build_search_body(LexicalSearchRequest(query="minimum cold tyre pressure"))

    boolean = body["query"]["bool"]
    should = [clause["multi_match"] for clause in boolean["should"]]
    assert [clause["type"] for clause in should] == ["phrase", "cross_fields"]
    assert all(clause["boost"] > 1 for clause in should)
    # Precision clauses are optional, so they can only reorder the recall set.
    assert len(boolean["must"]) == 1


def test_search_query_rejects_whitespace() -> None:
    with pytest.raises(ValueError, match="query must contain text"):
        LexicalSearchRequest(query="   ")
