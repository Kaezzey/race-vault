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

Status: complete (2026-08-13).

Classify document types and apply clause-, section-, or hierarchical chunking.
Every chunk retains stable source, page, section, and revision identity.

Acceptance gates:

1. Declared corpus metadata takes precedence over path and size classification rules.
2. Regulations use clause-aware boundaries, tyre data uses page and table boundaries,
   and manuals and references use hierarchical section boundaries.
3. Evidence text preserves the exact extracted text and remains separate from added
   retrieval context.
4. Every eligible extraction element appears in exactly one chunk.
5. Tables and individual source elements are never split; oversized chunks are marked.
6. Chunk identifiers and artifacts are stable across repeated runs with identical input.
7. Artifact validation rejects changed extraction inputs and incomplete provenance.

## M4 — Lexical retrieval

Status: complete (2026-08-13).

Index evidence in OpenSearch and evaluate exact-term BM25 retrieval with strict
metadata filters.

Acceptance gates:

1. A versioned, strict OpenSearch mapping defines searchable and stored fields.
2. Technical analyzers retain common engineering identifiers and clause terms.
3. Indexing preserves exact evidence, source metadata, pages, and provenance.
4. Reindexing replaces stale chunks for one source without removing other sources.
5. BM25 search supports document, authority, generation, championship, season,
   revision, page, role, kind, and source filters.
6. Search results contain the fields required to create exact source citations.
7. Representative regulation and tyre queries retrieve the expected evidence,
   and a wrong-revision filter returns no results.

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
