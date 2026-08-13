# Lexical retrieval

RaceVault uses OpenSearch BM25 to retrieve exact engineering terms from chunk
artifacts. Lexical retrieval is the first searchable stage in the pipeline.

This stage does not create embeddings or combine rankings.

## Processing flow

```text
chunks.json
  -> OpenSearch document conversion
  -> versioned index mapping
  -> BM25 index
  -> query and metadata filters
  -> citation-ready chunk results
```

## Indexed content

OpenSearch indexes `contextual_text`, section names, and source filenames. The
index stores `evidence_text` without indexing it separately because the same
evidence is already present in `contextual_text`.

Each search result contains:

- exact evidence text;
- source path, filename, role, and SHA-256;
- document metadata;
- page numbers and page range;
- section and clause references;
- element and table identifiers;
- page-numbered bounding-box provenance.

The stored evidence and provenance are suitable for citations. Search
highlights are display aids and are not source evidence.

## Technical-term analysis

The index uses two text analyzers:

- `racevault_technical` handles normal words and punctuation;
- `racevault_codes` retains characters used in technical identifiers, including
  periods, underscores, slashes, and hyphens.

Queries search both forms. This supports terms such as `P4`, `992.2`, `N3R`,
`ABS M5`, regulation clauses, and part numbers.

The BM25 candidate query uses OR matching across analyzed query terms. This
keeps natural-language questions from requiring every word to appear in one
chunk. Exact identifiers and repeated technical terms still receive higher
BM25 scores. RRF and cross-encoder reranking provide later precision.

## Metadata filters

Search supports exact filters for:

- source SHA-256 and representative-corpus role;
- document class and chunk kind;
- authority;
- vehicle generation;
- championship;
- season;
- revision;
- page number;
- oversized chunk status.

Filters are applied inside the OpenSearch query. They do not change BM25 scores.

## Index identity

The default index is `racevault-chunks-v1`. Its mapping contains a RaceVault
schema version. Index validation rejects a different schema version.

Each indexed artifact has an identity derived from:

- extraction SHA-256;
- chunk size setting;
- context setting;
- chunk strategy version.

Reindexing writes the current artifact before removing older indexed artifacts
for the same source SHA-256. A failed write does not first remove the last
complete source index.

## Create or validate the index

Run commands from `backend/`:

```powershell
python -m racevault.lexical.cli ensure-index
```

## Index chunks

```powershell
python -m racevault.lexical.cli index `
  "../.artifacts/chunks/<source>/<extraction>/<settings>/chunks.json"
```

The operation is idempotent. Existing chunk IDs are replaced, and stale chunks
for the same source are removed after the new artifact is written.

## Search

```powershell
python -m racevault.lexical.cli search "ABS M5"
```

Apply metadata filters:

```powershell
python -m racevault.lexical.cli search "Joker Tyre" `
  --document-class regulation `
  --season 2026 `
  --revision "Version 2"
```

Other filter options are available through:

```powershell
python -m racevault.lexical.cli search --help
```

## Count indexed chunks

```powershell
python -m racevault.lexical.cli count
```
