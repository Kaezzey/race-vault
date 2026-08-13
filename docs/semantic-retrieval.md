# Semantic retrieval

RaceVault uses the dense output from BGE-M3 to retrieve conceptually related
engineering evidence. PostgreSQL stores the vectors through pgvector.

This stage does not combine semantic results with BM25 results. Rank fusion is
part of Milestone 6.

## Processing flow

```text
chunks.json
  -> contextual text
  -> BGE-M3 dense encoder
  -> normalized 1,024-dimensional vector
  -> PostgreSQL and pgvector
  -> cosine similarity search
  -> citation-ready chunk results
```

## Model contract

RaceVault pins the following model identity:

| Setting | Value |
| --- | --- |
| Model | `BAAI/bge-m3` |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Dense dimensions | 1,024 |
| Maximum model input | 8,192 tokens |
| Stored vector normalization | L2 |
| Search distance | Cosine |

RaceVault embeds `contextual_text`. Exact `evidence_text` remains unchanged for
display and citations.

The embedding record stores the model ID, model revision, input-text SHA-256,
dimensions, and normalization state. A vector is reused only when its chunk ID,
model identity, and contextual-text hash match.

## Storage

The `chunk_embeddings` table stores model-versioned vectors separately from
chunks. Its primary key contains:

- chunk ID;
- model ID;
- model revision.

This allows a later model revision to coexist with the current vectors during
evaluation or migration.

The table has a cosine HNSW index. Filtered searches enable strict iterative
HNSW scans so pgvector can continue scanning when metadata filters remove early
candidates.

## Metadata filters

Semantic search supports the same exact filters as lexical search:

- source SHA-256 and representative-corpus role;
- document class and chunk kind;
- authority;
- vehicle generation;
- championship;
- season;
- revision;
- page number;
- oversized chunk status.

Filters limit eligible evidence. They do not modify cosine similarity scores.

## Install local model dependencies

The Docker API image contains the pgvector storage and search dependencies. Run
BGE-M3 on the host workstation so it can use the NVIDIA GPU.

From `backend/`:

```powershell
python -m pip install ".[semantic]"
```

The first embedding command downloads the pinned model into the local Hugging
Face cache. Later commands can use `--local-files-only`.

## Apply the database migration

```powershell
docker compose exec -T api alembic upgrade head
```

## Generate and store embeddings

```powershell
python -m racevault.semantic.cli embed `
  "../.artifacts/chunks/<source>/<extraction>/<settings>/chunks.json" `
  --device cuda
```

Re-run the same command safely. RaceVault does not regenerate matching vectors.

Use the local model cache without network access:

```powershell
python -m racevault.semantic.cli embed `
  "../.artifacts/chunks/<source>/<extraction>/<settings>/chunks.json" `
  --device cuda `
  --local-files-only
```

## Search

```powershell
python -m racevault.semantic.cli search `
  "How is front-to-rear braking balance adjusted?" `
  --document-class technical_manual `
  --vehicle-generation "992.2" `
  --device cuda `
  --local-files-only
```

Apply revision filters when querying versioned sources:

```powershell
python -m racevault.semantic.cli search `
  "What is a Joker Tyre?" `
  --document-class regulation `
  --season 2026 `
  --revision "Version 2" `
  --device cuda `
  --local-files-only
```

## Count vectors

```powershell
python -m racevault.semantic.cli count
```

## References

- [BAAI/bge-m3 model card](https://huggingface.co/BAAI/bge-m3)
- [pgvector indexing and iterative scans](https://github.com/pgvector/pgvector#iterative-index-scans)
- [pgvector Python integration](https://github.com/pgvector/pgvector-python#sqlalchemy)
