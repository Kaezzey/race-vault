# RaceVault evaluation-first technical report

## Hypotheses

1. Metadata pre-filtering prevents plausible evidence from the wrong season or
   championship from consuming candidate budget.
2. BM25 and BGE-M3 are complementary for identifiers and conceptual paraphrases.
3. Structure-aware chunks outperform generic windows on clauses, tables, and
   procedures.
4. Cross-encoder reranking improves top-rank quality enough to justify latency and
   VRAM.
5. Visual late interaction helps layout-dependent queries only when its operational
   cost is bounded.

## Experimental method

Evaluation v2 freezes document-family-disjoint development and test splits,
graded relevance, gold atomic claims, negative cases, adversarial slices, model
revisions, random seeds, and configuration hashes. Primary retrieval quality is
nDCG@10; Recall@5/10/20, MRR, context precision, and negative accuracy diagnose
different failure modes. Reports include 1,000-sample bootstrap intervals and
paired query-level comparisons.

The evaluation CLI exposes metadata-filter removal, RRF weights, rank constant,
candidate budgets, index selection, and ablation labels. Separate fixed-window
and structure-aware indices are compared with identical query and model settings.

## Current evidence

The `racevault-corpus-v2` dataset supersedes the 16-query legacy set, which had
one negative query and drew 7 of its 17 labels from the 66-chunk tyre-data
class while leaving component manuals (1,584 chunks), part catalogues (360), and
the engineering reference (164) unrepresented.

The v2 set holds 40 queries over nine document families: 31 answerable and 9
verified out-of-corpus. Every label is checked against the indexed corpus by
`evaluation/build_dataset.py`, and every negative is checked to have no answer
anywhere in it, so the dataset cannot silently drift from what is indexed.

On the held-out test split the reranked stage reports hit rate 1.000, MRR 0.944,
and nDCG@10 0.894. Abstention is calibrated on the development split alone
(threshold 0.2377, balanced accuracy 1.000) and generalises to the held-out
split without error.

Labels are author-verified against source passages rather than independently
annotated, so inter-annotator agreement remains unmeasured and graded relevance
is coarse. The repository still records human annotation as incomplete rather
than filling the benchmark synthetically.

## Required result tables

Publish BM25, dense, fused, reranked, no-prefilter, fixed-window, and sensitivity
runs with quality, confidence intervals, cold/warm latency, throughput, RAM/VRAM,
and index size. Generate the static table with
`scripts/build_benchmark_dashboard.py` and failed-query analysis with
`scripts/build_failure_atlas.py`.

## Rejected shortcuts

- Do not expand the dataset by paraphrasing known target passages with the answer
  visible.
- Do not use the same model as generator and uncalibrated judge to claim grounding.
- Do not enable visual retrieval because it is novel; require the frozen gate.
- Do not add agents, memory, or fine-tuning without a measured failure that needs
  them.

## Evidence-controller hypothesis

The current implementation adds a versioned `mmr_scope_v1` evidence controller
after cross-encoder reranking. The hypothesis is that scope coverage, duplicate
suppression, and source diversity reduce unsupported generation while retaining
answer completeness. An optional reranker threshold is calibrated on
development queries only and frozen before held-out use. The implementation and
ablation protocol are documented in
[evidence-controller.md](evidence-controller.md); no accuracy improvement will
be claimed until its paired grounding evaluation is complete.
