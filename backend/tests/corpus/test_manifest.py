from __future__ import annotations

from pathlib import Path

import pytest

from racevault.corpus.manifest import discover_manifest, validate_manifest_coverage
from racevault.corpus.models import CorpusDocument, CorpusManifest


def test_discovery_assigns_safe_metadata_and_stable_roles(tmp_path: Path) -> None:
    source = tmp_path / "Tyre Data" / "992.2" / "N4_2026.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pdf")

    first = discover_manifest(tmp_path)
    second = discover_manifest(tmp_path)

    assert first == second
    assert first.documents[0].document_type.value == "tyre_data"
    assert first.documents[0].authority == "component_supplier_document"
    assert first.documents[0].vehicle_generation == "992.2"
    assert first.documents[0].season == 2026
    assert validate_manifest_coverage(first, tmp_path) == (source.resolve(),)


def test_manifest_rejects_duplicate_paths() -> None:
    document = CorpusDocument(
        role="one",
        path="Manual.pdf",
        document_type="component_manual",
        authority="component_supplier_document",
    )
    duplicate = document.model_copy(update={"role": "two"})

    with pytest.raises(ValueError, match="paths must be unique"):
        CorpusManifest(documents=(document, duplicate))


def test_coverage_rejects_undeclared_pdf(tmp_path: Path) -> None:
    (tmp_path / "extra.pdf").write_bytes(b"pdf")
    manifest = CorpusManifest(
        documents=(
            CorpusDocument(
                role="manual",
                path="manual.pdf",
                document_type="component_manual",
                authority="component_supplier_document",
            ),
        )
    )

    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_manifest_coverage(manifest, tmp_path)


def test_discovery_does_not_treat_download_folder_as_season(
    tmp_path: Path,
) -> None:
    source = tmp_path / "PMRSI Other" / "2026-08-10_PA10" / "manual.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pdf")

    manifest = discover_manifest(tmp_path)

    assert manifest.documents[0].season is None


def test_discovery_reads_championship_from_regulation_path(tmp_path: Path) -> None:
    source = (
        tmp_path
        / "Rules and Regulations"
        / "Other"
        / "PCC France"
        / "2026 Regulations.pdf"
    )
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pdf")

    document = discover_manifest(tmp_path).documents[0]

    assert document.championship == "PCC France"
    assert document.season == 2026
