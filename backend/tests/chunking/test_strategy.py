from __future__ import annotations

from racevault.chunking.classifier import classify_document
from racevault.chunking.models import ChunkingSettings, ChunkKind
from racevault.chunking.strategy import build_chunks, eligible_elements
from tests.chunking.factories import element, extraction_artifact, table


def test_regulation_chunks_follow_clauses_and_isolate_tables() -> None:
    section = ("Technical Regulations", "Brakes")
    table_record = table(4, page=2, section_path=section)
    elements = (
        element(
            0,
            "Technical Regulations",
            label="section_header",
            section_path=section,
        ),
        element(1, "1.1 Brake cooling is permitted.", section_path=section),
        element(2, "The duct must remain standard.", section_path=section),
        element(3, "1.2 Brake fluid is free.", page=2, section_path=section),
        element(
            4,
            "Pressure",
            page=2,
            label="table",
            section_path=section,
            table_id=table_record.table_id,
        ),
    )
    artifact = extraction_artifact(
        elements,
        document_type="regulation",
        relative_path="Rules and Regulations/rules.pdf",
        tables=(table_record,),
    )

    chunks = build_chunks(
        artifact, classify_document(artifact), ChunkingSettings(max_characters=2400)
    )

    assert [chunk.kind for chunk in chunks] == [
        ChunkKind.CLAUSE,
        ChunkKind.CLAUSE,
        ChunkKind.TABLE,
    ]
    assert chunks[0].clause_reference == "1.1"
    assert chunks[0].element_ids == (elements[1].element_id, elements[2].element_id)
    assert chunks[1].clause_reference == "1.2"
    assert chunks[2].table_ids == (table_record.table_id,)
    assert "Section: Technical Regulations > Brakes" in chunks[0].contextual_text


def test_regulation_detects_section_and_standalone_clause_references() -> None:
    elements = (
        element(1, "Opening text", section_path=("S1.2 Authority",)),
        element(2, "1.2.1", section_path=("S1.2 Authority",)),
        element(3, "Requirement", section_path=("S1.2 Authority",)),
    )
    artifact = extraction_artifact(elements, document_type="regulation")

    chunks = build_chunks(artifact, classify_document(artifact), ChunkingSettings())

    assert [chunk.clause_reference for chunk in chunks] == ["S1.2", "1.2.1"]
    assert chunks[1].evidence_text == "1.2.1\n\nRequirement"


def test_page_table_strategy_does_not_cross_pages() -> None:
    elements = (
        element(1, "Front tyre pressure", page=1),
        element(2, "Rear tyre pressure", page=2),
    )
    artifact = extraction_artifact(elements, document_type="tyre_data")

    chunks = build_chunks(
        artifact, classify_document(artifact), ChunkingSettings(max_characters=2400)
    )

    assert len(chunks) == 2
    assert chunks[0].page_numbers == (1,)
    assert chunks[1].page_numbers == (2,)


def test_section_strategy_splits_at_size_without_splitting_elements() -> None:
    section = ("Chassis",)
    elements = (
        element(1, "A" * 300, section_path=section),
        element(2, "B" * 300, section_path=section),
    )
    artifact = extraction_artifact(elements, document_type="technical_manual")
    settings = ChunkingSettings(max_characters=400)

    first = build_chunks(artifact, classify_document(artifact), settings)
    second = build_chunks(artifact, classify_document(artifact), settings)

    assert len(first) == 2
    assert first[0].chunk_id == second[0].chunk_id
    assert all(not chunk.oversize for chunk in first)
    assert {item for chunk in first for item in chunk.element_ids} == {
        element.element_id for element in eligible_elements(artifact)
    }


def test_single_oversize_element_is_retained_and_marked() -> None:
    artifact = extraction_artifact(
        (element(1, "A" * 500),), document_type="engineering_reference"
    )

    chunks = build_chunks(
        artifact, classify_document(artifact), ChunkingSettings(max_characters=400)
    )

    assert len(chunks) == 1
    assert chunks[0].oversize is True
    assert chunks[0].element_ids == (artifact.elements[0].element_id,)


def test_evidence_text_preserves_extraction_element_text() -> None:
    artifact = extraction_artifact(
        (element(1, "  Exact extracted text. \n"),),
        document_type="technical_manual",
    )

    chunks = build_chunks(artifact, classify_document(artifact), ChunkingSettings())

    assert chunks[0].evidence_text == "  Exact extracted text. \n"
