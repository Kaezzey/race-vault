"""Type-specific, provenance-aware chunk construction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from racevault.chunking.models import (
    ChunkArtifact,
    ChunkingSettings,
    ChunkKind,
    ChunkStrategy,
    ClassificationArtifact,
)
from racevault.extraction.io import sha256_text
from racevault.extraction.models import (
    ElementArtifact,
    ExtractionArtifact,
    ProvenanceRef,
)

CLAUSE_PATTERN = re.compile(
    r"^\s*([A-Z]\.?\d+(?:\.\d+)*|\d+(?:\.\d+)+)\.?(?=\s|$)"
)
EXCLUDED_LABELS = {"title", "section_header", "picture"}
type BoundaryKey = tuple[object, ...]


@dataclass(frozen=True)
class EvidenceUnit:
    element: ElementArtifact
    clause_reference: str | None
    boundary: BoundaryKey


def _clause_reference(text: str) -> str | None:
    match = CLAUSE_PATTERN.match(text)
    return match.group(1).rstrip(".") if match else None


def _section_clause_reference(section_path: tuple[str, ...]) -> str | None:
    for section in reversed(section_path):
        reference = _clause_reference(section)
        if reference is not None:
            return reference
    return None


def eligible_elements(artifact: ExtractionArtifact) -> tuple[ElementArtifact, ...]:
    return tuple(
        element
        for element in artifact.elements
        if element.content_layer == "body"
        and element.label not in EXCLUDED_LABELS
        and element.text.strip()
        and element.provenance
    )


def _boundary(
    element: ElementArtifact,
    classification: ClassificationArtifact,
    clause_reference: str | None,
) -> BoundaryKey:
    strategy = classification.strategy
    if element.table_id is not None:
        return ("table", element.table_id)
    if strategy is ChunkStrategy.CLAUSE:
        return (element.section_path, clause_reference)
    if strategy is ChunkStrategy.PAGE_TABLE:
        pages = tuple(sorted({item.page_number for item in element.provenance}))
        return (element.section_path, pages)
    return (element.section_path,)


def _units(
    artifact: ExtractionArtifact, classification: ClassificationArtifact
) -> tuple[EvidenceUnit, ...]:
    units: list[EvidenceUnit] = []
    active_clause: str | None = None
    active_section: tuple[str, ...] | None = None
    for element in eligible_elements(artifact):
        if element.section_path != active_section:
            active_clause = (
                _section_clause_reference(element.section_path)
                if classification.strategy is ChunkStrategy.CLAUSE
                else None
            )
            active_section = element.section_path
        detected_clause = (
            _clause_reference(element.text)
            if classification.strategy is ChunkStrategy.CLAUSE
            else None
        )
        if detected_clause is not None:
            active_clause = detected_clause
        units.append(
            EvidenceUnit(
                element=element,
                clause_reference=active_clause,
                boundary=_boundary(element, classification, active_clause),
            )
        )
    return tuple(units)


def _evidence_text(units: tuple[EvidenceUnit, ...]) -> str:
    return "\n\n".join(unit.element.text for unit in units)


def _contextual_text(
    evidence_text: str,
    section_path: tuple[str, ...],
    clause_reference: str | None,
    include_context: bool,
) -> str:
    if not include_context:
        return evidence_text
    context: list[str] = []
    if section_path:
        context.append(f"Section: {' > '.join(section_path)}")
    if clause_reference:
        context.append(f"Clause: {clause_reference}")
    if not context:
        return evidence_text
    return f"{'\n'.join(context)}\n\n{evidence_text}"


def _kind(
    classification: ClassificationArtifact, units: tuple[EvidenceUnit, ...]
) -> ChunkKind:
    if len(units) == 1 and units[0].element.table_id is not None:
        return ChunkKind.TABLE
    return {
        ChunkStrategy.CLAUSE: ChunkKind.CLAUSE,
        ChunkStrategy.SECTION_EVIDENCE: ChunkKind.SECTION,
        ChunkStrategy.PAGE_TABLE: ChunkKind.PAGE,
        ChunkStrategy.HIERARCHICAL_PASSAGE: ChunkKind.PASSAGE,
        ChunkStrategy.GENERIC_EVIDENCE: ChunkKind.EVIDENCE,
    }[classification.strategy]


def _unique_provenance(units: tuple[EvidenceUnit, ...]) -> tuple[ProvenanceRef, ...]:
    seen: set[tuple[object, ...]] = set()
    result: list[ProvenanceRef] = []
    for unit in units:
        for item in unit.element.provenance:
            key = (
                item.page_number,
                item.bbox.left,
                item.bbox.top,
                item.bbox.right,
                item.bbox.bottom,
                item.bbox.coordinate_origin,
                item.char_start,
                item.char_end,
            )
            if key not in seen:
                seen.add(key)
                result.append(item)
    return tuple(result)


def _make_chunk(
    units: tuple[EvidenceUnit, ...],
    ordinal: int,
    source_sha256: str,
    classification: ClassificationArtifact,
    settings: ChunkingSettings,
) -> ChunkArtifact:
    evidence_text = _evidence_text(units)
    section_path = units[0].element.section_path
    clause_reference = units[0].clause_reference
    contextual_text = _contextual_text(
        evidence_text,
        section_path,
        clause_reference,
        settings.include_section_context,
    )
    element_ids = tuple(unit.element.element_id for unit in units)
    table_ids = tuple(
        unit.element.table_id
        for unit in units
        if unit.element.table_id is not None
    )
    provenance = _unique_provenance(units)
    page_numbers = tuple(sorted({item.page_number for item in provenance}))
    identity = "|".join(
        (
            source_sha256,
            settings.strategy_version,
            classification.strategy.value,
            *element_ids,
            sha256_text(contextual_text),
        )
    )
    chunk_id = f"chk_{hashlib.sha256(identity.encode()).hexdigest()[:32]}"
    return ChunkArtifact(
        chunk_id=chunk_id,
        ordinal=ordinal,
        kind=_kind(classification, units),
        strategy=classification.strategy,
        document_class=classification.document_class,
        evidence_text=evidence_text,
        evidence_sha256=sha256_text(evidence_text),
        contextual_text=contextual_text,
        contextual_sha256=sha256_text(contextual_text),
        section_path=section_path,
        clause_reference=clause_reference,
        page_start=page_numbers[0],
        page_end=page_numbers[-1],
        page_numbers=page_numbers,
        element_ids=element_ids,
        table_ids=table_ids,
        provenance=provenance,
        character_count=len(contextual_text),
        oversize=len(contextual_text) > settings.max_characters,
    )


def build_chunks(
    artifact: ExtractionArtifact,
    classification: ClassificationArtifact,
    settings: ChunkingSettings,
) -> tuple[ChunkArtifact, ...]:
    units = _units(artifact, classification)
    groups: list[tuple[EvidenceUnit, ...]] = []
    current: list[EvidenceUnit] = []
    current_boundary: BoundaryKey | None = None

    def flush() -> None:
        nonlocal current, current_boundary
        if current:
            groups.append(tuple(current))
        current = []
        current_boundary = None

    for unit in units:
        if unit.element.table_id is not None:
            flush()
            groups.append((unit,))
            continue

        candidate = tuple([*current, unit])
        candidate_text = _contextual_text(
            _evidence_text(candidate),
            unit.element.section_path,
            unit.clause_reference,
            settings.include_section_context,
        )
        boundary_changed = current_boundary is not None and (
            unit.boundary != current_boundary
        )
        exceeds_limit = bool(current) and len(candidate_text) > settings.max_characters
        if boundary_changed or exceeds_limit:
            flush()
        current.append(unit)
        current_boundary = unit.boundary
    flush()

    return tuple(
        _make_chunk(group, ordinal, artifact.source.sha256, classification, settings)
        for ordinal, group in enumerate(groups)
    )
