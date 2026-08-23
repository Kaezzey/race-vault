# RaceVault system card

## Intended use

RaceVault retrieves and summarizes evidence from motorsport technical documents.
It is intended for engineering research and document comparison, not autonomous
safety, scrutineering, or regulatory decisions. The original revision-controlled
document remains authoritative.

## Architecture and trust boundaries

PDFs are untrusted input. Extraction preserves hashes and page provenance;
metadata filters are applied before BM25 and dense retrieval; RRF and a
cross-encoder rank the common candidate set; the generator receives a bounded
evidence context. Generated citation identifiers must resolve to returned
evidence or the answer fails closed.

OpenSearch, PostgreSQL, model files, uploaded PDFs, and Ollama are separate trust
boundaries. API errors do not expose credentials. Metrics and traces omit raw
queries and evidence by default.

## Measured and unmeasured properties

The `racevault-corpus-v2` set (40 queries, nine document families, split
development/test without family overlap) is a regression check, not a general
quality estimate. Its held-out split is small and its labels are
author-verified rather than independently annotated, so inter-annotator
agreement is unmeasured.

Abstention on out-of-corpus questions is measured: a reranker-score threshold
calibrated on the development split alone answers 9 of 9 answerable held-out
queries and abstains on 4 of 4 out-of-corpus ones.

The v2 implementation also supports confidence intervals, claim-level grounding,
adversarial cases, and operational SLOs. Those results must not be claimed until
the human-labelled dataset is complete.

Structural citation validity is enforced. Semantic entailment is measured by
offline judgement and is not yet an online safety guarantee. OCR, complex tables,
figures, ambiguous revisions, and corpus omissions can still cause failure.

## Operational controls

- One generation job runs at a time by default; four additional jobs may queue.
- Excess generation requests receive HTTP 429 and `Retry-After`.
- Every HTTP response carries `X-Request-ID`.
- `/metrics` exports counts, latency, queue state, candidate counts, repairs, and
  token totals without content.
- Optional OTLP traces expose pipeline stage timing through the local
  observability Compose override.

## Release gates

A benchmark release requires 100% citation-ID validity, at least 90%
unanswerable-query recall, no more than 5% unsupported claims, no held-out
nDCG@10 regression greater than two absolute points, and passing declared
operational SLOs.
