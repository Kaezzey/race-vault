"""Normalize a Docling document into stable RaceVault evidence records."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from racevault.extraction.models import (
    BoundingBox,
    ElementArtifact,
    ProvenanceRef,
    TableArtifact,
    TableCell,
)


def _stable_id(prefix: str, source_sha256: str, docling_ref: str) -> str:
    value = f"{source_sha256}:{docling_ref}".encode()
    return f"{prefix}_{hashlib.sha256(value).hexdigest()[:32]}"


def _bbox(value: Mapping[str, Any] | None) -> BoundingBox | None:
    if not value:
        return None
    return BoundingBox(
        left=round(float(value["l"]), 6),
        top=round(float(value["t"]), 6),
        right=round(float(value["r"]), 6),
        bottom=round(float(value["b"]), 6),
        coordinate_origin=str(value.get("coord_origin", "UNKNOWN")),
    )


def _provenance(item: Mapping[str, Any]) -> tuple[ProvenanceRef, ...]:
    references: list[ProvenanceRef] = []
    for value in item.get("prov", []):
        bbox = _bbox(value.get("bbox"))
        if bbox is None:
            continue
        charspan = value.get("charspan")
        references.append(
            ProvenanceRef(
                page_number=int(value["page_no"]),
                bbox=bbox,
                char_start=int(charspan[0]) if charspan else None,
                char_end=int(charspan[1]) if charspan else None,
            )
        )
    return tuple(references)


def _build_index(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    collection_names = (
        "texts",
        "tables",
        "pictures",
        "groups",
        "key_value_items",
        "form_items",
    )
    for collection_name in collection_names:
        collection = document.get(collection_name, [])
        if not isinstance(collection, Sequence) or isinstance(collection, str):
            continue
        for item in collection:
            if isinstance(item, Mapping) and "self_ref" in item:
                index[str(item["self_ref"])] = item
    return index


def _walk_children(
    root: Mapping[str, Any] | None,
    index: Mapping[str, Mapping[str, Any]],
    active: set[str] | None = None,
) -> Iterator[Mapping[str, Any]]:
    if root is None:
        return
    active_refs = set() if active is None else active
    for reference in root.get("children", []):
        if not isinstance(reference, Mapping) or "$ref" not in reference:
            continue
        ref = str(reference["$ref"])
        if ref in active_refs:
            raise ValueError(f"cycle in Docling document at {ref}")
        item = index.get(ref)
        if item is None:
            raise ValueError(f"unresolved Docling reference: {ref}")
        if ref.startswith("#/groups/"):
            yield from _walk_children(item, index, active_refs | {ref})
        else:
            yield item


def _table_cells(item: Mapping[str, Any]) -> tuple[TableCell, ...]:
    cells: list[TableCell] = []
    data = item.get("data", {})
    for cell in data.get("table_cells", []):
        cells.append(
            TableCell(
                row_start=int(cell["start_row_offset_idx"]),
                row_end=int(cell["end_row_offset_idx"]),
                column_start=int(cell["start_col_offset_idx"]),
                column_end=int(cell["end_col_offset_idx"]),
                text=str(cell.get("text", "")).strip(),
                is_column_header=bool(cell.get("column_header", False)),
                is_row_header=bool(cell.get("row_header", False)),
                bbox=_bbox(cell.get("bbox")),
            )
        )
    return tuple(cells)


def _table_text(cells: Sequence[TableCell]) -> str:
    if not cells:
        return ""
    row_count = max(cell.row_end for cell in cells)
    column_count = max(cell.column_end for cell in cells)
    rows = [["" for _ in range(column_count)] for _ in range(row_count)]
    for cell in cells:
        rows[cell.row_start][cell.column_start] = cell.text
    return "\n".join("\t".join(row).rstrip() for row in rows).strip()


def normalize_docling(
    document: Mapping[str, Any], source_sha256: str
) -> tuple[tuple[ElementArtifact, ...], tuple[TableArtifact, ...]]:
    index = _build_index(document)
    ordered_items = list(_walk_children(document.get("body"), index))
    ordered_items.extend(_walk_children(document.get("furniture"), index))

    elements: list[ElementArtifact] = []
    tables: list[TableArtifact] = []
    section_levels: dict[int, str] = {}

    for reading_order, item in enumerate(ordered_items):
        ref = str(item["self_ref"])
        label = str(item.get("label", "unknown"))
        text = str(item.get("text", "")).strip()
        heading_level: int | None = None

        if label == "title" and text:
            heading_level = 1
            section_levels = {1: text}
        elif label == "section_header" and text:
            heading_level = int(item.get("level", 1))
            section_levels = {
                level: heading
                for level, heading in section_levels.items()
                if level < heading_level
            }
            section_levels[heading_level] = text

        section_path = tuple(
            heading for _, heading in sorted(section_levels.items())
        )
        table_id: str | None = None

        if label == "table":
            table_id = _stable_id("tbl", source_sha256, ref)
            cells = _table_cells(item)
            text = _table_text(cells)
            data = item.get("data", {})
            tables.append(
                TableArtifact(
                    table_id=table_id,
                    docling_ref=ref,
                    reading_order=reading_order,
                    section_path=section_path,
                    row_count=int(data.get("num_rows", 0)),
                    column_count=int(data.get("num_cols", 0)),
                    cells=cells,
                    provenance=_provenance(item),
                )
            )

        elements.append(
            ElementArtifact(
                element_id=_stable_id("el", source_sha256, ref),
                docling_ref=ref,
                label=label,
                content_layer=str(item.get("content_layer", "body")),
                reading_order=reading_order,
                text=text,
                heading_level=heading_level,
                section_path=section_path,
                provenance=_provenance(item),
                table_id=table_id,
            )
        )

    return tuple(elements), tuple(tables)

