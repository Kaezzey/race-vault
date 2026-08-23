from __future__ import annotations

import pytest

from racevault.chunking.models import DocumentClass
from racevault.corpus.manifest import _revision
from racevault.retrieval.editions import (
    DocumentEdition,
    resolve_latest_edition,
    revision_order,
)
from racevault.retrieval.models import SearchFilters

AUSTRALIA = (
    DocumentEdition(championship="PCC Australia", season=2025, revision="Version 1"),
    DocumentEdition(championship="PCC Australia", season=2026, revision="Version 2"),
)


@pytest.mark.parametrize(
    ("path", "document_type", "expected"),
    (
        (
            "Rules and Regulations/PCC Australia/"
            "2025_Porsche_Carrera_Cup_Australia_Sporting_Technical_Regulations_V1.pdf",
            DocumentClass.REGULATION,
            "Version 1",
        ),
        (
            "Rules and Regulations/PCC Australia/"
            "2026-Porsche-Carrera-Cup-Australia-Regulations-Version-2_260602.pdf",
            DocumentClass.REGULATION,
            "Version 2",
        ),
        (
            "Rules and Regulations/PCC Asia/PCCA 2025 Regulations_Final.pdf",
            DocumentClass.REGULATION,
            "Final",
        ),
        (
            "Rules and Regulations/Other/PCC France/2026 Regulations.pdf",
            DocumentClass.REGULATION,
            None,
        ),
        (
            "Part Catalogues/PA10_0842_911 GT3 Cup MY2021-2025 (992)_CW_11_26.pdf",
            DocumentClass.PART_CATALOGUE,
            None,
        ),
        (
            "ABS/Core/Data_Sheet_70612107_ABS_M5_Kit.pdf",
            DocumentClass.COMPONENT_MANUAL,
            None,
        ),
    ),
)
def test_revision_is_derived_from_versioned_filenames(
    path: str, document_type: DocumentClass, expected: str | None
) -> None:
    assert _revision(path, document_type) == expected


def test_revision_order_places_newer_versions_last() -> None:
    labels = ["Version 10", None, "Final", "Version 2", "Draft"]

    assert sorted(labels, key=revision_order) == [
        None,
        "Draft",
        "Final",
        "Version 2",
        "Version 10",
    ]


def test_revision_order_understands_curated_shorthand() -> None:
    """Curated metadata writes "V1" where derivation writes "Version 1"."""

    assert revision_order("V1") == revision_order("Version 1")
    assert revision_order("Rev.3") == revision_order("Version 3")
    assert revision_order("V1") < revision_order("Version 2")


def test_unqualified_championship_resolves_to_the_newest_season() -> None:
    resolved = resolve_latest_edition(
        SearchFilters(championship="PCC Australia"), AUSTRALIA
    )

    assert resolved.season == 2026


def test_explicit_season_is_never_overridden() -> None:
    resolved = resolve_latest_edition(
        SearchFilters(championship="PCC Australia", season=2025), AUSTRALIA
    )

    assert resolved.season == 2025
    assert resolved.revision is None


def test_superseded_revision_within_one_season_is_excluded() -> None:
    editions = (
        DocumentEdition(championship="PCC Asia", season=2026, revision="Version 1"),
        DocumentEdition(championship="PCC Asia", season=2026, revision="Version 2"),
    )

    resolved = resolve_latest_edition(SearchFilters(championship="PCC Asia"), editions)

    # A single catalogued season needs no filter; the revision does the work.
    assert resolved.season is None
    assert resolved.revision == "Version 2"


def test_partly_labelled_revisions_are_left_unfiltered() -> None:
    """A null revision means the filter could hide evidence, so it is skipped."""

    editions = (
        DocumentEdition(championship="PCC Benelux", season=2025, revision=None),
        DocumentEdition(
            championship="PCC Benelux", season=2025, revision="Version 2"
        ),
    )

    resolved = resolve_latest_edition(
        SearchFilters(championship="PCC Benelux"), editions
    )

    assert resolved.revision is None


def test_partly_labelled_seasons_are_left_unfiltered() -> None:
    editions = (
        DocumentEdition(championship="PCC France", season=None),
        DocumentEdition(championship="PCC France", season=2026),
    )

    resolved = resolve_latest_edition(
        SearchFilters(championship="PCC France"), editions
    )

    assert resolved.season is None


def test_unscoped_query_is_unchanged() -> None:
    filters = SearchFilters(document_class="regulation")

    assert resolve_latest_edition(filters, AUSTRALIA) == filters


def test_unknown_championship_is_unchanged() -> None:
    filters = SearchFilters(championship="PCC Nowhere")

    assert resolve_latest_edition(filters, AUSTRALIA) == filters
