# Operations, SLOs, and recovery

## Observability

Start the application with `compose.observability.yaml`. Grafana shows request
rate, stage p95 latency, and generation queue state; Jaeger shows scope resolution,
lexical retrieval, semantic retrieval, fusion, reranking, evidence packing,
generation, validation, and repair spans.

Telemetry is content-free: raw questions and evidence are never exported.

## SLO exercise

Run retrieval for four concurrent clients over 30 minutes:

```powershell
python scripts/load_test.py
```

For grounded answers, select `/v2/answers`, a 20-second p95 gate, and a timeout
appropriate for cold model loading. HTTP 429 is an intentional saturation signal;
all other non-200 responses count as unexpected errors.

## Answer latency

Model loading and connection setup, not inference, dominate a cold answer. On a
12 GB RTX 4070 with the 64-document corpus, the mean steady-state answer went
from 26.0 s to 7.8 s once each of these was removed:

| Cost | Measured | Cause |
| --- | ---: | --- |
| Ollama connection to `localhost` | 2.04 s each | `localhost` resolves to `::1` first and Ollama listens on IPv4 only |
| `status()` before every generation | 3 connections | model identity re-resolved per call, now resolved once |
| Reloading the embedder and reranker | 6.5 s per answer | `answer_release_retrieval_models` |
| Reloading the generation model | 7.2 s per answer | `ollama_keep_alive="0"` |
| Rebuilding the OpenSearch client | 0.21 s per search | one search per facet plus the full-question search |

All three models fit on a 12 GB card at once: 1.1 GB embedder, 1.1 GB reranker,
and 6.0 GB for the generation model at `num_ctx` 16384, leaving about 2 GB free.
The eviction settings exist for smaller GPUs. On a card that cannot hold all
three, set:

```dotenv
RACEVAULT_ANSWER_RELEASE_RETRIEVAL_MODELS=true
RACEVAULT_OLLAMA_KEEP_ALIVE=0
```

and expect roughly 14 s of extra loading per answer.

Point `RACEVAULT_OLLAMA_URL` at `127.0.0.1` rather than `localhost` on any host
whose resolver returns `::1` first. Inside compose the API reaches the host
through `host.docker.internal`, which is unaffected.

With loading removed, generation is the remaining cost and scales with output
length: a single-fact answer emits 170-330 tokens in about 4-7 s at roughly
60 tokens/s, while a compound question emits 865 and takes about 14 s. A failed
citation validation adds a second full generation.

## Recovery drills

1. Back up PostgreSQL with `pg_dump -Fc` and copy the corpus manifest, chunk
   artifacts, extraction artifacts, environment template, and experiment reports.
2. Restore PostgreSQL into a clean named volume and run `alembic upgrade head`.
3. Rebuild OpenSearch from canonical chunk artifacts with
   `racevault-corpus ingest --through lexical`; OpenSearch is not the source of
   truth.
4. Verify parity through `/v1/corpus/status` before serving traffic.
5. Interrupt corpus ingestion after several documents, restart the identical
   command, and confirm compatible extraction/chunk artifacts and embeddings are
   reused.
6. Repeat with a corrupted PDF. The failed document must appear in the checkpoint
   report while completed documents remain available.
7. Stop Ollama, OpenSearch, and PostgreSQL separately and verify stable 503 error
   shapes and recovery after restart.

Restore commands are intentionally not automated into a destructive script. A
human must identify and verify the exact backup and target volume before replacing
state.
