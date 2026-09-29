"""Read-only evaluation harness; never indexes, calibrates, or tunes production.

Run from the repository root with PYTHONHASHSEED=17. Saves new artifacts in
validation_evidence/, leaving the original .artifacts/evaluation/ runs intact.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
OUT = ROOT / "validation_evidence"
SEED = 17


def save(name, value):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(settings):
    import httpx
    import psycopg
    from psycopg.rows import dict_row
    result = {}
    with httpx.Client(base_url=settings.opensearch_url, timeout=30) as client:
        for name, route in [("version", "/"), ("settings", f"/{settings.opensearch_index_name}/_settings"),
                            ("mapping", f"/{settings.opensearch_index_name}/_mapping"),
                            ("count", f"/{settings.opensearch_index_name}/_count")]:
            response = client.get(route); response.raise_for_status(); result[name] = response.json()
        # A stable, sorted digest of the complete stored index documents.
        hashes = []
        response = client.post(f"/{settings.opensearch_index_name}/_search?scroll=1m", json={"size": 500, "sort": ["_doc"], "query": {"match_all": {}}})
        response.raise_for_status(); page = response.json()
        scroll_id = None
        try:
            while page["hits"]["hits"]:
                hashes.extend(hashlib.sha256(json.dumps(h["_source"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() for h in page["hits"]["hits"])
                scroll_id = page["_scroll_id"]
                response = client.post("/_search/scroll", json={"scroll": "1m", "scroll_id": scroll_id})
                response.raise_for_status(); page = response.json()
        finally:
            if scroll_id:
                client.request("DELETE", "/_search/scroll", json={"scroll_id": [scroll_id]})
        result["index_document_count"] = len(hashes)
        result["index_content_sha256"] = hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest()
    with psycopg.connect(settings.psycopg_conninfo + " connect_timeout=5", row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        result["postgres_version"] = conn.execute("SELECT version() AS version").fetchone()
        result["pgvector_version"] = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        result["counts"] = {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] for table in ("documents", "chunks", "chunk_embeddings")}
        result["embedding_models"] = conn.execute("SELECT model_id,model_revision,count(*) AS n FROM chunk_embeddings GROUP BY model_id,model_revision").fetchall()
        for table, order in [("documents", "id"), ("chunks", "id"), ("chunk_embeddings", "chunk_id,model_id,model_revision")]:
            h = hashlib.sha256()
            with conn.cursor(name=f"audit_{table}") as cursor:
                cursor.execute(f"SELECT row_to_json(t)::text AS row FROM {table} t ORDER BY {order}")
                for row in cursor:
                    h.update(row["row"].encode()); h.update(b"\n")
            result[f"{table}_sha256"] = h.hexdigest()
    return result


def live():
    from racevault.config import get_settings
    import numpy as np
    import torch
    from racevault.evaluation import runner
    from racevault.evaluation.experiment import create_experiment_fingerprint
    from racevault.fusion.models import RerankerSpec, RrfSettings
    from racevault.fusion.reranker import BgeReranker
    from racevault.lexical.client import OpenSearchClient
    from racevault.semantic.embedder import BgeM3Embedder
    from racevault.semantic.models import EmbeddingModelSpec
    from racevault.semantic.store import SemanticStore

    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    settings = get_settings()
    configuration = {"channel_limit": 50, "fusion_limit": 30, "rerank_limit": 15,
                     "embedding_batch_size": 1, "reranker_batch_size": settings.reranker_batch_size,
                     "device": "cuda", "metadata_filters": True, "rrf_rank_constant": 60,
                     "lexical_weight": 1.0, "semantic_weight": 1.0, "local_files_only": True,
                     "bootstrap_samples": 1000, "random_seed": SEED, "deterministic_algorithms": True,
                     "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                     "CUBLAS_WORKSPACE_CONFIG": os.environ.get("CUBLAS_WORKSPACE_CONFIG")}
    safe_settings = {k: v for k, v in settings.model_dump().items() if not any(x in k for x in ("password", "postgres", "url"))}
    manifest = {"started_at": datetime.now(timezone.utc).isoformat(), "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
                "configuration": configuration, "settings": safe_settings,
                "dataset_sha256": digest(ROOT / "evaluation/queries.json"),
                "python": sys.version, "platform": platform.platform(), "gpu": torch.cuda.get_device_name(0),
                "torch_cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
                "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"]},
                "status": "running"}
    save("run_manifest.json", manifest)
    try:
        save("stores_before.json", snapshot(settings))
        dataset_path = ROOT / "evaluation/queries.json"
        dataset = runner.load_dataset(dataset_path)
        embedder = BgeM3Embedder(spec=EmbeddingModelSpec(model_id=settings.semantic_model_id, model_revision=settings.semantic_model_revision, max_tokens=settings.semantic_max_tokens), device="cuda", batch_size=1, local_files_only=True)
        reranker = BgeReranker(spec=RerankerSpec(model_id=settings.reranker_model_id, model_revision=settings.reranker_model_revision, max_tokens=settings.reranker_max_tokens), device="cuda", batch_size=settings.reranker_batch_size, local_files_only=True)
        original = runner.hybrid_search_stages
        current_queries = iter(())

        def capture(request, **kwargs):
            query = next(current_queries)
            print(f"retrieving {query.split} {query.query_id}", flush=True)
            stages = original(request, **kwargs)
            save(f"retrieval_{query.query_id}.json", {"query_id": query.query_id, "request": request.model_dump(mode="json"),
                "lexical": [h.model_dump(mode="json") for h in stages.lexical.hits],
                "semantic": [h.model_dump(mode="json") for h in stages.semantic.hits],
                "fused": [h.model_dump(mode="json") for h in stages.fused],
                "reranked": [h.model_dump(mode="json") for h in stages.reranked]})
            return stages

        # Instrument only the evaluator's call site, returning the original result unchanged.
        runner.hybrid_search_stages = capture
        try:
            with OpenSearchClient(base_url=settings.opensearch_url, index_name=settings.opensearch_index_name, timeout_seconds=settings.opensearch_timeout_seconds) as lexical:
                for split in ("development", "test"):
                    current_queries = iter(q for q in dataset.queries if q.split == split)
                    fingerprint = create_experiment_fingerprint(repo_root=ROOT, dataset_path=dataset_path, configuration={**configuration, "split": split}, model_revisions={settings.semantic_model_id: settings.semantic_model_revision, settings.reranker_model_id: settings.reranker_model_revision}, random_seed=SEED)
                    report = runner.run_evaluation(dataset, lexical=lexical, semantic_embedder=embedder, semantic_store=SemanticStore(settings.psycopg_conninfo), reranker=reranker, split=split, random_seed=SEED, bootstrap_samples=1000, experiment=fingerprint, rrf=RrfSettings(), channel_limit=50, fusion_limit=30, rerank_limit=15)
                    save(f"fresh_{split}.json", report.model_dump(mode="json"))
        finally:
            runner.hybrid_search_stages = original
        save("stores_after.json", snapshot(settings))
        manifest["status"] = "completed"
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        save("run_manifest.json", manifest)


def answers():
    """Capture the current answer service and raw prompts; no automatic judgement."""
    import torch
    import numpy as np
    from racevault.config import get_settings
    from racevault.api.services import HybridRetrievalService
    from racevault.catalog.store import CatalogStore
    from racevault.evaluation.runner import load_dataset
    from racevault.generation.models import GroundedAnswerRequest
    from racevault.generation.ollama import OllamaClient
    from racevault.generation.service import GroundedAnswerService

    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    settings = get_settings()
    retrieval = HybridRetrievalService(settings, CatalogStore(settings.psycopg_conninfo))
    client = OllamaClient(base_url=settings.ollama_url, model=settings.ollama_model,
                          timeout_seconds=settings.ollama_timeout_seconds,
                          context_tokens=settings.ollama_context_tokens,
                          max_output_tokens=settings.ollama_max_output_tokens,
                          keep_alive=settings.ollama_keep_alive)
    state = {"started_at": datetime.now(timezone.utc).isoformat(), "status": "running",
             "selection_rule": "all existing test-split questions, dataset order; no development additions",
             "settings": {k: v for k, v in settings.model_dump().items() if not any(x in k for x in ("password", "postgres", "url"))},
             "generation_seed": 0, "temperature": 0, "retrieval_seed": SEED,
             "generation_status": client.status().model_dump(mode="json"), "results": []}
    save("answer_manifest.json", state)
    calls = []

    class CaptureClient:
        def status(self):
            return client.status()

        def generate(self, **kwargs):
            call = {k: v for k, v in kwargs.items() if k != "on_text"}
            calls.append(call)
            result = client.generate(**kwargs)
            call["generated"] = result.answer.model_dump(mode="json")
            call["model"] = result.model.model_dump(mode="json")
            call["usage"] = result.usage.model_dump(mode="json")
            return result

    service = GroundedAnswerService(settings=settings, retrieval=retrieval, ollama=CaptureClient())
    try:
        for query in load_dataset(ROOT / "evaluation/queries.json").queries:
            if query.split != "test":
                continue
            calls = []
            print(f"generating {query.query_id}", flush=True)
            item = {"query_id": query.query_id, "query": query.query, "split": query.split,
                    "expected_empty": query.expected_empty, "calls": calls}
            try:
                response = service.answer(GroundedAnswerRequest(query=query.query, filters=query.filters))
                item["response"] = response.model_dump(mode="json")
                item["status"] = "completed"
            except Exception as error:
                item["status"] = "failed"
                item["error"] = f"{type(error).__name__}: {error}"
            save(f"answer_{query.query_id}.json", item)
            state["results"].append({k: item[k] for k in ("query_id", "status")})
            save("answer_manifest.json", state)
        state["status"] = "completed"
    finally:
        client.close(); retrieval.close()
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        save("answer_manifest.json", state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["live", "answers"])
    args = parser.parse_args()
    live() if args.mode == "live" else answers()
