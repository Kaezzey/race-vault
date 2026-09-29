# RaceVault validation report

Production source commit: `5e669e763b92db944ac86ad22907fb7b0ecfb619`. Fresh retrieval completed at 2026-09-29T10:59:18.026172+00:00 (UTC; 2026-09-30 Pacific/Auckland). No production code, retrieval parameters, labels, split assignments or runtime threshold were changed. The starting tracked tree was clean; the recorded dirty state consists of newly added audit tools/artifacts.

## Scope and status

The requested 20-question benchmark is not present. This audit covers the actual 40-question dataset, preserves its 27/13 development/test split and documents all 40 questions in `racevault_benchmark_provenance.md`. The test split has 9 answerable questions and 4 negatives. All 13 were selected for citation capture before seeing their answers; adding development questions to reach 15–20 would misrepresent the split.

A fresh process ran the current evaluation runner against the existing stores; this was not a re-ingestion or clean-room index rebuild. Both store snapshots are byte-for-byte identical at the JSON snapshot level before and after: 64 documents, 9,212 chunks and 9,212 pinned BGE-M3 embeddings. The prior stopped Docker/Ollama services were started. The first attempt failed because .env used Docker-only hostnames; local endpoint overrides fixed connectivity without changing retrieval settings. That failed manifest is retained.

## Reproduction and frozen configuration

Run from the repository root with the existing PostgreSQL, OpenSearch and Ollama services and cached models available:

```powershell
$env:RACEVAULT_POSTGRES_HOST='localhost'
$env:RACEVAULT_OPENSEARCH_URL='http://localhost:9200'
$env:RACEVAULT_OLLAMA_URL='http://localhost:11434'
$env:PYTHONHASHSEED='17'
$env:CUBLAS_WORKSPACE_CONFIG=':4096:8'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
python evaluation/reproduce_validation.py live
$env:RACEVAULT_API_MODEL_DEVICE='cuda'
$env:RACEVAULT_API_LOCAL_FILES_ONLY='true'
python evaluation/reproduce_validation.py answers
python evaluation/build_validation_record.py --resolve-labels
```

Archive `validation_evidence/` and reviewer-edited CSVs before rerunning: the scripts overwrite their audit outputs. They never write to retrieval stores. The recorder wraps the evaluator's call site to save the unchanged stage results; the current production search functions perform ranking. Model loading is offline. No calibration was run on fresh or test scores: the historical development calibration algorithm was replayed only to verify its saved threshold.

The complete configuration, runtime package versions, GPU, Python, CUDA/cuDNN, seeds, dataset hash and safe settings are in `validation_evidence/run_manifest.json`; generation settings and model digest are in `answer_manifest.json`. Store settings/mappings/content hashes and PostgreSQL/pgvector versions are in `stores_before.json` and `stores_after.json`. The generation capture used Ollama 0.34.2 and qwen3.5:9b digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` (Q4_K_M, 9.7B). Raw stage hits and scores are in `retrieval_<query_id>.json`; raw answer-service responses and actual generation prompts/calls are in `answer_<query_id>.json`. Input and output SHA-256 manifests bind the record.

| Setting | Value |
| --- | --- |
| Dataset | racevault-corpus-v2 2.0.0; 2c0ecd96991945ce3d6a69153880a9d771f8f7e13fb2cb9320efc8b822b50cee |
| Embedding | BAAI/bge-m3 @ 5617a9f61b028005a4858fdac845db406aefb181; max_tokens=8192; batch=1; normalized CLS |
| Reranker | BAAI/bge-reranker-v2-m3 @ 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e; max_tokens=8192; batch=8; sigmoid scores |
| Device | CUDA, NVIDIA GeForce RTX 4070; model float16 |
| Retrieval lists | BM25=50, semantic=50, fused=30, reranked=15; only first 15 fused candidates are reranked |
| Fusion | RRF constant=60; lexical weight=1; semantic weight=1 |
| Filters | dataset filters enabled; runner bypasses service scope/latest-edition resolution |
| Index | racevault-chunks-v2; schema 2.0; OpenSearch 3.7.0 / Lucene 10.4.0; PostgreSQL 18.4 / pgvector 0.8.6 |
| BM25 | server similarity defaults (no explicit k1/b override); analyzer/mapping snapshotted; boosts/tie-breaks in lexical/query.py |
| Dense query | cosine distance; model/revision and metadata filters; distance then chunk ID; hnsw.iterative_scan=strict_order |
| Seeds | Python random, NumPy, PyTorch CPU/CUDA and PYTHONHASHSEED=17; bootstrap=1000 with base seed 17 and metric offsets; deterministic PyTorch algorithms; CUBLAS :4096:8 |
| Generation | qwen3.5:9b; temperature=0; seed=0; num_ctx=16384; num_predict=3072; think=false |
| Abstention | runtime fixed 0.2377; original saved calibration 0.237715570256114; no tuning |
| Acceptance checks | CLI hit>=0.8, MRR>=0.5, nDCG@10>=0.5 and negative retrieval accuracy=1; calibration constraints answerable recall>=0.8, unanswerable recall>=0.9 |

The runner's CLI random seed controls bootstrap resampling, not model RNGs. This harness additionally seeds model libraries. Fixed seeds do not guarantee bit-identical floating-point results across hardware, library versions or ANN index rebuilds. The pre-existing HNSW construction seed/history is unknown; preserved index state and hashes constrain this reproduction.

## Retrieval effectiveness

Metrics are macro-averages over answerable questions only (development n=22; test n=9). All 40 questions were executed. MRR is reciprocal first matching rank over each stage's full returned list, not uniformly MRR@10. Recall@k is the fraction of authored label predicates matched among the first k hits, credited once each; it is not exhaustive document/chunk recall. HitRate@k is the fraction of answerable questions with at least one matching hit within k. Empty-query metrics are blank in the CSV, not synthetic zeros. Family values on historical CSV rows are mapped to the current dataset for diagnosis; legacy files did not originally declare those families. Negative candidate returns are distinct from answer-layer abstention. The unchanged CLI acceptance rule would still fail this run because it requires negative retrieval accuracy=1, although out-of-corpus top-k retrieval returns candidates (development negative accuracy=0.2; test=0). This harness records metrics without changing that rule or describing the run as passing its CLI acceptance gate. The original positive_hit_rate uses the full list and must not be renamed HitRate@5/10.

| Split | Stage | All/positive n | MRR | Recall@5 | Recall@10 | HitRate@5 | HitRate@10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development | lexical | 27/22 | 0.659564 | 0.818182 | 0.818182 | 0.818182 | 0.818182 |
| development | semantic | 27/22 | 0.729600 | 0.863636 | 0.954545 | 0.863636 | 0.954545 |
| development | fused | 27/22 | 0.763223 | 0.818182 | 0.863636 | 0.818182 | 0.863636 |
| development | reranked | 27/22 | 0.901515 | 0.954545 | 0.954545 | 0.954545 | 0.954545 |
| test | lexical | 13/9 | 0.847222 | 0.777778 | 0.888889 | 0.888889 | 1.000000 |
| test | semantic | 13/9 | 0.888889 | 0.888889 | 0.888889 | 1.000000 | 1.000000 |
| test | fused | 13/9 | 0.870370 | 0.888889 | 0.888889 | 1.000000 | 1.000000 |
| test | reranked | 13/9 | 0.944444 | 0.888889 | 0.944444 | 1.000000 | 1.000000 |

Fresh metrics reproduce the saved final development/test aggregates. Scores may differ slightly at floating-point precision. The CSV separates fresh runs from saved-result arithmetic replay and includes per-question and per-family rows. Missing Recall fields in legacy saved files remain blank; they cannot be recovered from first-relevant rank alone. Saved reports omit hit identities/text, so their original relevance matching cannot be independently replayed from those reports alone. Fresh traces now retain that evidence.

### Failures and incomplete retrieval

| Split | Family | Question | Stage | First rank | Recall@10 | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| development | pcc-australia-regulations | aus_current_minimum_weight | lexical | 12 | 0.0 | miss_at_5;miss_at_10;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | pcc-australia-regulations | aus_2025_minimum_weight | lexical | 16 | 0.0 | miss_at_5;miss_at_10;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | abs-m5 | abs_map_switch_positions | lexical | 20 | 0.0 | miss_at_5;miss_at_10;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | abs-m5 | abs_hydraulic_unit_weight | lexical | 32 | 0.0 | miss_at_5;miss_at_10;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | pcc-australia-regulations | reg_joker_tyre_definition | semantic | 8 | 1.0 | miss_at_5;incomplete_label_recall_at_5 |
| development | pcc-australia-regulations | reg_round_alteration_precedence | semantic | 7 | 1.0 | miss_at_5;incomplete_label_recall_at_5 |
| development | abs-m5 | abs_map_switch_positions | semantic |  | 0.0 | no_label_match_in_returned_list;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | pcc-australia-regulations | aus_current_minimum_weight | fused | 6 | 1.0 | miss_at_5;incomplete_label_recall_at_5 |
| development | pcc-australia-regulations | aus_2025_minimum_weight | fused | 11 | 0.0 | miss_at_5;miss_at_10;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | abs-m5 | abs_map_switch_positions | fused |  | 0.0 | no_label_match_in_returned_list;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | abs-m5 | abs_hydraulic_unit_weight | fused | 12 | 0.0 | miss_at_5;miss_at_10;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| development | abs-m5 | abs_map_switch_positions | reranked |  | 0.0 | no_label_match_in_returned_list;incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | tyre-data | tyre_n3r_standard_cold_pressure | lexical | 8 | 1.0 | miss_at_5;incomplete_label_recall_at_5 |
| test | porsche-technical-manual | manual_intended_use | lexical | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | tyre-data | conflict_n3r_pressure_sources | lexical | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10;insufficient_distinct_sources |
| test | porsche-technical-manual | manual_intended_use | semantic | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | tyre-data | conflict_n3r_pressure_sources | semantic | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | porsche-technical-manual | manual_intended_use | fused | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | tyre-data | conflict_n3r_pressure_sources | fused | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | porsche-technical-manual | manual_intended_use | reranked | 1 | 0.5 | incomplete_label_recall_at_5;incomplete_label_recall_at_10 |
| test | tyre-data | conflict_n3r_pressure_sources | reranked | 1 | 1.0 | incomplete_label_recall_at_5 |

A passed query can still miss a relevant label: `manual_intended_use` passes at rank 1 but retrieves only one of two labels (Recall@10=0.5). `abs_map_switch_positions` misses both labels after fusion/reranking. These are failures under the existing literal labels; determining whether an unlabelled retrieved passage is semantically sufficient needs independent review. No label or parameter was changed in response.

## Abstention behaviour

The saved threshold artifact points to development run `b63a69a8-a9c6-4b80-ae8b-65af8d597001`; replaying its current calibration function yields the exact saved threshold 0.237715570256114. It selects among observed scores and midpoints under the stated recall constraints, maximizing balanced accuracy then recall, with lower-threshold tie-breaking. The runtime .env uses the rounded value 0.2377; both are evaluated in the CSV. A missing maximum (no candidates) is treated as score 0. Abstain iff maximum reranker score < threshold; equality answers.

Exactly these 27 questions selected the saved threshold and also underlie the published development score (resubstitution, not held-out validation):

`reg_joker_tyre_definition`, `reg_control_component_requirement`, `reg_slick_tyre_definition`, `reg_round_alteration_precedence`, `reg_driver_minimum_age`, `reg_2026_calendar`, `failure_wrong_regulation_revision`, `aus_current_minimum_weight`, `aus_current_racing_weight`, `aus_2025_minimum_weight`, `aus_driver_minimum_weight`, `aus_fuel_remaining`, `aus_driver_age`, `aus_joker_tyre_allocation`, `abs_map_switch_torque`, `abs_brake_line_diameter`, `abs_reset_after_drive_cycle_fault`, `abs_map_switch_positions`, `abs_hydraulic_unit_weight`, `software_update_order`, `ecu_temperature_range`, `ecu_flywheel_sensor_type`, `part_front_left_caliper`, `neg_drs_activation`, `neg_energy_recovery`, `neg_push_to_pass`, `neg_success_ballast`.

Exactly these 13 questions are excluded from the saved threshold-selection input and used here for fixed-threshold evaluation:

`tyre_n3r_dimensions`, `tyre_n3_rolling_circumference`, `tyre_shoulder_temperature_delta`, `tyre_unlisted_track_recommendation`, `tyre_n3r_standard_cold_pressure`, `manual_intended_use`, `manual_main_voltage_switch`, `manual_fire_system_test`, `conflict_n3r_pressure_sources`, `neg_budget_cap`, `neg_turbo_boost_limit`, `neg_sprint_shootout`, `neg_rallycross_joker`.

There is no separate calibration holdout. The saved development/test files have disjoint IDs and matching dataset hashes. However, the earlier all-split v2 report predates the development-only run, and the positive test questions have legacy retrieval exposure. This establishes separation of the saved threshold algorithm's input, not a prospective blind holdout of every design decision. Missing evidence: a preregistered freeze and tuning log showing nobody inspected these test scores when choosing the procedure/constraints.

| Origin | Split | Threshold | n | TP | FP | TN | FN | Abstention precision | Abstention recall | Answerable recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fresh | development | 0.2377 | 27 | 5 | 0 | 22 | 0 | 1.0 | 1.0 | 1.0 |
| fresh | test | 0.2377 | 13 | 4 | 0 | 9 | 0 | 1.0 | 1.0 | 1.0 |
| saved_recomputed | development | 0.2377 | 27 | 5 | 0 | 22 | 0 | 1.0 | 1.0 | 1.0 |
| saved_recomputed | test | 0.2377 | 13 | 4 | 0 | 9 | 0 | 1.0 | 1.0 | 1.0 |
| fresh_answer_service | test | 0.2377 | 13 | 4 | 0 | 9 | 0 | 1.0 | 1.0 | 1.0 |

Positive class is unanswerable/abstain: TP=correct abstention; FP=answerable rejected; TN=answerable accepted; FN=unanswerable accepted. This is a score-gate experiment using evaluation retrieval maxima, not end-to-end correctness or an assertion that accepted answers are correct. The actual answer service uses up to 20 reranked candidates, scope resolution, facet searches and evidence packing; its decisions can differ. In this captured run it generated 9 answers and abstained before generation on all 4 negatives. The separate fresh_answer_service rows in the abstention CSV report those observed responses, not just score predictions. The code default threshold is None, so deployments without the local setting do not enable this gate.

The documentation's lowest answerable score of about 0.32 belongs to the saved test set. The saved development minimum is 0.4449867904186249 and maximum unanswerable score is 0.030444350093603134; their midpoint gives the exact saved threshold. The perfect development score is in-sample. Four test negatives are too few for a general unanswerability claim.

## Citation-ID validity

`GeneratedStatement` requires citation-shaped IDs, and `validate_grounding()` rejects IDs absent from supplied evidence; responses enforce citation membership. Those structural checks do not test entailment. The captured worksheet independently joins each final rendered statement's IDs to returned source/page/chunk evidence. See capture counts below. No claim of semantic support follows from an ID resolving successfully.

Capture status/counts: `{"citation_pairs": 37, "completed": 13, "no_generated_claim": 4, "statements": 27, "valid_citation_pairs": 37}`. Counts refer to final rendered statements and statement–citation pairs, not human-verified atomic claims. No-claim/abstention rows are excluded from citation-rate denominators. The selected 13 questions are the full existing test split, with the historical exposure limitation above.

## Semantic citation support and manual review

`racevault_citation_audit.csv` contains verbatim final generated statements, their cited sources/pages/chunks, full retrieved evidence, the evidence actually supplied in the recorded final prompt, and blank judgement fields. It has one row per statement–citation pair plus explicit no-generated-claim rows. Atomic decomposition is deliberately left to reviewers; the same generating LLM is not used as a judge. Raw prompts are retained to detect truncation and distinguish supplied evidence from the larger retrieved chunk.

Review protocol:

1. Freeze and archive the captures. Record reviewer identity/date. Use two independent engineering reviewers where possible; neither should see the other's decisions before completing review.
2. Split compound generated statements into atomic claims in `atomic_claim_text`, duplicating rows with the same statement ID and a reviewer-assigned atomic suffix. Preserve the original generated text. Include unsupported factual clauses and uncited claims; do not silently discard them. Assess answer, conflict and limitation statements separately.
3. For each citation pair select Supported (the cited supplied passage entails the full atomic claim including values, units, conditions, scope and edition), Partially supported (only part is established or an essential qualification is missing), or Unsupported (no support, contradiction, or wrong source). Use Unreviewable only in notes when extraction is inadequate; do not count that as Supported. Do not use external knowledge to rescue citation support.
4. Mark citation_completeness as Complete/Incomplete/Not applicable at the atomic-claim level, considering all cited evidence together. A claim may need multiple citations even if an individual pair is only partially supporting. Mark wrong_source, wrong_vehicle_generation_or_edition and generation_error as Yes/No/Uncertain independently. Wrong generation means incorrect vehicle generation/revision; generation_error separately covers an answer-generation mistake despite usable context.
5. Inspect the authoritative PDF at the recorded physical page, resolving PDF-versus-printed-page offsets, extraction errors, table columns and scope. Record rationale and authoritative reference. Judge answer_correctness separately as Correct/Partially correct/Incorrect/Unreviewable; a supported quotation can still fail to answer the question.
6. Independently double-review, report raw agreement, then adjudicate disagreements with reviewer/date/rationale. Preserve original judgements. To report strict citation entailment use fully Supported pairs / reviewed pairs and report Partial separately; compute claim-level completeness using deduplicated atomic IDs, never duplicated CSV rows. Exclude abstentions/no-claim rows from support denominators and report them separately. No semantic rate is reported until manual review is completed.

The saved grounding-summary matches the illustrative two-answer/one-claim public fixture when recomputed; it is not evidence of perfect corpus answer grounding. The annotation-agreement fixture likewise demonstrates tooling rather than completed annotation. The public annotation plan records zero completed and zero double-labelled questions.

## Answer correctness

No current corpus gold claims/reference answers or completed independent answer judgements establish an answer-correctness rate. The 40-query corpus file contains zero gold claims. Retrieval hits, successful abstention, valid citation IDs and semantically supported claims are separate measurements; none alone establishes complete, correct answers. The generated worksheet makes correctness review possible but is not completed ground truth.

## Verification

53 existing evaluation and selected generation validation tests passed (`python -m pytest backend/tests/evaluation backend/tests/generation/test_service.py backend/tests/generation/test_evidence.py -q`, with backend/src on PYTHONPATH). Audit assertions independently recompute MRR, recall and hit rates from per-question records, verify saved aggregate arithmetic and replay historical calibration. All 160 fresh raw stage rankings were rescored with the unchanged `evaluate_stage` predicate and matched their per-question metrics exactly. Corpus label-resolution and absent-term checks are consistency checks, not human relevance review. Production Git diff remains empty.

## Limitations

- No identified 20-question set; all actual current questions are documented instead. A distinct set needs its file/hash or membership list.
- Existing test designation is preserved, but earlier exposure prevents claiming a demonstrably untouched test for the complete system; per-question tuning and human/LLM authorship are unknown.
- Labels are sparse author-verified literal predicates, not independently adjudicated exhaustive qrels. Keyword absence is an imperfect answerability proxy. No actual corpus inter-annotator agreement is established.
- Only 9 answerable test questions, covering tyre data and Porsche manuals, and 4 test negatives. Generalisation across unseen engineering domains, families and revisions is unmeasured.
- The run reuses existing index/embeddings. Original extraction/index build seed and exact historical dirty trees are unavailable; cross-machine bitwise reproduction is not asserted. Private PDFs and cached models are external prerequisites; hashes do not redistribute those assets.
- Citation capture uses 13 questions because only 13 current test questions exist. Semantic support, completeness and answer correctness remain unreviewed; no synthetic labels substitute for human judgement.
- Threshold-only replay differs from the complete answer service. Test separation from the saved calibrator does not establish that test outcomes never influenced broader choices.

## Claims supported for the thesis

- At the recorded source commit, settings and unchanged 64-document/9,212-chunk store, a fresh run evaluated all 40 authored questions with their existing family assignments and reproduced the recorded final split retrieval aggregates.
- On the 9 answerable questions in the existing test split, BM25, semantic, fused and reranked MRR are respectively 0.847222, 0.888889, 0.870370 and 0.944444 under the repository's literal relevance predicates; reranked Recall@10 is 0.944444.
- The saved threshold is exactly reproducible from its 27-question development input. At the fixed runtime threshold 0.2377, the separate 13-question test-score evaluation accepts 9 answerable questions and rejects 4 labelled unanswerable questions; this is a small fixed-threshold regression result.
- In 9 generated test-split answers, all 37 recorded statement–citation pairs resolve to supplied evidence; the 4 abstentions have no generated claims. A manual worksheet preserves 27 generated statements. This establishes citation-ID validity for these captures only, with no empirical semantic-support or answer-correctness rate.
