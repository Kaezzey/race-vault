"""Resolve the current edition of a versioned championship document set.

A motorsport corpus keeps superseded regulations alongside the current ones.
An unqualified question is almost always about the edition in force, so a
resolved championship scope is narrowed to its newest season and revision
before retrieval runs.

Narrowing is deliberately conservative. A filter is only applied when the
catalogue proves it cannot hide evidence: every edition in scope must carry the
field, and the field must actually distinguish between editions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import Field

from racevault.extraction.models import ArtifactModel
from racevault.retrieval.models import SearchFilters

# Accepts curated shorthand ("V1", "Rev.3") as well as derived labels.
_VERSION_NUMBER = re.compile(
    r"^(?:v|ver|version|rev|revision|issue|amendment)[\s.\-_]*(\d+)$",
    re.IGNORECASE,
)
_NAMED_REVISION_ORDER = ("draft", "provisional", "final")


class DocumentEdition(ArtifactModel):
    """One catalogued (championship, season, revision) combination."""

    championship: str
    season: int | None = Field(default=None, ge=1900, le=2200)
    revision: str | None = None


def revision_order(revision: str | None) -> tuple[int, int]:
    """Return a total order over revision labels, oldest first."""

    if revision is None:
        return (0, 0)
    match = _VERSION_NUMBER.match(revision.strip())
    if match is not None:
        return (2, int(match.group(1)))
    normalized = revision.strip().casefold()
    if normalized in _NAMED_REVISION_ORDER:
        return (1, _NAMED_REVISION_ORDER.index(normalized))
    return (1, -1)


def resolve_latest_edition(
    filters: SearchFilters,
    editions: Iterable[DocumentEdition],
) -> SearchFilters:
    """Narrow a championship scope to the newest edition the catalogue holds."""

    if filters.championship is None:
        return filters
    in_championship = tuple(
        edition
        for edition in editions
        if edition.championship == filters.championship
    )
    if not in_championship:
        return filters

    resolved = filters
    if resolved.season is None:
        seasons = [edition.season for edition in in_championship]
        known = [season for season in seasons if season is not None]
        if len(known) == len(seasons) and len(set(known)) > 1:
            resolved = resolved.model_copy(update={"season": max(known)})

    if resolved.revision is not None:
        return resolved
    in_season = tuple(
        edition
        for edition in in_championship
        if resolved.season is None or edition.season == resolved.season
    )
    revisions = {edition.revision for edition in in_season}
    if None in revisions or len(revisions) <= 1:
        return resolved
    return resolved.model_copy(
        update={"revision": max(revisions, key=revision_order)}
    )
