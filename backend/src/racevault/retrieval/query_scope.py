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
        "between",
        "compare",
        "compared",
        "difference",
        "differences",
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


def _championship_aliases(championship: str) -> tuple[str, ...]:
    """Return exact natural-language aliases for a catalogue championship."""

    canonical = _normalize(championship)
    aliases = [canonical]
    if canonical.startswith("pcc "):
        aliases.append(canonical.removeprefix("pcc "))
    return tuple(aliases)


def resolve_query_filter_scopes(
    query: str,
    filters: SearchFilters,
    *,
    championships: Iterable[str],
    vehicle_generations: Iterable[str] = (),
) -> tuple[SearchFilters, ...]:
    """Return one pre-filter scope for each championship named by the query.

    Explicit API filters take precedence. Unscoped queries retain their
    original filters.
    """

    normalized_query = f" {_normalize(query)} "
    resolved_filters = filters
    if filters.vehicle_generation is None:
        vehicle_matches = tuple(
            generation
            for generation in vehicle_generations
            if f" {_normalize(generation)} " in normalized_query
        )
        if len(vehicle_matches) == 1:
            resolved_filters = filters.model_copy(
                update={"vehicle_generation": vehicle_matches[0]}
            )
    if resolved_filters.season is None:
        season_matches = tuple(
            dict.fromkeys(
                int(value)
                for value in re.findall(
                    r"(?<!\d)(20[0-9]{2})(?!\d)",
                    query,
                )
            )
        )
        if len(season_matches) == 1:
            resolved_filters = resolved_filters.model_copy(
                update={"season": season_matches[0]}
            )
    if resolved_filters.championship is not None:
        return (resolved_filters,)
    available = tuple(championships)
    alias_owners: dict[str, set[str]] = {}
    for championship in available:
        for alias in _championship_aliases(championship):
            alias_owners.setdefault(alias, set()).add(championship)

    matches = []
    for championship in available:
        positions = [
            (normalized_query.index(f" {alias} "), -len(alias))
            for alias in _championship_aliases(championship)
            if len(alias_owners[alias]) == 1
            and f" {alias} " in normalized_query
        ]
        if positions:
            position, _ = min(positions)
            matches.append((position, championship))
    matches.sort(key=lambda item: item[0])
    if not matches:
        return (resolved_filters,)
    return tuple(
        resolved_filters.model_copy(update={"championship": championship})
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
        aliases = (
            _championship_aliases(scope.championship)
            if scope.championship is not None
            else ()
        )
        if scope.vehicle_generation is not None:
            aliases = (*aliases, _normalize(scope.vehicle_generation))
        if scope.season is not None:
            aliases = (*aliases, str(scope.season))
        for alias in aliases:
            words = alias.split()
            pattern = (
                r"\b"
                + r"[\W_]+".join(re.escape(word) for word in words)
                + r"\b"
            )
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
