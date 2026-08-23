"""Full-corpus manifest loading, discovery, and coverage validation."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from racevault.chunking.models import DocumentClass
from racevault.corpus.models import CorpusDocument, CorpusManifest
from racevault.extraction.io import load_json


def load_manifest(path: Path) -> CorpusManifest:
    return CorpusManifest.model_validate(load_json(path))


def validate_manifest_coverage(
    manifest: CorpusManifest, corpus_root: Path
) -> tuple[Path, ...]:
    root = corpus_root.resolve()
    declared = {item.path.casefold() for item in manifest.documents}
    discovered = {
        item.relative_to(root).as_posix().casefold()
        for item in root.rglob("*.pdf")
        if item.is_file()
    }
    missing = sorted(discovered - declared)
    extra = sorted(declared - discovered)
    if missing or extra:
        raise ValueError(
            f"manifest coverage mismatch; missing={missing}, extra={extra}"
        )
    return tuple(root / item.path for item in manifest.documents)


def _document_type(path: str) -> DocumentClass:
    prefix = path.casefold().split("/", 1)[0]
    mapping = {
        "abs": DocumentClass.COMPONENT_MANUAL,
        "cosworth": DocumentClass.COMPONENT_MANUAL,
        "ecu": DocumentClass.COMPONENT_MANUAL,
        "part catalogues": DocumentClass.PART_CATALOGUE,
        "pmrsi other": DocumentClass.COMPONENT_MANUAL,
        "porsche technical manuals": DocumentClass.TECHNICAL_MANUAL,
        "rules and regulations": DocumentClass.REGULATION,
        "tyre data": DocumentClass.TYRE_DATA,
    }
    return mapping.get(prefix, DocumentClass.UNKNOWN)


def _authority(document_type: DocumentClass, path: str) -> str:
    if document_type is DocumentClass.REGULATION:
        return "official_regulation"
    if document_type in {DocumentClass.TECHNICAL_MANUAL, DocumentClass.PART_CATALOGUE}:
        return "manufacturer_document"
    if path.casefold().startswith("pmrsi other/"):
        return "manufacturer_document"
    if document_type in {
        DocumentClass.COMPONENT_MANUAL,
        DocumentClass.TYRE_DATA,
    }:
        return "component_supplier_document"
    return "unknown"


def _season(path: str, document_type: DocumentClass) -> int | None:
    if document_type not in {
        DocumentClass.REGULATION,
        DocumentClass.TYRE_DATA,
        DocumentClass.PART_CATALOGUE,
    }:
        return None
    matches = re.findall(r"(?<!\d)(20(?:2[0-9]))(?!\d)", path)
    return int(matches[-1]) if matches else None


_REVISION_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])"
    r"(?:(?P<keyword>v|ver|version|rev|revision|issue|amendment)"
    r"[^a-z0-9]{0,2}(?P<number>\d{1,2})"
    r"|(?P<named>final|draft|provisional))"
    r"(?=$|[^a-z0-9])",
    re.IGNORECASE,
)
_VERSIONED_TYPES = {
    DocumentClass.REGULATION,
    DocumentClass.TYRE_DATA,
    DocumentClass.PART_CATALOGUE,
}


def _revision(path: str, document_type: DocumentClass) -> str | None:
    """Derive a comparable edition label from a versioned document filename."""

    if document_type not in _VERSIONED_TYPES:
        return None
    filename = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    match = _REVISION_PATTERN.search(stem)
    if match is None:
        return None
    if match.group("number") is not None:
        return f"Version {int(match.group('number'))}"
    named = match.group("named")
    return named[:1].upper() + named[1:].lower()


def _vehicle_generation(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if "/992.1/" in f"/{normalized}/" or "992.1 Technical" in normalized:
        return "992.1"
    if "/992.2/" in f"/{normalized}/" or "992.2 Technical" in normalized:
        return "992.2"
    return None


def _championship(path: str, document_type: DocumentClass) -> str | None:
    if document_type is not DocumentClass.REGULATION:
        return None
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 4 and parts[1].casefold() == "other":
        return parts[2]
    return parts[1] if len(parts) >= 3 else None


def discover_manifest(corpus_root: Path) -> CorpusManifest:
    root = corpus_root.resolve()
    documents = []
    sources = sorted(
        root.rglob("*.pdf"), key=lambda item: item.as_posix().casefold()
    )
    for source in sources:
        path = source.relative_to(root).as_posix()
        document_type = _document_type(path)
        role_hash = hashlib.sha256(path.encode()).hexdigest()[:16]
        documents.append(
            CorpusDocument(
                role=f"document_{role_hash}",
                path=path,
                document_type=document_type,
                authority=_authority(document_type, path),
                vehicle_generation=_vehicle_generation(path),
                championship=_championship(path, document_type),
                season=_season(path, document_type),
                revision=_revision(path, document_type),
            )
        )
    return CorpusManifest(corpus_root=corpus_root.name, documents=tuple(documents))


def apply_curated_metadata(
    manifest: CorpusManifest, curated_path: Path
) -> CorpusManifest:
    raw: dict[str, Any] = load_json(curated_path)
    curated = {
        str(item["path"]).replace("\\", "/").casefold(): item
        for item in raw["documents"]
    }
    documents = []
    for document in manifest.documents:
        override = curated.get(document.path.casefold())
        if override is None:
            documents.append(document)
            continue
        values = document.model_dump()
        values.update(override)
        documents.append(CorpusDocument.model_validate(values))
    return manifest.model_copy(update={"documents": tuple(documents)})
