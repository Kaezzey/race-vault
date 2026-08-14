"""Infer exact metadata scope that is explicitly named in a query."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from racevault.retrieval.models import SearchFilters

_QUERY_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "compare",
        "compared",
        "differ",
        "do",
        "does",
        "each",
        "for",
        "from",
        "how",
        "in",
        "is",
        "like",
        "of",
        "other",
        "something",
        "the",
        "they",
        "to",
        "versus",
        "vs",
        "what",
        "which",
        "with",
    }
)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())


def resolve_query_filter_scopes(
    query: str,
    filters: SearchFilters,
    *,
    championships: Iterable[str],
) -> tuple[SearchFilters, ...]:
    """Return one pre-filter scope for each championship named by the query.

    Explicit API filters take precedence. Unscoped queries retain their
    original filters.
    """

    if filters.championship is not None:
        return (filters,)
    normalized_query = f" {_normalize(query)} "
    matches = sorted(
        (
            (normalized_query.index(f" {_normalize(championship)} "), championship)
            for championship in championships
            if f" {_normalize(championship)} " in normalized_query
        ),
        key=lambda item: item[0],
    )
    if not matches:
        return (filters,)
    return tuple(
        filters.model_copy(update={"championship": championship})
        for _, championship in matches
    )


def remove_query_scope_terms(
    query: str,
    scopes: Iterable[SearchFilters],
) -> str:
    """Remove metadata phrases after they have become database filters."""

    content_query = query
    removed_scope_term = False
    for scope in scopes:
        if scope.championship is None:
            continue
        words = re.findall(r"[A-Za-z0-9]+", scope.championship)
        pattern = r"\b" + r"[\W_]+".join(re.escape(word) for word in words) + r"\b"
        content_query, replacements = re.subn(
            pattern,
            " ",
            content_query,
            flags=re.IGNORECASE,
        )
        removed_scope_term = removed_scope_term or replacements > 0
    if removed_scope_term:
        stop_words = "|".join(
            re.escape(word) for word in sorted(_QUERY_STOP_WORDS, key=len, reverse=True)
        )
        content_query = re.sub(
            rf"\b(?:{stop_words})\b",
            " ",
            content_query,
            flags=re.IGNORECASE,
        )
    content_query = " ".join(content_query.split()).strip(" ,;:-?!")
    return content_query if re.search(r"[A-Za-z0-9]", content_query) else query
