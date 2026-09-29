# RaceVault benchmark provenance

Audited commit: `5e669e763b92db944ac86ad22907fb7b0ecfb619`. Dataset SHA-256: `2c0ecd96991945ce3d6a69153880a9d771f8f7e13fb2cb9320efc8b822b50cee`.

## The requested 20-question set does not exist in the inspected repository

The current `evaluation/queries.json` contains **40 questions (31 answerable, 9 expected-empty)**. `queries-legacy-v1.json` contains **16 (15 positive, one wrong-revision negative)**. The public example contains 8. Saved runs contain 15, 16, 27, 13 or 40 questions. No 20-question benchmark, membership list or provenance was found in the working tree or reachable benchmark Git history. A claim about a particular 20-question set requires its exact file/version or question IDs; no arbitrary 20-question subset was manufactured.

## Recoverable creation history

1. Commit `ac6fc3d` (2026-08-14, recorded Git author Niket Shah) introduced the 16-query evaluation. The question-writing procedure, individual label authors, annotator identities, independent review and pre-tuning freeze are unknown. Git authorship does not establish who judged relevance or whether AI assisted authoring.
2. Commit `cce0fe7` (2026-08-24, recorded Git author Niket Shah) added the v2 builder and dataset. `evaluation/build_dataset.py` reads the 16 legacy questions, preserves their predicates, assigns grade 3 to legacy labels, and adds 16 positive questions and 8 negatives as literal definitions. The data card describes labels as author-verified, not independently annotated. Literal curation plus automatic validation is established; human-versus-LLM authorship of individual text/labels is unknown.
3. `verify()` checks source/page/text predicates against indexed chunks and checks absence of selected keywords for the new negatives. It neither establishes exhaustive qrels nor proves semantic unanswerability. The current read-only check is preserved in `validation_evidence/label_resolution.json`; these resolved chunk IDs are audit outputs, not original chunk-ID qrels.
4. `SPLIT_BY_FAMILY` overrides initial literals, including the seven Australian questions initially marked test in NEW_QUERIES: they are development in the actual output. There is no separate calibration split: all 27 development questions enter saved threshold selection. Legacy queries without a family default to development.
5. The builder says legacy test questions were not consulted for changes made since its construction. However, 8 of the current 9 answerable test questions appear in both `representative-baseline.json` and `representative-hardened.json`; the ninth appears in the legacy full-corpus and after-steps runs. Historical exposure is established. Exactly which question drove which retrieval parameter change is unknown. These are existing test-split regression results, not demonstrated untouched validation of the entire system.

## Split and label contract

The actual positive families are five development families and two test families; the mapping defines nine possible families, but PCC Asia/Other have no current questions. Null-family negatives are allocated explicitly. The wrong-revision negative is a scope-empty query, not a globally absent topic. No positive family or labelled source path crosses the current splits. No split was changed for this audit. The model validator checks the declared family field, rather than all source paths; this audit checks both.

| Split | Family | Questions | Answerable | Expected-empty |
| --- | --- | --- | --- | --- |
| development | unassigned | 5 | 0 | 5 |
| development | abs-m5 | 5 | 5 | 0 |
| development | cup-software-updates | 1 | 1 | 0 |
| development | ms6-ecu | 2 | 2 | 0 |
| development | part-catalogue-992 | 1 | 1 | 0 |
| development | pcc-australia-regulations | 13 | 13 | 0 |
| test | unassigned | 4 | 0 | 4 |
| test | porsche-technical-manual | 3 | 3 | 0 |
| test | tyre-data | 6 | 6 | 0 |

Relevance is a case-insensitive exact source path, optional PDF page-number membership and AND of literal text fragments within `evidence_text`. No original chunk IDs are labelled; all label_id values and gold_claims are empty. Grade 3 is the default, with the ABS data-sheet alternative graded 2. Relevance matching ignores grade for MRR/recall. Labels are sparse passage predicates, not exhaustive chunk-level relevance judgements. Independent review: not established (data card explicitly says not independently annotated). The public 200-query annotation plan reports zero completed/double-labelled queries.

## Question-by-question record

For every entry: independent reviewer = unknown/not recorded; individual relevance adjudicator = unknown. The recorded Git author is not asserted to be that adjudicator. Source family, split, filters and labels below are copied from the frozen dataset. `development/calibration` means the question was included in the saved calibration input; it does not prove that it influenced a retrieval parameter.

### reg_joker_tyre_definition

What is a Joker Tyre?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: pcc-australia-regulations; category: regulation_definition; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 6, "text_contains": ["Joker Tyre", "Regulation S16.3"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_ff6c5f631854ebe913c8c34f258667a9.

### reg_control_component_requirement

Are control components mandatory?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: pcc-australia-regulations; category: regulation_concept; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 6, "text_contains": ["Control Component", "mandatory"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_ff6c5f631854ebe913c8c34f258667a9.

### reg_slick_tyre_definition

Which regulation defines a slick tyre?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: pcc-australia-regulations; category: regulation_definition; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 7, "text_contains": ["Slick Tyre", "Regulation T12"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_a153ca123ff198e102ad0ce097f4d7db.

### reg_round_alteration_precedence

What takes precedence when the regulations are altered for a specific round?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 8, "text_contains": ["Supplementary Regulations", "take precedence"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_0bcd8bb20beb546d85592636b797b155.

### reg_driver_minimum_age

What is the minimum driver age?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 9, "text_contains": ["seventeen (17) years"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_75b5c4b7867ddb4b1d01facead0cee98.

### reg_2026_calendar

Which circuits are on the 2026 championship calendar?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: pcc-australia-regulations; category: regulation_table; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 10, "text_contains": ["Round", "Circuit", "Albert Park"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_2c78142b7d08c40136664753df1d0786.

### tyre_n3r_dimensions

What are the N3R tyre dimensions and recommended wheel width?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: tyre-data; category: technical_table; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "tyre_data", "vehicle_generation": "992.1", "season": 2025}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Tyre Data/992.1/Combined/Porsche Technical recommendations N3_N3R_2025.pdf", "page_number": 2, "text_contains": ["31/71-18", "N3R", "2197"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_32aed2741216e83e7f7c3f6335b98f3a.

### tyre_n3_rolling_circumference

What is the rolling circumference of the front N3 tyre?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: tyre-data; category: technical_table; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "tyre_data", "vehicle_generation": "992.1", "season": 2025}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Tyre Data/992.1/Combined/Porsche Technical recommendations N3_N3R_2025.pdf", "page_number": 2, "text_contains": ["30/65-18", "N3", "2030"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_32aed2741216e83e7f7c3f6335b98f3a.

### tyre_shoulder_temperature_delta

What is the maximum temperature difference between the inside and outside tyre shoulders?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: tyre-data; category: technical_recommendation; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "tyre_data", "vehicle_generation": "992.1", "season": 2025}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Tyre Data/992.1/Combined/Porsche Technical recommendations N3_N3R_2025.pdf", "page_number": 3, "text_contains": ["inside shoulder", "outside shoulder", "20"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_979a04bfbd3dbd14cee46a474fe51a45.

### tyre_unlisted_track_recommendation

Which recommendation applies to tracks that are not specifically listed?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: tyre-data; category: technical_recommendation; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "tyre_data", "vehicle_generation": "992.1", "season": 2025}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Tyre Data/992.1/Combined/Porsche Technical recommendations N3_N3R_2025.pdf", "page_number": 4, "text_contains": ["all other tracks", "STANDARD recommendations"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_7080ff28f08cfe1d6d3a9cf13ec5a898.

### tyre_n3r_standard_cold_pressure

What is the standard minimum cold pressure for the rear N3R tyre?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: tyre-data; category: technical_table; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "tyre_data", "vehicle_generation": "992.1", "season": 2025}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Tyre Data/992.1/Combined/Porsche Technical recommendations N3_N3R_2025.pdf", "page_number": 6, "text_contains": ["13 J 18", "1.2 bar", "17.4 Psi"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_7bb9956e39700a69eb65c67a43b4152a.

### manual_intended_use

Is the Porsche 911 Cup 992 II designed for public-road driving?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: porsche-technical-manual; category: manual_concept; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "technical_manual", "vehicle_generation": "992.2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Porsche Technical Manuals/992.2 Technical Manual.pdf", "page_number": 3, "text_contains": ["circuit races", "racecar"], "relevance_grade": 3}, {"label_id": null, "source_path": "Porsche Technical Manuals/992.2 Technical Manual.pdf", "page_number": 3, "text_contains": ["cannot be approved", "public roads"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_105391d4b3c51d7d961e5e699c2ef8c6; label 2: chk_ed35f9d646190257f4ab0be316305ae4.

### manual_main_voltage_switch

Which switch position turns the main voltage supply on?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: porsche-technical-manual; category: manual_procedure; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "technical_manual", "vehicle_generation": "992.2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Porsche Technical Manuals/992.2 Technical Manual.pdf", "page_number": 9, "text_contains": ["main voltage supply", "Switch down: ON"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_e09ccca9a904dc473a5be5cd3b2d8adf.

### manual_fire_system_test

Why must the fire extinguisher system be tested in test mode?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: porsche-technical-manual; category: manual_safety; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"document_class": "technical_manual", "vehicle_generation": "992.2"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Porsche Technical Manuals/992.2 Technical Manual.pdf", "page_number": 9, "text_contains": ["test mode", "activated unintentionally"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_62e9853f1870d32d99d0c813cd35ef82.

### failure_wrong_regulation_revision

What is a Joker Tyre?

- Origin: legacy literal question/labels, upgraded by builder.
- Family: unknown/unassigned; category: wrong_revision; split: development/calibration.
- Label: unanswerable in supplied filter scope. Minimum distinct sources: 1.
- Filters: `{"document_class": "regulation", "championship": "PCC Australia", "season": 2026, "revision": "Version 1"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[]`.

### conflict_n3r_pressure_sources

minimum cold pressure N3R

- Origin: legacy literal question/labels, upgraded by builder.
- Family: tyre-data; category: multi_source_conflict; split: test (existing test designation, not proven untouched).
- Label: answerable (author-assigned). Minimum distinct sources: 2.
- Filters: `{"document_class": "tyre_data", "vehicle_generation": "992.1"}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Tyre Data/992.1/Combined/Porsche Technical recommendations N3_N3R_2025.pdf", "page_number": null, "text_contains": ["13 J 18", "Mini cold pressure"], "relevance_grade": 3}, {"label_id": null, "source_path": "Tyre Data/992.1/Combined/01_2025_Tech_Info_GT3_Cup_Michelin_Preco.pdf", "page_number": 2, "text_contains": ["tyre pressure", "Michelin Precos"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_7bb9956e39700a69eb65c67a43b4152a, chk_1d7c04169bc6b3b2d3f1d186549640a3, chk_2c12cc9b2020700896b55247b083943c, chk_3344b38d2ef74f7195fdf30fddbd5800, chk_a8cc84dfc79b78daae9c5227134f3ead, chk_ce825ee0ab0f4ef74c1a9a81177a0440; label 2: chk_7350f900afcfefb3e34195cc2e4ab066.

### aus_current_minimum_weight

What is the minimum weight of the car in Carrera Cup Australia?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2026}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 26, "text_contains": ["minimum of 1300 kg"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_34441abb6093c6ce29e5de8b28820d7b.

### aus_current_racing_weight

What minimum racing weight must a Carrera Cup Australia car achieve?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2026}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 26, "text_contains": ["1385 kg"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_b393ab6f56457744ccd7b57abc988dab.

### aus_2025_minimum_weight

What was the minimum car weight in the 2025 Carrera Cup Australia regulations?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2025}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2025_Porsche_Carrera_Cup_Australia_Sporting_Technical_Regulations_V1.pdf", "page_number": 47, "text_contains": ["1295 kg"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_d4939d6a52cf181aaa147189b40f757b.

### aus_driver_minimum_weight

How much must a driver weigh in Carrera Cup Australia, and what happens if they weigh less?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2026}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 26, "text_contains": ["85 kg", "ballast"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_fd9c342a7f8d616d4aba51ea25f621ea.

### aus_fuel_remaining

How much fuel must remain in the car during a track session?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2026}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 19, "text_contains": ["2.0 kg of fuel"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_72e1f8fdf838251f66294c7558c5f2c5.

### aus_driver_age

How old must a driver be to compete in Carrera Cup Australia?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2026}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 9, "text_contains": ["seventeen (17) years of age"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_75b5c4b7867ddb4b1d01facead0cee98.

### aus_joker_tyre_allocation

How many Joker Tyres may a driver use per round and per season?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: pcc-australia-regulations; category: regulation_rule; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{"championship": "PCC Australia", "season": 2026}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Rules and Regulations/PCC Australia/2026-Porsche-Equity-One-Carrera-Cup-Australia-Championship-Sporting-and-Technical-Regulations-Version-2_260602.pdf", "page_number": 17, "text_contains": ["six (6) front", "two (2) front"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_efc616194f898e7304b63fafac183c5f.

### abs_map_switch_torque

What tightening torque applies to the ABS map switch?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: abs-m5; category: component_specification; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ABS/Core/Operation_Manual_70618763_ABS_M5_Kit.pdf", "page_number": 21, "text_contains": ["1 to 2 Nm"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_8527820013d17b1545c6c25c804da2e9.

### abs_brake_line_diameter

What brake line should be used to plumb the ABS M5 unit?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: abs-m5; category: component_specification; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ABS/Core/Operation_Manual_70618763_ABS_M5_Kit.pdf", "page_number": 22, "text_contains": ["3.3 mm"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_666a7a2b5e7b355d415cab7d414f4012.

### abs_reset_after_drive_cycle_fault

How is the ABS reset after a drive cycle fault?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: abs-m5; category: component_procedure; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ABS/Core/Operation_Manual_70618763_ABS_M5_Kit.pdf", "page_number": 37, "text_contains": ["Power off - Power on"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_69455d11d84585eb06beb1102cfaae3a.

### abs_map_switch_positions

How many positions does the ABS function switch have?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: abs-m5; category: component_specification; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ABS/Core/Operation_Manual_70618763_ABS_M5_Kit.pdf", "page_number": 31, "text_contains": ["12-position map switch"], "relevance_grade": 3}, {"label_id": null, "source_path": "ABS/Core/Data_Sheet_70612107_ABS_M5_Kit.pdf", "page_number": 2, "text_contains": ["12-position function switch"], "relevance_grade": 2}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_81e986fc7e66312d36f919e2d146dbc5; label 2: chk_03b4eb8d4a060704b7c44bd38101d954.

### abs_hydraulic_unit_weight

How much does the ABS M5 hydraulic unit weigh?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: abs-m5; category: technical_table; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ABS/Core/Data_Sheet_70612107_ABS_M5_Kit.pdf", "page_number": 2, "text_contains": ["1,910 g"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_03b4eb8d4a060704b7c44bd38101d954.

### software_update_order

In what order must the PowerBox, logger and display be updated?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: cup-software-updates; category: component_procedure; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "PMRSI Other/2026-08-10_PA10_1918/992Cup_Manual_Software_Updates_V03.pdf", "page_number": 20, "text_contains": ["Update firmware PowerBox", "Update firmware display"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_29a6e7cbed5c5a59e85aa12268ad3e6e.

### ecu_temperature_range

What temperature range is the MS 6 harness connector rated for?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: ms6-ecu; category: technical_table; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ECU/engine_control_unit_ms_6-x_manual.pdf", "page_number": 74, "text_contains": ["Temperature range"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_50e2afbc28e71a6e8e7ea9e7c9253ce9.

### ecu_flywheel_sensor_type

Can the MS 6 use an inductive sensor for flywheel measurement?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: ms6-ecu; category: component_specification; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "ECU/engine_control_unit_ms_6-x_manual.pdf", "page_number": 29, "text_contains": ["flywheel measurement"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_11e3c0d298d15fbcb95b204a4b100a60.

### part_front_left_caliper

What is the part number for the front left brake caliper on the 992 GT3 Cup?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: part-catalogue-992; category: exact_identifier; split: development/calibration.
- Label: answerable (author-assigned). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[{"label_id": null, "source_path": "Part Catalogues/PA10_0842_911 GT3 Cup MY2021-2025 (Typ 992)_CW_11_26_English_en.pdf", "page_number": 109, "text_contains": ["9F1615427D"], "relevance_grade": 3}]`.
- Audit-resolved matching chunk IDs (not original annotations): label 1: chk_00d1979d88c0428d37301ae13400e3f5.

### neg_drs_activation

Where are the DRS activation zones?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: development/calibration.
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"DRS": 0, "drag reduction system": 0}`; zero counts do not prove semantic absence.

### neg_energy_recovery

How is the energy recovery system deployed on a qualifying lap?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: development/calibration.
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"energy recovery": 0, "hybrid deployment": 0}`; zero counts do not prove semantic absence.

### neg_push_to_pass

How many push to pass activations does each driver get?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: development/calibration.
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"push to pass": 0}`; zero counts do not prove semantic absence.

### neg_success_ballast

How much success ballast is added after a race win?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: development/calibration.
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Development family documented as available for tuning; per-question retrieval tuning history unknown.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"success ballast": 0}`; zero counts do not prove semantic absence.

### neg_budget_cap

What is the budget cap for the season?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: test (existing test designation, not proven untouched).
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Excluded from saved threshold calibration; individual pre-test tuning exposure unknown. Negative topics checked by builder across the corpus.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"budget cap": 0}`; zero counts do not prove semantic absence.

### neg_turbo_boost_limit

What is the maximum turbocharger boost pressure permitted?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: test (existing test designation, not proven untouched).
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Excluded from saved threshold calibration; individual pre-test tuning exposure unknown. Negative topics checked by builder across the corpus.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"turbocharger boost": 0}`; zero counts do not prove semantic absence.

### neg_sprint_shootout

What is the sprint shootout format?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: test (existing test designation, not proven untouched).
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Excluded from saved threshold calibration; individual pre-test tuning exposure unknown. Negative topics checked by builder across the corpus.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"sprint shootout": 0}`; zero counts do not prove semantic absence.

### neg_rallycross_joker

How does the rallycross joker lap work?

- Origin: literal NEW_QUERIES/negative() definition in builder.
- Family: unknown/unassigned; category: out_of_corpus; split: test (existing test designation, not proven untouched).
- Label: unanswerable (author-assigned; keyword absence proxy). Minimum distinct sources: 1.
- Filters: `{}`.
- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. Excluded from saved threshold calibration; individual pre-test tuning exposure unknown. Negative topics checked by builder across the corpus.
- Exact original relevance predicates: `[]`.
- Audit keyword occurrence counts: `{"rallycross": 0}`; zero counts do not prove semantic absence.

## Evaluation inventory

All inspected evaluation code, tests, scripts, labels, cards, settings and saved-result files are enumerated with hashes in `validation_evidence/input_inventory.json`. Local PDFs/extraction/chunk artifacts and database contents are private corpus inputs, not independently annotated benchmarks. `.artifacts/reports/full-ingestion.json` currently records a failed ingestion attempt; its totals must not replace the live store snapshot.

| Path | Bytes | SHA-256 |
| --- | --- | --- |
| .artifacts/evaluation/after-steps-1-3.json | 98395 | de7cfeb895eb3f7196920f11064d174b5f740b76f19d16dd1cd37ea8cc13bf8c |
| .artifacts/evaluation/annotation-agreement.json | 99 | 74248d219c62d6c5c55ed2ed61cda318d281a13994292e60fae27f05f2b32ba7 |
| .artifacts/evaluation/corpus-v2-all.json | 247275 | 8c4c58372a03dc6b1908b091144b51c6d88c480a060cfccd95056178d88ccbba |
| .artifacts/evaluation/corpus-v2-development.json | 182702 | 83f91c9f0b33f1e960d8c7bbeaac368be232ee3b86ddacb960370946a22d2432 |
| .artifacts/evaluation/corpus-v2-test.json | 116836 | 13cda2ef0fdee12711831c38e625ce161686c3fe85e2b4c7dc65fb35fab2b25f |
| .artifacts/evaluation/dashboard.html | 1089 | 27aa78bd33cb96f304c5d13f1a04c4d12366af9a99c1c6492d0f034b2ab229f4 |
| .artifacts/evaluation/failure-atlas.md | 150 | 7fd87c4fb53c44c7db9ce4c362a50a7d3c23679928ae9d433a5fe7b86b7eddb6 |
| .artifacts/evaluation/full-corpus.json | 14440 | 0c77746eb756e6681ce5c948b6216d3bd0f3b2b98266ee9e747c84a42b18a1c9 |
| .artifacts/evaluation/grounding-summary.json | 393 | e35715551cd842a1a0e6842e2c77f29f21064e3b9259e74fa461675b8303a493 |
| .artifacts/evaluation/representative-baseline.json | 13005 | 50d3468f977825bdd742925bc1ecaa73bf3989a60bb21d4ba1010e3e5ae3b86f |
| .artifacts/evaluation/representative-hardened.json | 13543 | c130bffe3dc3673d6a2a5aa8916f577f1cf464462bee1b554806e375017775fb |
| .artifacts/evaluation/sufficiency-calibration.json | 428 | 1378d2298e1639ce70bfe799d6d56adf4b6501ecb0d8b00fd744faa9d48bb61b |
| .artifacts/evaluation/visual-gate.json | 39 | f5cea5df45f2112e765085448feb577c262af0849c32967b0d41c06f5474ba95 |
| .artifacts/reports/full-ingestion.json | 11023 | 88474569851fd38505089b0b55ed9a8cdf029cafc856eac2985c05293347e732 |
| .artifacts/reports/great-britain-metadata-refresh.json | 1121 | c831e629a0ea317c6267d72ae615f1b69c2b24f2e73594a62339a6ca42b34046 |
| .github/dependabot.yml | 407 | f682415fb7e7ae9749f4c696ff983341caf5795557c2bc75d24b2758199d487f |
| .github/workflows/ci.yml | 1764 | 52a76d8ecc40f9c9e088e4997e9b37c640f3cdf8132596b321b0916ec0dcb57f |
| .github/workflows/full-benchmark.yml | 1222 | f9f2fb79ae7a9c59008f4b53c0b0550ddd908d486f036d949ecbb12daec80376 |
| .github/workflows/security.yml | 1035 | ca406f586c6f82eb54bd2086b6549ca8421954442d26371e73072eef44d5748d |
| backend/requirements.lock | 2586 | d29f5b823186238881cda858a6ff8c369bae4bb29133fa67e9acbc086bb86eb6 |
| backend/src/racevault/config.py | 7239 | cba96344913407d1a6911340a5e8061c92197dfd6c1aafbfdc0c8f9238944ddd |
| backend/src/racevault/evaluation/__init__.py | 37 | 89d8294a47384a25feb31a011ec0c562bc69fd9b5e6b893ef10aaa912d00b851 |
| backend/src/racevault/evaluation/annotation.py | 1838 | f966f5a7e463c360f4d9e96704a7510bd6b0bb6575916432fc8e568bd3734c6a |
| backend/src/racevault/evaluation/annotation_cli.py | 1016 | 63e0ab185c5c8a45cd7b54e45aa407ab5648ae23194a6fce3fe14304913d6cc5 |
| backend/src/racevault/evaluation/calibration.py | 4584 | 658ae040fa5f110a310f8a74a386d602000c59006b1d77bee83e80fcffe6bc8b |
| backend/src/racevault/evaluation/calibration_cli.py | 1450 | c9a1144b6a1e1dd7af27a395081c23fb96bf9b2d4ee5590671e5f726cb43c7bb |
| backend/src/racevault/evaluation/cli.py | 7341 | 66f052920ca819efd2e6f15d61a36df7134a383416b5c3e4b21029a00b0afb74 |
| backend/src/racevault/evaluation/experiment.py | 2224 | 8279400a8eaf3fc8463eed66ddd1a85aca964008c212d39e0687b39283331fc8 |
| backend/src/racevault/evaluation/grounding.py | 4918 | 36a9cbec84f1e6da3cf69e71c11b089b829ca6dbba167b18ca6e3f7d078d6a9b |
| backend/src/racevault/evaluation/grounding_cli.py | 1256 | 559260aad0bacc621111cc809073689cb6ffdce398f1fd841af80e4085ec14ab |
| backend/src/racevault/evaluation/metrics.py | 10194 | d0d4376d4c6c5459a38086cd50b91bdccdc445399b7939df9517adbbedb79681 |
| backend/src/racevault/evaluation/models.py | 7001 | 35c62fdf3a2c43989088b471c8d8ee6b5d2ebcdd3c70f49ef4568b639414cf10 |
| backend/src/racevault/evaluation/runner.py | 7769 | 75a105c239a08af54f76d9663807bcd3ed8777d21fb6345a0844f399f1551ff3 |
| backend/src/racevault/evaluation/visual.py | 1747 | c90e850dbf6b25cf06df29a97d58a050f542881491548947cdf3e1dca8f1ba5b |
| backend/src/racevault/evaluation/visual_cli.py | 935 | f17611fac80db8d369198d3a0db5d61c4b39fa4b44a2de92451d170a9633cc09 |
| backend/src/racevault/fusion/models.py | 2934 | f73c8310f509b32fe8d4e9e1e19a78d5091127381ac086eb73d57c6a1380049e |
| backend/src/racevault/fusion/pipeline.py | 3845 | e4fdf0e45ab9c503e107bd99af851cabae0f1500f185becbdc70290094038e7e |
| backend/src/racevault/fusion/reranker.py | 4745 | 1f6df7c5c858123631de455ebb1c332753297f1bc3abe35c6b4aa548eb1f3491 |
| backend/src/racevault/fusion/rrf.py | 2531 | dbf3bd244b6bc24a1d99e6e8001d64f46d2658cff9debfdfb534a2be78b5da45 |
| backend/src/racevault/generation/evidence.py | 23286 | 289941648cd6387123545e38071c887b2e04eae5602572dad4cbdf507b4567e0 |
| backend/src/racevault/generation/ollama.py | 11933 | 6418e29c23f8fa6a9be5f2705a9e0c458725d548692d00f0aafa03f90260912f |
| backend/src/racevault/generation/service.py | 41691 | abaeeb771e0fb226ce84885616a83a28e386fbb907c77dcbc9f786dd8b32049c |
| backend/src/racevault/lexical/mapping.py | 5637 | 42e609cb905f6a6ab6d692e5f1b75c95e97b6f7f64ff78541cf3d387569f8a51 |
| backend/src/racevault/lexical/query.py | 3608 | a0c2983168eb88ebbd5c4f96ea04e09cf3ede7654d6caf1312fa2c12782d0846 |
| backend/src/racevault/lexical/synonyms.py | 4515 | 302f76c08ce239b3f21b221857761c6854900f3da99e584f70f94e90d1363a9b |
| backend/tests/evaluation/__init__.py | 24 | 88a80d4bfcae3fc4c7a344631bb8d428947c663aaef56304704095cc6a8379c0 |
| backend/tests/evaluation/test_annotation.py | 604 | 2adab710083d421d2c7c1de6528d338cb427b2821cf1355bda0543fe7d9ba07b |
| backend/tests/evaluation/test_calibration.py | 2825 | 728e3a70b12ebccf293698595c4a6da86e2ed442bdec31cdd5a33868a442acfb |
| backend/tests/evaluation/test_experiment.py | 264 | bba337dc22e37840b95ef1c0fda1a10dcf018b1141f04e180944b83d613077ee |
| backend/tests/evaluation/test_grounding.py | 1539 | e67b1f139ce8905ab002ee3a849bca042509ce8c9a5025b345913b1e6cc16c26 |
| backend/tests/evaluation/test_metrics.py | 4334 | 25b8c55e546d9cc8e30ed17ca6ce08dcf1e9d808b09f77ba0623a3e4d9c3e3c9 |
| backend/tests/evaluation/test_visual.py | 1462 | e08e71ce1a0703b9527d0c9cf04540d29c3d0d5aa246108428e525bf19f339e7 |
| compose.yaml | 3472 | da8302327974615b4f30c9fe5f9510c67ffc0a994dd9e3fa13c2e6ddf78cf0bf |
| corpus/full_documents.json | 16184 | f89124f666a2c4dc6b887e900e561ced2b43a6bddbae20398828bdc1ceec6b2e |
| corpus/public_sources.json | 288 | 7094a1eb1e3dd0fbca9c3e42ebd87a98651e7de29038deec2d08f204fc338070 |
| corpus/representative_documents.json | 2107 | 17edc2af652ec3d9ded2acf1dae9216a3ab76a223ed57894442c7765a18c299f |
| docs/architecture-context.md | 10993 | 74ee118155fe05ddd36726e86344a966231b2e01a08bdafe1f6114125baa5476 |
| docs/chunking.md | 4015 | 7059f4aac2653f01e790ec5b26f9a36f041fe5db28a6f998dd97d53d50e18b71 |
| docs/data-card.md | 2831 | 0dc7e07d28cfcb0a4b6cccc0920587b5af341bc6c294c933bd4ceeec7d8d85ed |
| docs/design-decisions.md | 4637 | dbae668364878775c9687bfa84c95a9f76bef34050ea339418f164fc045b16e7 |
| docs/evaluation-and-corpus.md | 5778 | 9b03fa962beedb3be4ccef614f0a3c86a7fc191e387ced1e78aead7b2993d484 |
| docs/evidence-controller.md | 4811 | 6728617dfa0aad84118826774aab814201b690f1bcec0873c4f43d4970ece3c7 |
| docs/evidence-interface.md | 4482 | 9272b016e1ad6e062cdfbfaaadf8f12d6a7c45f957642b97abb56474b95cbe8f |
| docs/extraction.md | 3252 | 2c9088215e3efe5bfd46c101893998491f664ab44c84f689f8217689cc09a19f |
| docs/grounded-generation.md | 7018 | b0e50e76ab74579a22f706ed9070546f6dac6c0cce7f2427b277aaa0d1db85f5 |
| docs/hybrid-retrieval.md | 5323 | 8d1c70fa52ad5e2a586d30b0786381eb66c1c6133e935f7d529da3d873cda5cb |
| docs/lexical-retrieval.md | 5711 | c37fa30706f5668fd9e37a7c90937cc40f065fe9e2278797c18b58cc550ab3af |
| docs/metadata-model.md | 1101 | 37522368cbd937b96581acdc8b0525e8881ee08f38cc91e70e4e006b50e6a533 |
| docs/milestones.md | 13903 | 91d32f06f93af49322d8c43a87de55160ccecd01817f48b30623b448a55b250d |
| docs/model-card.md | 1647 | 6759800dde18f3a1b816223c73965d3d2670a59a2d2d615a0926a54f7c7c27ed |
| docs/operations.md | 3592 | e52729bcfb6822e189c8495d5fb47168faeb1097d2732aa22bfd9dad186d558f |
| docs/product-api.md | 10333 | 84103effc7122fd1760c2332f00b3b3aef27df4d2bbc686b6860e3b75c07293c |
| docs/semantic-retrieval.md | 3745 | 769b847a192285343277733407b7a0f57432b4f0f6fb54a7751e52f2e89bb1e8 |
| docs/showcase-demo.md | 743 | 7a0a74f8d8a50b27775487c808b313b942efca6644136c39f87202f892b2d5c9 |
| docs/system-card.md | 2631 | ecec829ef03a54c30518adbe73376067350022455bed127ef7bd72d21185e5a3 |
| docs/technical-report.md | 3788 | 7f63a6c5278f5afc7b9d599af0f4f846ef4301775203054d3735a422b971df97 |
| docs/visual-retrieval-experiment.md | 867 | d317e31a4ef056e1b7f12d6a605241a5fd74d0c20f60a1fc9c91b8c50cde1183 |
| evaluation/build_dataset.py | 18103 | 75609afa695a54f4484d811f93823fb849814084b1ce69ac565fab8cf564079d |
| evaluation/build_validation_record.py | 47876 | b45dc4f2d036edef203727ebdb01dcce57b80d9f31021095f23081f5f2340793 |
| evaluation/public/annotation-pairs.example.json | 365 | 1488052b59bf567cce1e26aec02d7406915ed335c69365869fb78fb587147647 |
| evaluation/public/ANNOTATION.md | 1266 | 8fdea1fd3c1a1926b89bc4e0d7905bd78c9cadf8da8e39e8f7a82d27605aa46f |
| evaluation/public/annotation_progress.json | 417 | d7939538b6fe7213414b54c074932d28924bdc5a00765eaec5527f8c4c0cfece |
| evaluation/public/fixture_sources.json | 1648 | 5e215a5a358919526cd7669b3714556e6b9c57cdb015166aef9d9fee251c2568 |
| evaluation/public/grounding-judgements.example.json | 813 | c042d7ae4ac1f00f29443913145557711bfed379f4d7a9b8e6dfc999988b2cb3 |
| evaluation/public/queries-v2.example.json | 4428 | cb994e01a430adc805a6813fbb4d9e6d7b74ba74f3a588a9ba2369bb6653dace |
| evaluation/public/visual-gate.example.json | 212 | 20d5805adc5c066c148a00bef226d13865ca82bcfe0f82f2092bed7448b02226 |
| evaluation/queries-legacy-v1.json | 9181 | e17120dbe985b0e2a22d713eb7e0c0c901042938bbe8e58a45c98f56773e342c |
| evaluation/queries.json | 45217 | 2c0ecd96991945ce3d6a69153880a9d771f8f7e13fb2cb9320efc8b822b50cee |
| evaluation/reproduce_validation.py | 13024 | c4045718e9bb05f45b88dbdaae335bdf546aedb2ecd5349bf522dc24d78216e9 |
| README.md | 12152 | 871b476351aaf3aa1ee89caba1f334ec2596cfe3486966c2bd18126ba6ff0a3d |
| scripts/build_benchmark_dashboard.py | 2974 | c67ef060a8397daf0b2ecfa1621c3eefac255e786450f374b68adc362cdf2bad |
| scripts/build_failure_atlas.py | 2152 | e982ce0e529535c1f94793d56845dd37bc84b39bbfef80e061db949244ed089c |
| scripts/build_public_fixture_pdfs.py | 4144 | fa1c3e58985c8e7a3ce3c39f4907b35ce3002e2128ef635ddc2029db8da4a1b6 |
| scripts/load_test.py | 3860 | d459ec01e4bd7588828243b19155efaedbfb59efe0c8c34e615a184d22bf4794 |
| scripts/run_benchmark.py | 2315 | d3919cb43ec1b666c16dbbffd9dd35e838e7e4ae160ed5aa910acca8e186a9cc |
| scripts/validate_corpus.py | 1689 | d22e64f960d681f6901e4c694dc644e555ca70d67cf8b39858cb073fa536a47e |

Saved corpus-v2 development/test runs have dataset hash matching the current file, commit `75c8f3e...`, dirty_worktree=true, seed 17 and pinned model revisions. Their configuration hashes are present, but the exact dirty source tree and full configuration payload are not. The earlier all-split v2 run has a different dataset hash; do not combine it with final-split scores as one experiment. Full saved fingerprints remain in `validation_evidence/historical/`.
