# Document classification and chunking

RaceVault converts extraction artifacts into text units for lexical and semantic
retrieval. Each chunk retains the metadata and source references required for
filtering and citations.

## Processing flow

```text
extraction.json
  -> document classification
  -> strategy selection
  -> evidence element grouping
  -> provenance validation
  -> chunks.json
```

Chunking does not create embeddings or search indexes.

## Classification

Classification uses the first matching source:

1. Declared `document_type` metadata from the extraction artifact.
2. A corpus-relative path rule.
3. The large-document rule for documents with at least 300 pages.
4. The `unknown` fallback.

The output records the method and rule used for the classification.

| Document class | Chunking strategy |
| --- | --- |
| Regulation | Clause |
| Technical manual | Section evidence |
| Component manual | Section evidence |
| Tyre data | Page and table |
| Part catalogue | Page and table |
| Engineering reference | Hierarchical passage |
| Unknown | Generic evidence |

Declared metadata takes precedence over path rules. This prevents a directory
name from overriding reviewed document metadata.

## Chunk boundaries

RaceVault applies these rules:

- Regulation chunks do not cross detected clause or section boundaries.
- Manual chunks do not cross section boundaries.
- Tyre-data and part-catalogue text chunks do not cross page boundaries.
- Reference passages do not cross section boundaries.
- Tables are stored as independent chunks.
- Extraction elements are never split.
- A chunk can exceed the configured size when one source element is too large.
  The chunk is marked `oversize` for later review.

The default maximum is 2,400 characters of contextual text. Structural
boundaries take priority over chunk size.

## Chunk text

Each chunk contains:

- `evidence_text`: text copied from each extraction element without modification;
- `contextual_text`: section and clause context followed by the evidence;
- SHA-256 hashes for both text forms.

RaceVault joins multiple evidence elements with two newline characters. It does
not trim or rewrite the element text.

Later embedding stages should embed `contextual_text`. Citations and source
inspection should display `evidence_text` with its provenance.

## Provenance

Each `chunks.json` artifact contains the source path, source SHA-256, and source
metadata such as vehicle generation, season, revision, and authority.

Each chunk contains:

- document class and strategy;
- section hierarchy;
- clause reference when detected;
- page numbers and page range;
- extraction element IDs;
- table IDs;
- page-numbered bounding boxes;

Every eligible extraction element must appear in exactly one chunk. Validation
rejects missing, extra, or duplicated element references.

## Output path

```text
.artifacts/chunks/
  <source-sha256>/
    <extraction-sha256>/
      <settings-id>/
        chunks.json
```

The path allows outputs from different source revisions, extraction artifacts,
and chunking settings to coexist.

## Classify an extraction

```powershell
python -m racevault.chunking.cli classify `
  ".artifacts/extracted/<source>/<configuration>/extraction.json"
```

## Create chunks

```powershell
python -m racevault.chunking.cli chunk `
  ".artifacts/extracted/<source>/<configuration>/extraction.json"
```

Set a different maximum size:

```powershell
python -m racevault.chunking.cli chunk `
  ".artifacts/extracted/<source>/<configuration>/extraction.json" `
  --max-characters 1800
```

Use `--force` to rebuild an existing output. Otherwise, the command validates
and reuses it.

## Validate chunks

```powershell
python -m racevault.chunking.cli validate `
  ".artifacts/chunks/<source>/<extraction>/<settings>/chunks.json" `
  --extraction ".artifacts/extracted/<source>/<configuration>/extraction.json"
```

Supplying `--extraction` verifies the extraction SHA-256, source SHA-256, and
complete element coverage.
