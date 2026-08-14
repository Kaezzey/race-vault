"""Public API response factories."""

from __future__ import annotations

from racevault.api.models import (
    CandidateCounts,
    Citation,
    ModelIdentity,
    RetrievalDiagnostics,
    RetrievalResult,
    RetrievalSearchResponse,
)
from racevault.catalog.models import SourceSummary
from racevault.retrieval.models import SearchFilters
from tests.chunking.factories import provenance


def retrieval_response(query: str = "Joker Tyre") -> RetrievalSearchResponse:
    return RetrievalSearchResponse(
        query=query,
        filters=SearchFilters(document_class="regulation", season=2026),
        counts=CandidateCounts(lexical=1, semantic=10, fused=10, reranked=10),
        embedding_model=ModelIdentity(
            model_id="BAAI/bge-m3", model_revision="a" * 40
        ),
        reranker_model=ModelIdentity(
            model_id="BAAI/bge-reranker-v2-m3", model_revision="b" * 40
        ),
        results=(
            RetrievalResult(
                rank=1,
                evidence_text="Joker Tyre definition.",
                document_class="regulation",
                chunk_kind="table",
                source_role="regulation_current",
                source_metadata={"season": 2026},
                citation=Citation(
                    chunk_id="chk_" + "1" * 32,
                    source_sha256="a" * 64,
                    source_path="Rules/current.pdf",
                    source_filename="current.pdf",
                    page_start=6,
                    page_end=6,
                    page_numbers=(6,),
                    section_path=("Definitions",),
                    clause_reference=None,
                    evidence_sha256="b" * 64,
                    element_ids=("el_" + "1" * 32,),
                    table_ids=("tbl_" + "1" * 32,),
                    provenance=provenance(6),
                ),
                diagnostics=RetrievalDiagnostics(
                    lexical_rank=1,
                    lexical_score=8.0,
                    semantic_rank=2,
                    semantic_score=0.8,
                    fused_rank=1,
                    rrf_score=0.03,
                    reranker_score=0.9,
                ),
            ),
        ),
    )


def source_summary(source_sha256: str = "a" * 64) -> SourceSummary:
    return SourceSummary(
        source_sha256=source_sha256,
        source_path="Rules/current.pdf",
        filename="current.pdf",
        source_role="regulation_current",
        title=None,
        document_type="regulation",
        vehicle_generation="992.2",
        championship="PCC Australia",
        season=2026,
        revision="Version 2",
        authority="official_regulation",
        language=None,
        page_count=36,
        extra_metadata={},
        chunk_count=100,
        embedding_count=100,
    )
