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

The index uses three text analyzers:

- `racevault_technical` handles normal words and punctuation, and applies the
  light dictionary stemmer `kstem` so that `brakes` matches `brake`;
- `racevault_technical_search` adds motorsport synonym expansion on top, and is
  used only at search time;
- `racevault_codes` retains characters used in technical identifiers, including
  periods, underscores, slashes, and hyphens.

No stop-word filter is applied. Regulations distinguish `shall` from `should`
from `may`, and removing those words would erase the difference between a
requirement and a recommendation.

### Motorsport synonyms

One corpus carries documents written by regulators, a manufacturer, and
component suppliers across several regions, so the same thing is named
differently from document to document. Australian regulations say `tyre` where
North American ones say `tire`; a supplier writes `shock absorber` where a
manual writes `damper`; regulations legislate about the `Automobile` while
people ask about the `car`. `racevault/lexical/synonyms.py` records those
equivalences and the rules for adding to them.

Expansion happens at search time only, so the vocabulary can grow without
reindexing the corpus:

```powershell
curl -XPOST "$env:RACEVAULT_OPENSEARCH_URL/racevault-chunks-v2/_close"
curl -XPUT "$env:RACEVAULT_OPENSEARCH_URL/racevault-chunks-v2/_settings" -d @analysis.json
curl -XPOST "$env:RACEVAULT_OPENSEARCH_URL/racevault-chunks-v2/_open"
```

Units are grouped only where one quantity has several spellings (`nm`,
`newton metre`), never where the values differ (`psi`, `bar`), which would make
numeric answers wrong.

Queries search both forms. This supports terms such as `P4`, `992.2`, `N3R`,
`ABS M5`, regulation clauses, and part numbers.

The BM25 candidate query uses OR matching across analyzed query terms. This
keeps natural-language questions from requiring every word to appear in one
chunk. A question long enough to have optional terms must still match at least
two of them, so a passage cannot qualify by sharing one common word.

Two optional clauses raise precision without narrowing that candidate set: a
phrase match over `contextual_text` and `section_text`, and a cross-field match
requiring every term somewhere in the document. Both only reorder what the
recall clause already admits, which matters because the most valuable passages
in the corpus are short table rows such as `Minimum weight: 1265 kg` that would
fail a stricter term requirement.

Exact identifiers and repeated technical terms still receive higher BM25 scores.
RRF and cross-encoder reranking provide later precision.

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

The default index is `racevault-chunks-v2`. Its mapping contains a RaceVault
schema version, which changes whenever the analysis chain does, because the
stored tokens change with it. Index validation rejects a different schema
version rather than querying an index built by an older chain.

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
