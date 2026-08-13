# Hybrid retrieval and reranking

RaceVault combines BM25 and dense-vector results before scoring the strongest
candidates with a cross-encoder reranker.

## Pipeline

```text
Query and metadata filters
  -> OpenSearch BM25: top 50
  -> pgvector cosine search: top 50
  -> Reciprocal Rank Fusion: top 30
  -> BGE-Reranker-v2-M3: top 15
  -> final results: top 10
```

The limits are defaults. The command-line interface allows smaller limits for
development and evaluation.

The same metadata filters are passed to both retrieval channels before fusion.
This prevents a result from an excluded season, revision, vehicle generation,
or document class from entering the candidate set.

## Reciprocal Rank Fusion

RaceVault uses weighted Reciprocal Rank Fusion (RRF):

```text
score(chunk) = sum(channel_weight / (rank_constant + channel_rank))
```

The default rank constant is `60`. BM25 and semantic search each have a weight
of `1.0`.

RRF uses rank positions instead of raw BM25 and cosine scores. The two score
scales do not require calibration. A chunk returned by both channels receives
both rank contributions. RaceVault deduplicates candidates by stable chunk ID.

Results with the same RRF score are ordered by chunk ID. This makes fusion
deterministic for identical inputs.

## Reranker contract

RaceVault pins the following cross-encoder:

| Setting | Value |
| --- | --- |
| Model | `BAAI/bge-reranker-v2-m3` |
| Revision | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
| Maximum input length | 8,192 tokens |
| Output | Sigmoid-normalized relevance score from 0 to 1 |

The reranker receives the complete query and each candidate's contextual text.
It scores only the top RRF candidates. It does not generate text or change the
stored evidence.

Final ties are ordered by RRF score and then chunk ID.

## Result fields

Each result includes:

- BM25 rank and raw score, when returned by BM25;
- semantic rank and cosine score, when returned by vector search;
- RRF score and fused rank;
- reranker score and final rank;
- exact evidence text and retrieval context;
- document, revision, page, section, clause, table, and source metadata;
- stable chunk, artifact, source, and content hashes.

The shared evidence contract ensures that lexical and semantic results expose
the same citation fields. Fusion rejects a chunk if the channels disagree on
its contextual-text hash.

## Run hybrid retrieval

Install the semantic dependencies and start PostgreSQL and OpenSearch. Run the
command from `backend/`:

```powershell
python -m pip install ".[semantic]"

python -m racevault.fusion.cli `
  "Joker Tyre" `
  --document-class regulation `
  --season 2026 `
  --revision "Version 2" `
  --device cuda
```

Use the installed script as an alternative:

```powershell
racevault-retrieve "N3R" --document-class tyre_data --device cuda
```

Use `--local-files-only` after both BGE models are cached. The command fails if
a pinned model revision is unavailable in the local cache.

Development limits can reduce latency:

```powershell
python -m racevault.fusion.cli `
  "Joker Tyre" `
  --document-class regulation `
  --season 2026 `
  --revision "Version 2" `
  --channel-limit 20 `
  --fusion-limit 20 `
  --rerank-limit 10 `
  --limit 3 `
  --device cuda `
  --local-files-only
```

## Configuration

The default reranker settings are available as environment variables:

```text
RACEVAULT_RERANKER_MODEL_ID
RACEVAULT_RERANKER_MODEL_REVISION
RACEVAULT_RERANKER_MAX_TOKENS
RACEVAULT_RERANKER_BATCH_SIZE
```

Lower the batch size if GPU memory is insufficient. Use `--device cpu` when
CUDA is unavailable.

## Current scope

Milestone 6 validates fusion and reranking on the representative three-document
corpus. Full-corpus ingestion and labelled retrieval-quality evaluation belong
to Milestone 7.

## Reference

See the [BGE-Reranker-v2-M3 model card](https://huggingface.co/BAAI/bge-reranker-v2-m3)
for the upstream model interface and scoring guidance.
