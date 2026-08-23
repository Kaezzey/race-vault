# Evidence Intelligence Controller

RaceVault keeps the existing BM25, BGE-M3, RRF, and cross-encoder retrieval
pipeline. Before generation, a deterministic controller now decides which of
the reranked candidates should consume the limited model context.

## Why this exists

Passing the first N chunks to a language model has two common failure modes:

1. Near-duplicate chunks consume the context budget without adding evidence.
2. A model attempts an answer even though the best retrieved passage is weak.

The controller addresses these without introducing another learned model or
an unauditable agent step. Its policy is versioned as `mmr_scope_v1`.

## Selection policy

The controller:

- classifies the query as conceptual, exact/numeric, or comparison/conflict;
- preserves explicit championship scope coverage;
- suppresses near-duplicate passages using token-set similarity;
- applies an MMR-style relevance/diversity objective to remaining candidates;
- prefers an unseen source for conflict and comparison questions;
- caps repeated evidence from one source; and
- optionally abstains before generation when the best reranker score is below
  a development-calibrated threshold.

Every answer response includes content-free `evidence_selection` diagnostics:
the policy version, inferred intent, candidate and selection counts, duplicate
count, source and scope coverage, maximum score, threshold, and decision.

## Calibrating abstention without test leakage

First produce a report containing only development queries:

```powershell
racevault-evaluate evaluation/queries-v2.json `
  --split development `
  --output .artifacts/reports/retrieval-development.json
```

Then calibrate the threshold:

```powershell
racevault-calibrate-sufficiency `
  .artifacts/reports/retrieval-development.json `
  --output .artifacts/reports/sufficiency-calibration.json `
  --minimum-answerable-recall 0.80 `
  --minimum-unanswerable-recall 0.90
```

The calibrator refuses reports containing held-out results. Copy the emitted
threshold into `RACEVAULT_ANSWER_MINIMUM_RERANKER_SCORE`, record the calibration
artifact with the experiment, freeze the configuration, and only then run the
test split.

If no threshold satisfies both recall constraints, calibration fails. That is
an actionable retrieval result, not a reason to relax the test set after
looking at it.

Candidate thresholds include the midpoint between each pair of adjacent observed
scores, not only the observed scores themselves. Without them a separating
threshold lands exactly on the lowest-scoring answerable development query, and
any drift in that one query's score flips its verdict.

### Current calibration

Calibrated on the 27 development queries of `racevault-corpus-v2`:

| Property | Value |
| --- | ---: |
| Threshold | 0.2377 |
| Answerable recall | 1.000 |
| Unanswerable recall | 1.000 |
| Balanced accuracy | 1.000 |

The two classes separate by roughly a factor of ten: the lowest-scoring
answerable query scores 0.32 and the highest-scoring out-of-corpus query scores
0.03. On the held-out test split the same threshold answers 9 of 9 answerable
queries and abstains on 4 of 4 out-of-corpus ones.

Before this dataset existed the threshold was unset, so the system returned
evidence for every question including ones the corpus cannot answer.

## Required ablation

Evaluate two frozen variants on identical generated answers:

| Variant | Evidence selection | Sufficiency gate |
|---|---|---|
| Control | Original top-N order | Disabled |
| Controller | `mmr_scope_v1` | Development-calibrated |

Report completeness, citation entailment precision, unsupported-claim rate,
context utilization, abstention precision/recall, tokens, and latency. Promote
the controller only if unsupported claims or unanswerable recall improve
without a material completeness regression.

## Configuration

- `RACEVAULT_ANSWER_EVIDENCE_DIVERSITY_WEIGHT` controls the novelty penalty.
- `RACEVAULT_ANSWER_EVIDENCE_TOPIC_WEIGHT` controls the explicit query-topic
  coverage bonus applied after cross-encoder reranking.
- `RACEVAULT_ANSWER_FACET_CANDIDATE_LIMIT` bounds the reranked results retained
  from each explicit query facet.
- `RACEVAULT_ANSWER_MAX_QUERY_FACETS` bounds facet decomposition and therefore
  its retrieval-latency cost.
- `RACEVAULT_ANSWER_EVIDENCE_DUPLICATE_THRESHOLD` controls duplicate removal.
- `RACEVAULT_ANSWER_EVIDENCE_MAX_PER_SOURCE` limits source concentration.
- `RACEVAULT_ANSWER_MINIMUM_RERANKER_SCORE` enables calibrated abstention.

The threshold defaults to unset. This is deliberate: a score cut-off must be
estimated from RaceVault's development distribution, not selected by intuition.
