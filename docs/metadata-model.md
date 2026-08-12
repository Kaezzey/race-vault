# Document identity and metadata model

Retrieval must never collapse documents that happen to discuss similar topics.
RaceVault therefore separates immutable source identity from filterable domain
metadata.

## Immutable identity

- `id`: RaceVault UUID
- `sha256`: exact source-content identity
- `source_path`: canonical corpus-relative path
- `filename`: original filename

## Domain metadata

- document type
- title
- vehicle generation
- championship
- season
- revision
- authority
- language

Unknown values remain null or `unknown`; they are not guessed during registry
creation. Later ingestion stages may propose metadata, but inferred values must
record provenance and remain reviewable.

## Authority

Authority expresses how strongly a source should be treated when evidence
conflicts. It is not a relevance boost by default.

1. `official_regulation`
2. `manufacturer_document`
3. `component_supplier_document`
4. `engineering_reference`
5. `team_document`
6. `unknown`

The retrieval response must expose authority and revision rather than silently
resolving contradictory evidence.

