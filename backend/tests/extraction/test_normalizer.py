from __future__ import annotations

from typing import Any

from racevault.extraction.normalizer import normalize_docling

SOURCE_SHA256 = "a" * 64


def _prov(page: int) -> list[dict[str, Any]]:
    return [
        {
            "page_no": page,
            "bbox": {
                "l": 10,
                "t": 20,
                "r": 30,
                "b": 40,
                "coord_origin": "TOPLEFT",
            },
            "charspan": [0, 4],
        }
    ]


def test_normalizer_preserves_order_sections_tables_and_provenance() -> None:
    document = {
        "body": {
            "children": [
                {"$ref": "#/texts/0"},
                {"$ref": "#/groups/0"},
                {"$ref": "#/tables/0"},
            ]
        },
        "furniture": {"children": []},
        "groups": [
            {
                "self_ref": "#/groups/0",
                "children": [
                    {"$ref": "#/texts/1"},
                    {"$ref": "#/texts/2"},
                ],
            }
        ],
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "title",
                "text": "Manual",
                "content_layer": "body",
                "prov": _prov(1),
            },
            {
                "self_ref": "#/texts/1",
                "label": "section_header",
                "level": 2,
                "text": "Brakes",
                "content_layer": "body",
                "prov": _prov(2),
            },
            {
                "self_ref": "#/texts/2",
                "label": "text",
                "text": "Set the pressure.",
                "content_layer": "body",
                "prov": _prov(2),
            },
        ],
        "tables": [
            {
                "self_ref": "#/tables/0",
                "label": "table",
                "content_layer": "body",
                "prov": _prov(2),
                "data": {
                    "num_rows": 2,
                    "num_cols": 2,
                    "table_cells": [
                        {
                            "start_row_offset_idx": 0,
                            "end_row_offset_idx": 1,
                            "start_col_offset_idx": 0,
                            "end_col_offset_idx": 1,
                            "text": "Axle",
                            "column_header": True,
                        },
                        {
                            "start_row_offset_idx": 0,
                            "end_row_offset_idx": 1,
                            "start_col_offset_idx": 1,
                            "end_col_offset_idx": 2,
                            "text": "Pressure",
                            "column_header": True,
                        },
                        {
                            "start_row_offset_idx": 1,
                            "end_row_offset_idx": 2,
                            "start_col_offset_idx": 0,
                            "end_col_offset_idx": 1,
                            "text": "Front",
                        },
                        {
                            "start_row_offset_idx": 1,
                            "end_row_offset_idx": 2,
                            "start_col_offset_idx": 1,
                            "end_col_offset_idx": 2,
                            "text": "2.0 bar",
                        },
                    ],
                },
            }
        ],
        "pictures": [],
        "key_value_items": [],
        "form_items": [],
    }

    elements, tables = normalize_docling(document, SOURCE_SHA256)

    assert [element.label for element in elements] == [
        "title",
        "section_header",
        "text",
        "table",
    ]
    assert elements[2].section_path == ("Manual", "Brakes")
    assert elements[2].provenance[0].page_number == 2
    assert elements[3].text == "Axle\tPressure\nFront\t2.0 bar"
    assert elements[3].table_id == tables[0].table_id
    assert tables[0].row_count == 2
    assert tables[0].column_count == 2
    assert tables[0].cells[0].is_column_header is True


def test_normalizer_ids_are_stable() -> None:
    document = {
        "body": {"children": [{"$ref": "#/texts/0"}]},
        "furniture": {"children": []},
        "texts": [
            {
                "self_ref": "#/texts/0",
                "label": "text",
                "text": "Stable",
                "content_layer": "body",
                "prov": _prov(1),
            }
        ],
        "tables": [],
        "pictures": [],
        "groups": [],
        "key_value_items": [],
        "form_items": [],
    }

    first, _ = normalize_docling(document, SOURCE_SHA256)
    second, _ = normalize_docling(document, SOURCE_SHA256)

    assert first[0].element_id == second[0].element_id

