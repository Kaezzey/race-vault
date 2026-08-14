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

Status: complete (2026-08-13).

Run BGE-M3 locally, persist embeddings in pgvector, and expose filtered vector
search.

Acceptance gates:

1. The embedding contract pins the BGE-M3 model ID, revision, dimensions,
   normalization, maximum input length, and input-text hash.
2. Every representative chunk has one valid 1,024-dimensional dense vector.
3. Matching vectors are reused without regenerating or reloading the model.
4. PostgreSQL stores chunks, exact evidence, provenance, and model-versioned
   embeddings transactionally.
5. A cosine HNSW index and strict iterative scans support filtered retrieval.
6. Semantic search supports the same source and domain filters as BM25 search.
7. Representative conceptual queries retrieve relevant manual, tyre-data, and
   regulation evidence, and a wrong-revision filter returns no results.

## M6 — Fusion and reranking

Status: complete (2026-08-14).

Combine lexical and semantic rankings with RRF and rerank candidates using
BGE-Reranker-v2-M3.

Acceptance gates:

1. Lexical and semantic hits use one citation-ready evidence contract.
2. Both retrieval channels apply the same source and domain filters before fusion.
3. Weighted RRF deduplicates chunks and records each channel rank and raw score.
4. Fusion and final tie handling are deterministic for identical inputs.
5. The reranker model ID, revision, maximum input length, and normalized score
   contract are pinned.
6. Final results retain lexical, semantic, fused, and reranked diagnostics with
   complete source provenance.
7. Representative regulation and tyre-data queries return the expected evidence,
   and a wrong-revision filter returns no candidates at every stage.

## M7 — Evaluation and corpus hardening

Status: complete (2026-08-14).

Create a labelled engineering query set, measure retrieval quality, ingest the
full corpus, and cover conflicts and wrong-revision failure modes.

Acceptance gates:

1. A validated manifest covers every one of the 64 corpus PDFs exactly once.
2. Full-corpus extraction and chunking are resumable and record per-document
   failures without removing completed artifacts.
3. All 4,888 pages complete extraction and produce 9,212 validated chunks with
   no document failures.
4. OpenSearch and PostgreSQL each contain the same 9,212 canonical chunks.
5. All 64 PostgreSQL documents have matching pinned BGE-M3 embeddings.
6. A labelled dataset measures BM25, BGE-M3, RRF, and reranked hit rate and MRR
   independently.
7. The full-corpus evaluation passes positive hit-rate and MRR thresholds, the
   wrong-revision case returns no candidates, and the multi-source case exposes
   relevant evidence from both sources.

## M8 — Product API

Status: complete (2026-08-14).

Expose ingestion, retrieval, citation, source inspection, and document
comparison through stable FastAPI contracts.

Acceptance gates:

1. V1 retrieval applies matching metadata prefilters in both search channels and
   returns fused, reranked evidence.
2. Every retrieval result contains page-level citation and extraction provenance.
3. Source listing and chunk inspection support filters and bounded pagination.
4. Document comparison retrieves independently from two verified source hashes.
5. Corpus status verifies PostgreSQL chunk and embedding counts against OpenSearch.
6. Ingestion requires an explicit scope, permits one active run, writes resumable
   checkpoints, and is disabled by default.
7. Validation and service failures use stable error codes and response shapes.
8. The Compose runtime supports CPU operation and an explicit NVIDIA GPU override.
9. Unit, contract, full-corpus, live GPU retrieval, and comparison checks pass.

## M9 — Evidence interface

Status: complete (2026-08-14).

Build the Next.js engineering interface for queries, filters, citations, source
inspection, and comparison.

Acceptance gates:

1. Search runs the V1 hybrid retrieval endpoint and reports loading and service
   errors without losing the current query.
2. Metadata filters are visible before submission and remain attached to the
   displayed result set.
3. Evidence cards show exact text, source, page, clause, domain metadata, rank,
   and normalized reranker score.
4. Citation inspection shows source and evidence hashes, section identity,
   provenance count, and retrieval-stage diagnostics.
5. The source catalogue exposes all loaded documents, chunk counts, and vector
   coverage with local filtering.
6. Comparison retrieves independently from two selected source hashes and keeps
   both evidence sets visually separate.
7. Desktop and mobile layouts provide access to search, sources, comparison,
   filters, and the query composer.
8. Type checking, lint, production build, live search, filtered retrieval,
   comparison, responsive layout, and container checks pass.

## M10 — V1 deployment acceptance

Verify recovery, repeatable full-corpus ingestion, workstation performance, and
operational documentation for the 50–80 PDF target.
