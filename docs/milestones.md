# RaceVault delivery milestones

Every milestone ends with automated checks, documented decisions, and an
explicit review before work begins on the next milestone.

## M1 — Foundation and project scaffold

Status: complete (2026-08-12).

Acceptance gates:

1. `docker compose config` validates the service graph.
2. Backend unit tests pass without requiring live infrastructure.
3. The representative corpus manifest resolves to real, readable PDFs.
4. `/health/live` reports process liveness.
5. `/health/ready` distinguishes healthy and unavailable dependencies.
6. The initial migration enables pgvector and creates the document registry.

## M2 — Deterministic PDF extraction

Status: complete (2026-08-13).

Build a Docling and PyMuPDF extraction pipeline that preserves page boundaries,
headings, section hierarchy, tables, hashes, and extraction provenance.

Acceptance gates:

1. Extraction artifacts include source and page-text SHA-256 hashes.
2. Every normalized element and table retains page-numbered provenance.
3. Table rows, columns, spans, header flags, and cell text are preserved.
4. Raw lossless Docling output is stored and hash-verified.
5. Artifact validation rejects broken page, table, hash, and statistics references.
6. Repeated extraction of the representative tyre document produces byte-identical
   normalized and raw JSON artifacts.
7. Representative tyre-data and regulation PDFs complete successfully.

## M3 — Classification and evidence-aware chunking

Classify document types and apply clause-, section-, or hierarchical chunking.
Every chunk must retain stable source, page, section, and revision identity.

## M4 — Lexical retrieval

Index evidence in OpenSearch and evaluate exact-term BM25 retrieval with strict
metadata filters.

## M5 — Semantic retrieval

Run BGE-M3 locally, persist embeddings in pgvector, and expose filtered vector
search.

## M6 — Fusion and reranking

Combine lexical and semantic rankings with RRF and rerank candidates using
BGE-Reranker-v2-M3.

## M7 — Evaluation and corpus hardening

Create a labelled engineering query set, measure retrieval quality, ingest the
full corpus, and cover conflicts and wrong-revision failure modes.

## M8 — Product API

Expose ingestion, retrieval, citation, source inspection, and document
comparison through stable FastAPI contracts.

## M9 — Evidence interface

Build the Next.js engineering interface for queries, filters, citations, source
inspection, and comparison.

## M10 — V1 deployment acceptance

Verify recovery, repeatable full-corpus ingestion, workstation performance, and
operational documentation for the 50–80 PDF target.
