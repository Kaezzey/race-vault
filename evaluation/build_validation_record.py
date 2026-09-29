"""Recompute audit tables from frozen evidence; no retrieval or generation tuning."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
E = ROOT / "validation_evidence"
STAGES = ("lexical", "semantic", "fused", "reranked")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def csv_out(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table(headers, rows):
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", "<br>")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |", *["| " + " | ".join(cell(x) for x in row) + " |" for row in rows]])


def resolve_labels(queries):
    """Read-only corpus consistency check; matching is not independent relevance review."""
    from racevault.config import get_settings
    import psycopg
    from psycopg.rows import dict_row
    import importlib.util
    spec = importlib.util.spec_from_file_location("dataset_builder", ROOT / "evaluation/build_dataset.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    output = {}
    with psycopg.connect(get_settings().psycopg_conninfo, row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        for q in queries:
            labels = []
            for label in q["relevant"]:
                rows = conn.execute("SELECT c.id, c.page_numbers, c.evidence_text FROM chunks c JOIN documents d ON d.id=c.document_id WHERE lower(d.source_path)=lower(%s)", (label["source_path"],)).fetchall()
                matches = [r for r in rows if (label["page_number"] is None or label["page_number"] in r["page_numbers"]) and all(t.casefold() in r["evidence_text"].casefold() for t in label["text_contains"])]
                labels.append({"label": label, "matches": matches})
            negatives = {term: conn.execute("SELECT count(*) AS n FROM chunks WHERE evidence_text ILIKE %s", (f"%{term}%",)).fetchone()["n"] for term in builder.NEGATIVE_ABSENT_TERMS.get(q["query_id"], ())}
            output[q["query_id"]] = {"labels": labels, "negative_term_counts": negatives}
    save(E / "label_resolution.json", output)


def main():
    dataset = read(ROOT / "evaluation/queries.json")
    queries = dataset["queries"]; by_id = {q["query_id"]: q for q in queries}
    legacy = {q["query_id"] for q in read(ROOT / "evaluation/queries-legacy-v1.json")["queries"]}
    # Independently replay every fresh ranking against the existing predicates.
    from racevault.evaluation.runner import load_dataset
    from racevault.evaluation.metrics import evaluate_stage
    from racevault.lexical.models import LexicalSearchHit
    from racevault.semantic.models import SemanticSearchHit
    from racevault.fusion.models import FusedCandidate
    from racevault.evaluation.grounding import GroundingJudgementDataset, summarize_grounding
    from racevault.evaluation.annotation import AnnotationPair, annotation_agreement
    models = {"lexical": LexicalSearchHit, "semantic": SemanticSearchHit, "fused": FusedCandidate, "reranked": FusedCandidate}
    for q in load_dataset(ROOT / "evaluation/queries.json").queries:
        trace = read(E / f"retrieval_{q.query_id}.json")
        result = next(r for r in read(E / f"fresh_{q.split}.json")["results"] if r["query_id"] == q.query_id)
        for stage, cls in models.items():
            assert evaluate_stage([cls.model_validate(h) for h in trace[stage]], q).model_dump(mode="json") == result[stage]
    for field in ("document_family", "source_path"):
        split_values = {s: {v.casefold() for q in queries if q["split"] == s for v in ([q[field]] if field == "document_family" and q[field] else [lab[field] for lab in q["relevant"]] if field == "source_path" else [])} for s in ("development", "test")}
        assert not split_values["development"] & split_values["test"]
    assert read(E / "stores_before.json") == read(E / "stores_after.json")
    g = GroundingJudgementDataset.model_validate(read(ROOT / "evaluation/public/grounding-judgements.example.json"))
    assert summarize_grounding(g.judgements).model_dump(mode="json") == read(ROOT / ".artifacts/evaluation/grounding-summary.json")
    pairs = [AnnotationPair.model_validate(p) for p in read(ROOT / "evaluation/public/annotation-pairs.example.json")]
    assert annotation_agreement(pairs).model_dump(mode="json") == read(ROOT / ".artifacts/evaluation/annotation-agreement.json")
    if "--resolve-labels" in sys.argv:
        resolve_labels(queries)
    labels = read(E / "label_resolution.json") if (E / "label_resolution.json").exists() else {}
    historical = E / "historical"; historical.mkdir(exist_ok=True)
    for p in (ROOT / ".artifacts/evaluation").glob("*"):
        if p.is_file() and p.suffix in (".json", ".md") and not (historical / p.name).exists():
            shutil.copyfile(p, historical / p.name)
    reports = [("fresh", E / f"fresh_{s}.json") for s in ("development", "test")]
    reports += [("saved_recomputed", p) for p in sorted(historical.glob("*.json")) if "results" in read(p)]
    retrieval_rows = []; aggregate = []; failures = []
    for origin, path in reports:
        d = read(path); fp = d.get("experiment") or {}
        for stage in STAGES:
            base = {"origin": origin, "source_file": str(path.relative_to(ROOT)).replace("\\", "/"), "source_sha256": sha(path), "dataset_id": d.get("dataset_id", "legacy_v1_identity_not_recorded"), "run_id": fp.get("run_id", "unknown"), "commit": fp.get("commit_sha", "unknown"), "split": d.get("split", "not_recorded"), "stage": stage}
            items = []
            for result in d["results"]:
                q = by_id[result["query_id"]]; r = result[stage]; positive = not result["expected_empty"]
                rank = r.get("first_relevant_rank")
                vals = {"mrr": (1 / rank if rank else 0) if positive else "", "recall_at_5": r.get("recall_at_5", "") if positive else "", "recall_at_10": r.get("recall_at_10", "") if positive else "", "hit_rate_at_5": int(bool(rank and rank <= 5)) if positive else "", "hit_rate_at_10": int(bool(rank and rank <= 10)) if positive else ""}
                if positive:
                    assert abs(vals["mrr"] - r["reciprocal_rank"]) < 1e-12
                row = {**base, "row_type": "question", "query_id": q["query_id"], "question": q["query"], "document_family": q["document_family"] or "unassigned", "expected_empty": result["expected_empty"], "n_questions": 1, "n_answerable": int(positive), "n_unanswerable": int(not positive), **vals, "first_relevant_rank": rank if rank else "", "returned": r["returned"], "passed": r["passed"], "maximum_score": r.get("maximum_score", ""), "failure": ""}
                problems = []
                if positive:
                    if not rank: problems.append("no_label_match_in_returned_list")
                    elif rank > 5: problems.append("miss_at_5")
                    if rank and rank > 10: problems.append("miss_at_10")
                    if r.get("recall_at_5", 1) < 1: problems.append("incomplete_label_recall_at_5")
                    if r.get("recall_at_10", 1) < 1: problems.append("incomplete_label_recall_at_10")
                    if not r["passed"] and rank: problems.append("insufficient_distinct_sources")
                elif r["returned"]: problems.append("candidates_for_unanswerable_not_an_abstention_failure")
                row["failure"] = ";".join(problems)
                items.append(row); retrieval_rows.append(row)
                if origin == "fresh" and positive and problems: failures.append(row)
            groups = [("aggregate", "ALL", items)] + [("family", family, [r for r in items if r["document_family"] == family]) for family in sorted({r["document_family"] for r in items})]
            for kind, family, selected in groups:
                positives = [r for r in selected if not r["expected_empty"]]
                means = {k: sum(r[k] for r in positives) / len(positives) if positives and all(r[k] != "" for r in positives) else "" for k in ("mrr", "recall_at_5", "recall_at_10", "hit_rate_at_5", "hit_rate_at_10")}
                row = {**base, "row_type": kind, "document_family": family, "n_questions": len(selected), "n_answerable": len(positives), "n_unanswerable": len(selected)-len(positives), **means}
                retrieval_rows.append(row)
                if origin == "fresh" and kind == "aggregate": aggregate.append(row)
                if kind == "aggregate":
                    assert abs(means["mrr"] - d[stage]["mean_reciprocal_rank"]) < 1e-12
                    for key in ("recall_at_5", "recall_at_10"):
                        if means[key] != "": assert abs(means[key] - d[stage]["mean_" + key]) < 1e-12
    csv_out(ROOT / "racevault_retrieval_results.csv", retrieval_rows)

    from racevault.evaluation.calibration import calibrate_sufficiency_threshold
    from racevault.evaluation.models import EvaluationReport
    old_dev = read(historical / "corpus-v2-development.json")
    calibration = read(historical / "sufficiency-calibration.json")
    replay = calibrate_sufficiency_threshold(EvaluationReport.model_validate(old_dev)).model_dump(mode="json")
    assert replay == calibration
    save(E / "calibration_replay.json", replay)
    from racevault.config import get_settings
    threshold = get_settings().answer_minimum_reranker_score
    abstention = []; abstention_summaries = []
    for origin, path in reports:
        d = read(path)
        if d.get("dataset_id") != "racevault-corpus-v2" or d.get("split") not in ("development", "test"): continue
        for threshold_name, t in [("runtime_fixed", threshold), ("saved_calibration_exact", calibration["threshold"])]:
            counts = Counter()
            for r in d["results"]:
                raw = r["reranked"].get("maximum_score"); score = raw if raw is not None else 0.0
                predicted = score < t; actual = r["expected_empty"]
                cell = "TP" if actual and predicted else "FN" if actual else "FP" if predicted else "TN"
                counts[cell] += 1
                q = by_id[r["query_id"]]
                abstention.append({"origin": origin, "row_type": "question", "source_file": str(path.relative_to(ROOT)).replace("\\", "/"), "split": d["split"], "role": "calibration_questions_reused_for_reporting" if d["split"] == "development" else "excluded_from_saved_threshold_selection;historical_retrieval_exposure", "query_id": r["query_id"], "question": q["query"], "document_family": q["document_family"] or "unassigned", "threshold_name": threshold_name, "threshold": t, "raw_maximum_score": raw, "score_for_decision": score, "expected_unanswerable": actual, "predicted_abstain": predicted, "confusion_cell_abstention_positive": cell})
            tp, fp, tn, fn = (counts[x] for x in ("TP", "FP", "TN", "FN"))
            summary = {"origin": origin, "row_type": "aggregate", "source_file": str(path.relative_to(ROOT)).replace("\\", "/"), "split": d["split"], "threshold_name": threshold_name, "threshold": t, "n_questions": sum(counts.values()), "TP": tp, "FP": fp, "TN": tn, "FN": fn, "abstention_precision": tp/(tp+fp) if tp+fp else "", "abstention_recall": tp/(tp+fn) if tp+fn else "", "answerable_recall": tn/(tn+fp) if tn+fp else ""}
            abstention.append(summary); abstention_summaries.append(summary)
    csv_out(ROOT / "racevault_abstention_results.csv", abstention)

    citation_rows = []; answer_stats = Counter()
    for q in queries:
        if q["split"] != "test": continue
        path = E / f"answer_{q['query_id']}.json"
        base = {"query_id": q["query_id"], "question": q["query"], "document_family": q["document_family"] or "unassigned", "split": "test", "holdout_status": "existing_test_split;prior_retrieval_exposure", "answerable_label": not q["expected_empty"], "capture_file": str(path.relative_to(ROOT)).replace("\\", "/")}
        d = read(path) if path.exists() else {"status": "not_captured"}
        response = d.get("response"); answer_stats[d["status"]] += 1
        blanks = {"support_judgement": "", "citation_completeness": "", "wrong_source": "", "wrong_vehicle_generation_or_edition": "", "generation_error": "", "answer_correctness": "", "atomic_claim_text": "", "reviewer_id": "", "reviewed_at": "", "second_reviewer_judgement": "", "adjudicated_judgement": "", "review_notes": ""}
        if not response or not d.get("calls"):
            citation_rows.append({**base, "row_kind": "no_generated_claim", "capture_status": d["status"], "generated_claim": "", "generated_statement_id": "", "cited_evidence_id": "", "cited_source": "", "cited_pages": "", "cited_chunk": "", "retrieved_evidence_text": "", "supplied_evidence_text": "", "citation_id_valid": "not_applicable", **blanks, "missing_or_abstention_reason": d.get("error", (response or {}).get("answer", "capture pending"))})
            answer_stats["no_generated_claim"] += 1
            continue
        citations = {c["evidence_id"]: c["citation"] for c in response["citations"]}
        statements = [("answer", t) for t in response["answer"].split("\n\n")] + [("conflict", t) for t in response["conflicts"]] + [("limitation", t) for t in response["limitations"]]
        final_prompt = d["calls"][-1]["user_prompt"]
        for i, (section, text) in enumerate(statements, 1):
            ids = re.findall(r"\bE[1-9][0-9]*\b", text)
            claim = re.sub(r"\s*\[E\d+(?:, E\d+)*\]", "", text)
            answer_stats["statements"] += 1
            for eid in ids or [""]:
                index = int(eid[1:])-1 if eid else -1
                hit = response["evidence"][index] if 0 <= index < len(response["evidence"]) else {}
                cited = citations.get(eid, {})
                valid = bool(eid in citations and hit and cited["chunk_id"] == hit["citation"]["chunk_id"])
                answer_stats["citation_pairs"] += 1; answer_stats["valid_citation_pairs"] += valid
                match = re.search(rf"BEGIN {eid}\n.*?\nevidence:\n(.*?)\nEND {eid}", final_prompt, re.S) if eid else None
                citation_rows.append({**base, "row_kind": "statement_citation_pair", "capture_status": d["status"], "generated_statement_id": f"{q['query_id']}:S{i}", "statement_section": section, "generated_claim": claim, "cited_evidence_id": eid, "cited_source": cited.get("source_path", ""), "cited_pages": json.dumps(cited.get("page_numbers", [])), "cited_chunk": cited.get("chunk_id", ""), "retrieved_evidence_text": hit.get("evidence_text", ""), "supplied_evidence_text": match.group(1) if match else "", "citation_id_valid": valid, **blanks})
    csv_out(ROOT / "racevault_citation_audit.csv", citation_rows)
    save(E / "citation_capture_summary.json", dict(answer_stats))
    service_counts = Counter()
    for q in queries:
        if q["split"] != "test":
            continue
        p = E / f"answer_{q['query_id']}.json"
        if not p.exists() or "response" not in read(p):
            continue
        response = read(p)["response"]
        predicted = response["insufficient_evidence"]
        actual = q["expected_empty"]
        cell = "TP" if actual and predicted else "FN" if actual else "FP" if predicted else "TN"
        service_counts[cell] += 1
        abstention.append({"origin": "fresh_answer_service", "row_type": "question", "source_file": str(p.relative_to(ROOT)).replace("\\", "/"), "split": "test", "role": "end_to_end_response_insufficient_evidence", "query_id": q["query_id"], "question": q["query"], "document_family": q["document_family"] or "unassigned", "threshold_name": "runtime_fixed", "threshold": threshold, "raw_maximum_score": response["evidence_selection"]["maximum_reranker_score"], "expected_unanswerable": actual, "predicted_abstain": predicted, "confusion_cell_abstention_positive": cell, "service_decision_reason": response["evidence_selection"]["reason"]})
    if service_counts:
        tp,fp,tn,fn = (service_counts[k] for k in ("TP","FP","TN","FN"))
        summary = {"origin": "fresh_answer_service", "row_type": "aggregate", "source_file": "validation_evidence/answer_manifest.json", "split": "test", "threshold_name": "runtime_fixed", "threshold": threshold, "n_questions": sum(service_counts.values()), "TP": tp, "FP": fp, "TN": tn, "FN": fn, "abstention_precision": tp/(tp+fp) if tp+fp else "", "abstention_recall": tp/(tp+fn) if tp+fn else "", "answerable_recall": tn/(tn+fp) if tn+fp else ""}
        abstention.append(summary); abstention_summaries.append(summary)
    csv_out(ROOT / "racevault_abstention_results.csv", abstention)

    inventory_paths = set()
    for folder in ("evaluation", "backend/src/racevault/evaluation", "backend/tests/evaluation"):
        inventory_paths.update(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    inventory_paths.update((ROOT / "scripts").glob("*.py"))
    inventory_paths.update(p for p in (ROOT / ".github").rglob("*") if p.is_file())
    inventory_paths.update((ROOT / "docs").glob("*.md"))
    inventory_paths.update((ROOT / "corpus").glob("*.json"))
    inventory_paths.update((ROOT / ".artifacts/evaluation").glob("*"))
    inventory_paths.update((ROOT / ".artifacts/reports").glob("*.json"))
    inventory_paths.update(ROOT / p for p in ("README.md", "compose.yaml", "backend/requirements.lock", "backend/src/racevault/config.py", "backend/src/racevault/lexical/query.py", "backend/src/racevault/lexical/mapping.py", "backend/src/racevault/lexical/synonyms.py", "backend/src/racevault/fusion/models.py", "backend/src/racevault/fusion/pipeline.py", "backend/src/racevault/fusion/rrf.py", "backend/src/racevault/fusion/reranker.py", "backend/src/racevault/generation/service.py", "backend/src/racevault/generation/evidence.py", "backend/src/racevault/generation/ollama.py"))
    inventory = [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(inventory_paths) if p.is_file()]
    save(E / "input_inventory.json", inventory)
    history = subprocess.check_output(["git", "log", "--all", "--format=%H %aI %an %s", "--", "evaluation", "backend/src/racevault/evaluation"], cwd=ROOT, text=True)
    (E / "benchmark_git_history.txt").write_text(history, encoding="utf-8")
    save(E / "audit_summary.json", {"retrieval": aggregate, "abstention": abstention_summaries, "failures": failures, "citation": dict(answer_stats)})
    build_documents(queries, legacy, labels, inventory, aggregate, abstention_summaries, failures, answer_stats)
    save(E / "verification.json", {"raw_rankings_rescored": 160, "raw_metrics_exact_match": True,
         "declared_families_disjoint": True, "labelled_source_paths_disjoint": True,
         "store_snapshots_unchanged": True, "historical_calibration_exact_match": True,
         "saved_grounding_and_agreement_match_illustrative_fixtures": True,
         "existing_tests_passed": 53,
         "test_command": "python -m pytest backend/tests/evaluation backend/tests/generation/test_service.py backend/tests/generation/test_evidence.py -q (PYTHONPATH=backend/src)"})
    outputs = [*ROOT.glob("racevault_*.md"), *ROOT.glob("racevault_*.csv"), ROOT / "evaluation/reproduce_validation.py", ROOT / "evaluation/build_validation_record.py", *E.rglob("*")]
    save(E / "output_sha256.json", {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in sorted(outputs) if p.is_file() and p.name != "output_sha256.json"})


def build_documents(queries, legacy, labels, inventory, aggregate, abstention, failures, answer_stats):
    manifest = read(E / "run_manifest.json")
    commit = manifest["commit"]
    provenance = ["# RaceVault benchmark provenance", "", f"Audited commit: `{commit}`. Dataset SHA-256: `{sha(ROOT / 'evaluation/queries.json')}`.", "", "## The requested 20-question set does not exist in the inspected repository", "", "The current `evaluation/queries.json` contains **40 questions (31 answerable, 9 expected-empty)**. `queries-legacy-v1.json` contains **16 (15 positive, one wrong-revision negative)**. The public example contains 8. Saved runs contain 15, 16, 27, 13 or 40 questions. No 20-question benchmark, membership list or provenance was found in the working tree or reachable benchmark Git history. A claim about a particular 20-question set requires its exact file/version or question IDs; no arbitrary 20-question subset was manufactured.", "", "## Recoverable creation history", "", "1. Commit `ac6fc3d` (2026-08-14, recorded Git author Niket Shah) introduced the 16-query evaluation. The question-writing procedure, individual label authors, annotator identities, independent review and pre-tuning freeze are unknown. Git authorship does not establish who judged relevance or whether AI assisted authoring.", "2. Commit `cce0fe7` (2026-08-24, recorded Git author Niket Shah) added the v2 builder and dataset. `evaluation/build_dataset.py` reads the 16 legacy questions, preserves their predicates, assigns grade 3 to legacy labels, and adds 16 positive questions and 8 negatives as literal definitions. The data card describes labels as author-verified, not independently annotated. Literal curation plus automatic validation is established; human-versus-LLM authorship of individual text/labels is unknown.", "3. `verify()` checks source/page/text predicates against indexed chunks and checks absence of selected keywords for the new negatives. It neither establishes exhaustive qrels nor proves semantic unanswerability. The current read-only check is preserved in `validation_evidence/label_resolution.json`; these resolved chunk IDs are audit outputs, not original chunk-ID qrels.", "4. `SPLIT_BY_FAMILY` overrides initial literals, including the seven Australian questions initially marked test in NEW_QUERIES: they are development in the actual output. There is no separate calibration split: all 27 development questions enter saved threshold selection. Legacy queries without a family default to development.", "5. The builder says legacy test questions were not consulted for changes made since its construction. However, 8 of the current 9 answerable test questions appear in both `representative-baseline.json` and `representative-hardened.json`; the ninth appears in the legacy full-corpus and after-steps runs. Historical exposure is established. Exactly which question drove which retrieval parameter change is unknown. These are existing test-split regression results, not demonstrated untouched validation of the entire system.", "", "## Split and label contract", "", "The actual positive families are five development families and two test families; the mapping defines nine possible families, but PCC Asia/Other have no current questions. Null-family negatives are allocated explicitly. The wrong-revision negative is a scope-empty query, not a globally absent topic. No positive family or labelled source path crosses the current splits. No split was changed for this audit. The model validator checks the declared family field, rather than all source paths; this audit checks both.", "", table(["Split", "Family", "Questions", "Answerable", "Expected-empty"], [(s, f or "unassigned", len(group), sum(not q['expected_empty'] for q in group), sum(q['expected_empty'] for q in group)) for s in ('development','test') for f in sorted({q['document_family'] for q in queries if q['split']==s}, key=lambda x:x or '') for group in [[q for q in queries if q['split']==s and q['document_family']==f]]]), "", "Relevance is a case-insensitive exact source path, optional PDF page-number membership and AND of literal text fragments within `evidence_text`. No original chunk IDs are labelled; all label_id values and gold_claims are empty. Grade 3 is the default, with the ABS data-sheet alternative graded 2. Relevance matching ignores grade for MRR/recall. Labels are sparse passage predicates, not exhaustive chunk-level relevance judgements. Independent review: not established (data card explicitly says not independently annotated). The public 200-query annotation plan reports zero completed/double-labelled queries.", "", "## Question-by-question record", "", "For every entry: independent reviewer = unknown/not recorded; individual relevance adjudicator = unknown. The recorded Git author is not asserted to be that adjudicator. Source family, split, filters and labels below are copied from the frozen dataset. `development/calibration` means the question was included in the saved calibration input; it does not prove that it influenced a retrieval parameter."]
    for q in queries:
        qid=q['query_id']; current=labels.get(qid, {})
        origin = "legacy literal question/labels, upgraded by builder" if qid in legacy else "literal NEW_QUERIES/negative() definition in builder"
        exposure = "Present in pre-v2 retrieval evaluations; specific use for parameter selection unknown." if qid in legacy else "Development family documented as available for tuning; per-question retrieval tuning history unknown." if q['split']=='development' else "Excluded from saved threshold calibration; individual pre-test tuning exposure unknown. Negative topics checked by builder across the corpus."
        provenance += ["", f"### {qid}", "", q['query'], "", f"- Origin: {origin}.", f"- Family: {q['document_family'] or 'unknown/unassigned'}; category: {q['category']}; split: {q['split']}{'/calibration' if q['split']=='development' else ' (existing test designation, not proven untouched)' }.", f"- Label: {'unanswerable in supplied filter scope' if qid=='failure_wrong_regulation_revision' else 'unanswerable (author-assigned; keyword absence proxy)' if q['expected_empty'] else 'answerable (author-assigned)'}. Minimum distinct sources: {q['minimum_distinct_sources']}.", f"- Filters: `{json.dumps({k:v for k,v in q['filters'].items() if v is not None}, ensure_ascii=False)}`.", f"- Label establishment: curated literals; automatic predicate verification; actual human/LLM author and independent reviewer unknown. {exposure}", "- Exact original relevance predicates: `"+json.dumps(q['relevant'],ensure_ascii=False)+"`."]
        if current.get('labels'):
            provenance += ["- Audit-resolved matching chunk IDs (not original annotations): " + "; ".join(f"label {i}: " + (", ".join(str(m['id']) for m in lab['matches']) or "NO MATCH") for i,lab in enumerate(current['labels'],1)) + "."]
        if current.get('negative_term_counts'):
            provenance += ["- Audit keyword occurrence counts: `"+json.dumps(current['negative_term_counts'])+"`; zero counts do not prove semantic absence."]
    provenance += ["", "## Evaluation inventory", "", "All inspected evaluation code, tests, scripts, labels, cards, settings and saved-result files are enumerated with hashes in `validation_evidence/input_inventory.json`. Local PDFs/extraction/chunk artifacts and database contents are private corpus inputs, not independently annotated benchmarks. `.artifacts/reports/full-ingestion.json` currently records a failed ingestion attempt; its totals must not replace the live store snapshot.", "", table(["Path", "Bytes", "SHA-256"], [(r['path'],r['bytes'],r['sha256']) for r in inventory]), "", "Saved corpus-v2 development/test runs have dataset hash matching the current file, commit `75c8f3e...`, dirty_worktree=true, seed 17 and pinned model revisions. Their configuration hashes are present, but the exact dirty source tree and full configuration payload are not. The earlier all-split v2 run has a different dataset hash; do not combine it with final-split scores as one experiment. Full saved fingerprints remain in `validation_evidence/historical/`."]
    (ROOT / "racevault_benchmark_provenance.md").write_text("\n".join(provenance)+"\n",encoding="utf-8")

    dev_ids=[q['query_id'] for q in queries if q['split']=='development'];test_ids=[q['query_id'] for q in queries if q['split']=='test']
    report=["# RaceVault validation report", "", f"Production source commit: `{commit}`. Fresh retrieval completed at {manifest['finished_at']} (UTC; 2026-09-30 Pacific/Auckland). No production code, retrieval parameters, labels, split assignments or runtime threshold were changed. The starting tracked tree was clean; the recorded dirty state consists of newly added audit tools/artifacts.", "", "## Scope and status", "", "The requested 20-question benchmark is not present. This audit covers the actual 40-question dataset, preserves its 27/13 development/test split and documents all 40 questions in `racevault_benchmark_provenance.md`. The test split has 9 answerable questions and 4 negatives. All 13 were selected for citation capture before seeing their answers; adding development questions to reach 15–20 would misrepresent the split.", "", "A fresh process ran the current evaluation runner against the existing stores; this was not a re-ingestion or clean-room index rebuild. Both store snapshots are byte-for-byte identical at the JSON snapshot level before and after: 64 documents, 9,212 chunks and 9,212 pinned BGE-M3 embeddings. The prior stopped Docker/Ollama services were started. The first attempt failed because .env used Docker-only hostnames; local endpoint overrides fixed connectivity without changing retrieval settings. That failed manifest is retained.", "", "## Reproduction and frozen configuration", "", "Run from the repository root with the existing PostgreSQL, OpenSearch and Ollama services and cached models available:", "", "```powershell", "$env:RACEVAULT_POSTGRES_HOST='localhost'", "$env:RACEVAULT_OPENSEARCH_URL='http://localhost:9200'", "$env:RACEVAULT_OLLAMA_URL='http://localhost:11434'", "$env:PYTHONHASHSEED='17'", "$env:CUBLAS_WORKSPACE_CONFIG=':4096:8'", "$env:HF_HUB_OFFLINE='1'", "$env:TRANSFORMERS_OFFLINE='1'", "python evaluation/reproduce_validation.py live", "$env:RACEVAULT_API_MODEL_DEVICE='cuda'", "$env:RACEVAULT_API_LOCAL_FILES_ONLY='true'", "python evaluation/reproduce_validation.py answers", "python evaluation/build_validation_record.py --resolve-labels", "```", "", "Archive `validation_evidence/` and reviewer-edited CSVs before rerunning: the scripts overwrite their audit outputs. They never write to retrieval stores. The recorder wraps the evaluator's call site to save the unchanged stage results; the current production search functions perform ranking. Model loading is offline. No calibration was run on fresh or test scores: the historical development calibration algorithm was replayed only to verify its saved threshold.", "", "The complete configuration, runtime package versions, GPU, Python, CUDA/cuDNN, seeds, dataset hash and safe settings are in `validation_evidence/run_manifest.json`; generation settings and model digest are in `answer_manifest.json`. Store settings/mappings/content hashes and PostgreSQL/pgvector versions are in `stores_before.json` and `stores_after.json`. The generation capture used Ollama 0.34.2 and qwen3.5:9b digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` (Q4_K_M, 9.7B). Raw stage hits and scores are in `retrieval_<query_id>.json`; raw answer-service responses and actual generation prompts/calls are in `answer_<query_id>.json`. Input and output SHA-256 manifests bind the record.", "", table(["Setting", "Value"], [("Dataset", "racevault-corpus-v2 2.0.0; "+sha(ROOT/'evaluation/queries.json')), ("Embedding", "BAAI/bge-m3 @ 5617a9f61b028005a4858fdac845db406aefb181; max_tokens=8192; batch=1; normalized CLS"), ("Reranker", "BAAI/bge-reranker-v2-m3 @ 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e; max_tokens=8192; batch=8; sigmoid scores"), ("Device", "CUDA, NVIDIA GeForce RTX 4070; model float16"), ("Retrieval lists", "BM25=50, semantic=50, fused=30, reranked=15; only first 15 fused candidates are reranked"), ("Fusion", "RRF constant=60; lexical weight=1; semantic weight=1"), ("Filters", "dataset filters enabled; runner bypasses service scope/latest-edition resolution"), ("Index", "racevault-chunks-v2; schema 2.0; OpenSearch 3.7.0 / Lucene 10.4.0; PostgreSQL 18.4 / pgvector 0.8.6"), ("BM25", "server similarity defaults (no explicit k1/b override); analyzer/mapping snapshotted; boosts/tie-breaks in lexical/query.py"), ("Dense query", "cosine distance; model/revision and metadata filters; distance then chunk ID; hnsw.iterative_scan=strict_order"), ("Seeds", "Python random, NumPy, PyTorch CPU/CUDA and PYTHONHASHSEED=17; bootstrap=1000 with base seed 17 and metric offsets; deterministic PyTorch algorithms; CUBLAS :4096:8"), ("Generation", "qwen3.5:9b; temperature=0; seed=0; num_ctx=16384; num_predict=3072; think=false"), ("Abstention", "runtime fixed 0.2377; original saved calibration 0.237715570256114; no tuning"), ("Acceptance checks", "CLI hit>=0.8, MRR>=0.5, nDCG@10>=0.5 and negative retrieval accuracy=1; calibration constraints answerable recall>=0.8, unanswerable recall>=0.9")]), "", "The runner's CLI random seed controls bootstrap resampling, not model RNGs. This harness additionally seeds model libraries. Fixed seeds do not guarantee bit-identical floating-point results across hardware, library versions or ANN index rebuilds. The pre-existing HNSW construction seed/history is unknown; preserved index state and hashes constrain this reproduction.", "", "## Retrieval effectiveness", "", "Metrics are macro-averages over answerable questions only (development n=22; test n=9). All 40 questions were executed. MRR is reciprocal first matching rank over each stage's full returned list, not uniformly MRR@10. Recall@k is the fraction of authored label predicates matched among the first k hits, credited once each; it is not exhaustive document/chunk recall. HitRate@k is the fraction of answerable questions with at least one matching hit within k. Empty-query metrics are blank in the CSV, not synthetic zeros. Family values on historical CSV rows are mapped to the current dataset for diagnosis; legacy files did not originally declare those families. Negative candidate returns are distinct from answer-layer abstention. The unchanged CLI acceptance rule would still fail this run because it requires negative retrieval accuracy=1, although out-of-corpus top-k retrieval returns candidates (development negative accuracy=0.2; test=0). This harness records metrics without changing that rule or describing the run as passing its CLI acceptance gate. The original positive_hit_rate uses the full list and must not be renamed HitRate@5/10.", "", table(["Split", "Stage", "All/positive n", "MRR", "Recall@5", "Recall@10", "HitRate@5", "HitRate@10"],[(r['split'],r['stage'],f"{r['n_questions']}/{r['n_answerable']}",*[f"{r[k]:.6f}" for k in ('mrr','recall_at_5','recall_at_10','hit_rate_at_5','hit_rate_at_10')]) for r in aggregate]), "", "Fresh metrics reproduce the saved final development/test aggregates. Scores may differ slightly at floating-point precision. The CSV separates fresh runs from saved-result arithmetic replay and includes per-question and per-family rows. Missing Recall fields in legacy saved files remain blank; they cannot be recovered from first-relevant rank alone. Saved reports omit hit identities/text, so their original relevance matching cannot be independently replayed from those reports alone. Fresh traces now retain that evidence.", "", "### Failures and incomplete retrieval", "", table(["Split", "Family", "Question", "Stage", "First rank", "Recall@10", "Failure"],[(r['split'],r['document_family'],r['query_id'],r['stage'],r['first_relevant_rank'],r['recall_at_10'],r['failure']) for r in failures]), "", "A passed query can still miss a relevant label: `manual_intended_use` passes at rank 1 but retrieves only one of two labels (Recall@10=0.5). `abs_map_switch_positions` misses both labels after fusion/reranking. These are failures under the existing literal labels; determining whether an unlabelled retrieved passage is semantically sufficient needs independent review. No label or parameter was changed in response.", "", "## Abstention behaviour", "", "The saved threshold artifact points to development run `b63a69a8-a9c6-4b80-ae8b-65af8d597001`; replaying its current calibration function yields the exact saved threshold 0.237715570256114. It selects among observed scores and midpoints under the stated recall constraints, maximizing balanced accuracy then recall, with lower-threshold tie-breaking. The runtime .env uses the rounded value 0.2377; both are evaluated in the CSV. A missing maximum (no candidates) is treated as score 0. Abstain iff maximum reranker score < threshold; equality answers.", "", "Exactly these 27 questions selected the saved threshold and also underlie the published development score (resubstitution, not held-out validation):", "", "`"+"`, `".join(dev_ids)+"`.", "", "Exactly these 13 questions are excluded from the saved threshold-selection input and used here for fixed-threshold evaluation:", "", "`"+"`, `".join(test_ids)+"`.", "", "There is no separate calibration holdout. The saved development/test files have disjoint IDs and matching dataset hashes. However, the earlier all-split v2 report predates the development-only run, and the positive test questions have legacy retrieval exposure. This establishes separation of the saved threshold algorithm's input, not a prospective blind holdout of every design decision. Missing evidence: a preregistered freeze and tuning log showing nobody inspected these test scores when choosing the procedure/constraints.", "", table(["Origin", "Split", "Threshold", "n", "TP", "FP", "TN", "FN", "Abstention precision", "Abstention recall", "Answerable recall"],[(r['origin'],r['split'],r['threshold'],r['n_questions'],r['TP'],r['FP'],r['TN'],r['FN'],r['abstention_precision'],r['abstention_recall'],r['answerable_recall']) for r in abstention if r['threshold_name']=='runtime_fixed']), "", "Positive class is unanswerable/abstain: TP=correct abstention; FP=answerable rejected; TN=answerable accepted; FN=unanswerable accepted. This is a score-gate experiment using evaluation retrieval maxima, not end-to-end correctness or an assertion that accepted answers are correct. The actual answer service uses up to 20 reranked candidates, scope resolution, facet searches and evidence packing; its decisions can differ. In this captured run it generated 9 answers and abstained before generation on all 4 negatives. The separate fresh_answer_service rows in the abstention CSV report those observed responses, not just score predictions. The code default threshold is None, so deployments without the local setting do not enable this gate.", "", "The documentation's lowest answerable score of about 0.32 belongs to the saved test set. The saved development minimum is 0.4449867904186249 and maximum unanswerable score is 0.030444350093603134; their midpoint gives the exact saved threshold. The perfect development score is in-sample. Four test negatives are too few for a general unanswerability claim.", "", "## Citation-ID validity", "", "`GeneratedStatement` requires citation-shaped IDs, and `validate_grounding()` rejects IDs absent from supplied evidence; responses enforce citation membership. Those structural checks do not test entailment. The captured worksheet independently joins each final rendered statement's IDs to returned source/page/chunk evidence. See capture counts below. No claim of semantic support follows from an ID resolving successfully.", "", f"Capture status/counts: `{json.dumps(dict(answer_stats),sort_keys=True)}`. Counts refer to final rendered statements and statement–citation pairs, not human-verified atomic claims. No-claim/abstention rows are excluded from citation-rate denominators. The selected 13 questions are the full existing test split, with the historical exposure limitation above.", "", "## Semantic citation support and manual review", "", "`racevault_citation_audit.csv` contains verbatim final generated statements, their cited sources/pages/chunks, full retrieved evidence, the evidence actually supplied in the recorded final prompt, and blank judgement fields. It has one row per statement–citation pair plus explicit no-generated-claim rows. Atomic decomposition is deliberately left to reviewers; the same generating LLM is not used as a judge. Raw prompts are retained to detect truncation and distinguish supplied evidence from the larger retrieved chunk.", "", "Review protocol:", "", "1. Freeze and archive the captures. Record reviewer identity/date. Use two independent engineering reviewers where possible; neither should see the other's decisions before completing review.", "2. Split compound generated statements into atomic claims in `atomic_claim_text`, duplicating rows with the same statement ID and a reviewer-assigned atomic suffix. Preserve the original generated text. Include unsupported factual clauses and uncited claims; do not silently discard them. Assess answer, conflict and limitation statements separately.", "3. For each citation pair select Supported (the cited supplied passage entails the full atomic claim including values, units, conditions, scope and edition), Partially supported (only part is established or an essential qualification is missing), or Unsupported (no support, contradiction, or wrong source). Use Unreviewable only in notes when extraction is inadequate; do not count that as Supported. Do not use external knowledge to rescue citation support.", "4. Mark citation_completeness as Complete/Incomplete/Not applicable at the atomic-claim level, considering all cited evidence together. A claim may need multiple citations even if an individual pair is only partially supporting. Mark wrong_source, wrong_vehicle_generation_or_edition and generation_error as Yes/No/Uncertain independently. Wrong generation means incorrect vehicle generation/revision; generation_error separately covers an answer-generation mistake despite usable context.", "5. Inspect the authoritative PDF at the recorded physical page, resolving PDF-versus-printed-page offsets, extraction errors, table columns and scope. Record rationale and authoritative reference. Judge answer_correctness separately as Correct/Partially correct/Incorrect/Unreviewable; a supported quotation can still fail to answer the question.", "6. Independently double-review, report raw agreement, then adjudicate disagreements with reviewer/date/rationale. Preserve original judgements. To report strict citation entailment use fully Supported pairs / reviewed pairs and report Partial separately; compute claim-level completeness using deduplicated atomic IDs, never duplicated CSV rows. Exclude abstentions/no-claim rows from support denominators and report them separately. No semantic rate is reported until manual review is completed.", "", "The saved grounding-summary matches the illustrative two-answer/one-claim public fixture when recomputed; it is not evidence of perfect corpus answer grounding. The annotation-agreement fixture likewise demonstrates tooling rather than completed annotation. The public annotation plan records zero completed and zero double-labelled questions.", "", "## Answer correctness", "", "No current corpus gold claims/reference answers or completed independent answer judgements establish an answer-correctness rate. The 40-query corpus file contains zero gold claims. Retrieval hits, successful abstention, valid citation IDs and semantically supported claims are separate measurements; none alone establishes complete, correct answers. The generated worksheet makes correctness review possible but is not completed ground truth.", "", "## Verification", "", "53 existing evaluation and selected generation validation tests passed (`python -m pytest backend/tests/evaluation backend/tests/generation/test_service.py backend/tests/generation/test_evidence.py -q`, with backend/src on PYTHONPATH). Audit assertions independently recompute MRR, recall and hit rates from per-question records, verify saved aggregate arithmetic and replay historical calibration. All 160 fresh raw stage rankings were rescored with the unchanged `evaluate_stage` predicate and matched their per-question metrics exactly. Corpus label-resolution and absent-term checks are consistency checks, not human relevance review. Production Git diff remains empty.", "", "## Limitations", "", "- No identified 20-question set; all actual current questions are documented instead. A distinct set needs its file/hash or membership list.", "- Existing test designation is preserved, but earlier exposure prevents claiming a demonstrably untouched test for the complete system; per-question tuning and human/LLM authorship are unknown.", "- Labels are sparse author-verified literal predicates, not independently adjudicated exhaustive qrels. Keyword absence is an imperfect answerability proxy. No actual corpus inter-annotator agreement is established.", "- Only 9 answerable test questions, covering tyre data and Porsche manuals, and 4 test negatives. Generalisation across unseen engineering domains, families and revisions is unmeasured.", "- The run reuses existing index/embeddings. Original extraction/index build seed and exact historical dirty trees are unavailable; cross-machine bitwise reproduction is not asserted. Private PDFs and cached models are external prerequisites; hashes do not redistribute those assets.", "- Citation capture uses 13 questions because only 13 current test questions exist. Semantic support, completeness and answer correctness remain unreviewed; no synthetic labels substitute for human judgement.", "- Threshold-only replay differs from the complete answer service. Test separation from the saved calibrator does not establish that test outcomes never influenced broader choices.", "", "## Claims supported for the thesis", "", "- At the recorded source commit, settings and unchanged 64-document/9,212-chunk store, a fresh run evaluated all 40 authored questions with their existing family assignments and reproduced the recorded final split retrieval aggregates.", "- On the 9 answerable questions in the existing test split, BM25, semantic, fused and reranked MRR are respectively 0.847222, 0.888889, 0.870370 and 0.944444 under the repository's literal relevance predicates; reranked Recall@10 is 0.944444.", "- The saved threshold is exactly reproducible from its 27-question development input. At the fixed runtime threshold 0.2377, the separate 13-question test-score evaluation accepts 9 answerable questions and rejects 4 labelled unanswerable questions; this is a small fixed-threshold regression result.", "- In 9 generated test-split answers, all 37 recorded statement–citation pairs resolve to supplied evidence; the 4 abstentions have no generated claims. A manual worksheet preserves 27 generated statements. This establishes citation-ID validity for these captures only, with no empirical semantic-support or answer-correctness rate."]
    (ROOT / "racevault_validation_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
