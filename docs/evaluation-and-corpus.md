# Retrieval evaluation and full-corpus ingestion

Milestone 7 measures each retrieval stage with labelled engineering queries and
loads the complete local PDF corpus into both retrieval stores.

## Full corpus

The corpus manifest contains 64 PDFs and covers 4,888 pages. The current class
distribution is:

| Document class | Documents |
| --- | ---: |
| Component manual | 35 |
| Engineering reference | 1 |
| Part catalogue | 4 |
| Regulation | 16 |
| Technical manual | 2 |
| Tyre data | 6 |

The complete manifest is [full_documents.json](../corpus/full_documents.json).
Every PDF below `AI & ML Reference File Database/` must appear exactly once.
The audit fails if a PDF is missing from the manifest or a manifest path does
not resolve to a PDF.

Metadata derived from a directory or filename is limited to deterministic
values such as document class, championship directory, explicit season, and
explicit vehicle-generation directory. Curated representative metadata
overrides derived values. Unknown fields remain unset.

Audit the corpus:

```powershell
python -m racevault.corpus.cli audit
```

## Resumable ingestion

The ingestion runner processes each PDF through these stages:

```text
PDF
  -> Docling and PyMuPDF extraction
  -> document-specific chunking
  -> OpenSearch BM25 indexing
  -> BGE-M3 embedding and PostgreSQL/pgvector storage
```

Each extraction and chunk artifact has a content- and settings-derived path.
Compatible artifacts are reused. PostgreSQL reuses an embedding when its chunk
ID, contextual-text hash, model ID, and model revision match.

The runner writes `.artifacts/reports/full-ingestion.json` after every document.
One failed document is recorded without discarding completed documents. Use
`--fail-fast` when any failure should stop the run.

For workstations with a CUDA GPU, use two passes. This avoids loading Docling
and BGE-M3 on the GPU at the same time:

```powershell
python -m racevault.corpus.cli ingest `
  --through chunk `
  --extraction-device cuda

python -m racevault.corpus.cli ingest `
  --through semantic `
  --extraction-device cuda `
  --embedding-device cuda `
  --embedding-batch-size 8 `
  --local-files-only
```

The second command reuses the completed extraction and chunk artifacts. It
indexes the canonical chunks in OpenSearch and generates or reuses BGE-M3
vectors in PostgreSQL.

## Labelled evaluation set

The evaluation dataset is [queries.json](../evaluation/queries.json). It covers:

- exact technical identifiers;
- regulation definitions and rules;
- manual procedures and safety instructions;
- structured tyre tables;
- conceptual questions;
- wrong-revision empty-result behavior;
- evidence returned from more than one source.

Each positive query defines one or more relevant evidence labels using source
path, optional page number, and required text fragments. Negative queries define
an expected empty result. Multi-source cases define the minimum number of
distinct relevant sources required.

## Metrics

RaceVault evaluates four ranked lists independently:

1. OpenSearch BM25.
2. BGE-M3 cosine retrieval.
3. Reciprocal Rank Fusion.
4. Cross-encoder reranking.

The report includes:

- positive hit rate: fraction of positive queries with relevant evidence;
- mean reciprocal rank (MRR): mean of `1 / first relevant rank`;
- negative accuracy: fraction of empty-result cases returning no candidates;
- passed queries: labels and multi-source requirements satisfied.

Run the evaluation from `backend/`:

```powershell
python -m racevault.evaluation.cli `
  --dataset "../evaluation/queries.json" `
  --output "../.artifacts/evaluation/full-corpus.json" `
  --device cuda `
  --local-files-only
```

The command fails its acceptance check when reranked hit rate is below `0.8`,
reranked MRR is below `0.5`, or wrong-revision accuracy is below `1.0`. Override
the positive thresholds with `--minimum-hit-rate` and `--minimum-mrr`.

## Current full-corpus results

The 2026-08-14 run produced 9,212 canonical chunks. OpenSearch and PostgreSQL
each contain 9,212 chunks, and all 64 PostgreSQL documents have matching pinned
BGE-M3 embeddings.

| Stage | Positive hit rate | MRR | Negative accuracy |
| --- | ---: | ---: | ---: |
| BM25 | 1.000 | 0.717 | 1.000 |
| BGE-M3 | 1.000 | 0.751 | 1.000 |
| RRF | 1.000 | 0.741 | 1.000 |
| Reranked | 1.000 | 0.967 | 1.000 |

These numbers describe the current 16-query dataset. They are a regression
baseline, not a general estimate of retrieval accuracy. Extend the labelled set
when new engineering domains or failure modes are added.
