from __future__ import annotations

from racevault.semantic.store import FILTER_SQL


def test_semantic_store_defines_every_supported_filter() -> None:
    assert set(FILTER_SQL) == {
        "source_sha256",
        "source_role",
        "document_class",
        "authority",
        "vehicle_generation",
        "championship",
        "season",
        "revision",
        "page_number",
        "chunk_kind",
        "oversize",
    }
    assert FILTER_SQL["page_number"] == (
        "c.page_numbers @> ARRAY[%s]::smallint[]"
    )
