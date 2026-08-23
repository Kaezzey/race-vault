from __future__ import annotations

from racevault.lexical.mapping import INDEX_SCHEMA_VERSION, index_definition
from racevault.lexical.synonyms import MOTORSPORT_SYNONYMS


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


def test_prose_fields_expand_synonyms_only_at_search_time() -> None:
    """Search-time expansion lets the vocabulary grow without reindexing."""

    properties = index_definition()["mappings"]["properties"]

    for field in ("contextual_text", "section_text", "source_filename"):
        assert properties[field]["analyzer"] == "racevault_technical"
        assert properties[field]["search_analyzer"] == "racevault_technical_search"
        # Identifier sub-fields stay literal: a part number has no synonym.
        assert properties[field]["fields"]["codes"]["analyzer"] == "racevault_codes"


def test_regulation_modal_verbs_survive_analysis() -> None:
    """"shall" and "should" carry the obligation, so no stop filter is used."""

    analyzers = index_definition()["settings"]["analysis"]["analyzer"]

    for name in ("racevault_technical", "racevault_technical_search"):
        assert "stop" not in analyzers[name]["filter"]
        assert "kstem" in analyzers[name]["filter"]


def test_synonym_groups_never_share_a_term() -> None:
    """A term in two groups would drag both meanings into every query."""

    owners: dict[str, str] = {}
    for group in MOTORSPORT_SYNONYMS:
        for term in (item.strip() for item in group.split(",")):
            assert term, group
            assert term not in owners, f"{term!r} in {owners.get(term)!r} and {group!r}"
            owners[term] = group
