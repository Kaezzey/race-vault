from __future__ import annotations

from racevault.lexical.mapping import INDEX_SCHEMA_VERSION, index_definition


def test_index_mapping_is_strict_and_versioned() -> None:
    definition = index_definition()
    mappings = definition["mappings"]

    assert isinstance(mappings, dict)
    assert mappings["dynamic"] == "strict"
    assert mappings["_meta"] == {
        "racevault_schema_version": INDEX_SCHEMA_VERSION
    }
    properties = mappings["properties"]
    assert isinstance(properties, dict)
    assert properties["contextual_text"]["analyzer"] == "racevault_technical"
    assert properties["evidence_text"]["index"] is False
    assert properties["provenance"]["enabled"] is False
