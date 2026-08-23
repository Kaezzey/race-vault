"""Evidence packing under a bounded prompt budget."""

from __future__ import annotations

from racevault.api.models import (
    Citation,
    RetrievalDiagnostics,
    RetrievalResult,
)
from racevault.config import Settings
from racevault.generation.service import (
    GroundedAnswerService,
    _truncate_evidence,
)
from tests.chunking.factories import provenance


def _result(rank: int, text: str) -> RetrievalResult:
    return RetrievalResult(
        rank=rank,
        evidence_text=text,
        document_class="regulation",
        chunk_kind="table",
        source_role="regulation_current",
        source_metadata={},
        citation=Citation(
            chunk_id=f"chk_{rank:032d}",
            source_sha256=f"{rank:064d}",
            source_path="Rules/current.pdf",
            source_filename="current.pdf",
            page_start=1,
            page_end=1,
            page_numbers=(1,),
            section_path=("Section",),
            clause_reference=None,
            evidence_sha256=f"{rank:064d}",
            element_ids=(),
            table_ids=(),
            provenance=provenance(1),
        ),
        diagnostics=RetrievalDiagnostics(
            lexical_rank=rank,
            lexical_score=1.0,
            semantic_rank=rank,
            semantic_score=0.5,
            fused_rank=rank,
            rrf_score=0.03,
            reranker_score=0.9,
        ),
    )


def _service(budget: int) -> GroundedAnswerService:
    return GroundedAnswerService(
        settings=Settings(answer_evidence_character_budget=budget),
        retrieval=None,  # type: ignore[arg-type]
        ollama=None,  # type: ignore[arg-type]
    )


def test_one_oversized_passage_does_not_end_the_pack() -> None:
    """A large table at rank 2 must not cost every lower-ranked passage."""

    results = (
        _result(1, "a" * 3000),
        _result(2, "b" * 9000),
        _result(3, "c" * 400),
        _result(4, "d" * 400),
    )

    packed = _service(4000)._pack_evidence(results, limit=10)

    assert [item.result.rank for item in packed] == [1, 3, 4]
    assert [item.evidence_id for item in packed] == ["E1", "E2", "E3"]


def test_the_best_passage_is_truncated_rather_than_dropped() -> None:
    packed = _service(4000)._pack_evidence((_result(1, "a" * 90000),), limit=10)

    assert len(packed) == 1
    assert packed[0].prompt_text.endswith("[Evidence truncated]")
    assert len(packed[0].prompt_text) <= 4100


def test_truncation_prefers_a_line_boundary() -> None:
    """Half a table row misleads the model about which column it read."""

    table = "\n".join(f"Circuit {index} | 1.7 bar | 1.9 bar" for index in range(20))

    truncated = _truncate_evidence(table, 120)

    body = truncated.removesuffix("\n[Evidence truncated]")
    assert all(line.endswith("bar") for line in body.split("\n"))


def test_budget_never_exceeds_the_generation_context() -> None:
    """A raised character budget must not push the system prompt out."""

    service = GroundedAnswerService(
        settings=Settings(
            answer_evidence_character_budget=60000,
            ollama_context_tokens=8192,
            ollama_max_output_tokens=3072,
        ),
        retrieval=None,  # type: ignore[arg-type]
        ollama=None,  # type: ignore[arg-type]
    )

    assert service._evidence_character_budget() < 60000


def test_a_budget_that_fits_is_left_alone() -> None:
    service = GroundedAnswerService(
        settings=Settings(
            answer_evidence_character_budget=24000,
            ollama_context_tokens=16384,
            ollama_max_output_tokens=3072,
        ),
        retrieval=None,  # type: ignore[arg-type]
        ollama=None,  # type: ignore[arg-type]
    )

    assert service._evidence_character_budget() == 24000
