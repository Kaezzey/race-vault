# RaceVault

RaceVault is a local retrieval system for motorsport engineering documents. It
finds technical evidence across manuals, regulations, tyre data, component
documentation, part catalogues, and engineering references.

RaceVault returns evidence with its document, page, section, revision, and
domain metadata. It does not treat a generated answer or an embedding as a
source of truth.

## Why RaceVault exists

Motorsport engineering knowledge is distributed across documents with different
formats, scopes, and authority levels. Documents can apply to different:

- vehicle generations;
- championships;
- seasons;
- software or hardware revisions;
- regulation versions;
- components.

A semantic search result can be relevant to the query but wrong for the selected
car, season, or regulation. Exact terminology also matters. Queries often contain
part numbers, channel names, model codes, fault codes, or regulation clauses that
semantic retrieval can miss.

RaceVault combines lexical search, semantic search, metadata filters, rank
fusion, and reranking. This reduces incorrect cross-version retrieval and keeps
results linked to the original evidence.

## Goals

RaceVault is designed to:

- search heterogeneous technical PDFs on a local workstation;
- support exact-term and conceptual engineering queries;
- distinguish vehicle generations, seasons, championships, and revisions;
- preserve page and section references during document processing;
- identify the authority of each source;
- expose conflicting evidence instead of hiding it;
- return exact citations for every retrieved result;
- run without a paid AI API.

The V1 target is a corpus of 50 to 80 PDFs on a workstation with an NVIDIA RTX
4070.

## Retrieval principles

### Source documents are authoritative

The evidence chain is:

```text
Original document
  -> document record
  -> page
  -> section, clause, table, or figure
  -> retrieved evidence
```

Embeddings and rerankers help locate evidence. They do not replace the source
document.

### Metadata is part of retrieval

RaceVault stores and filters metadata such as:

- document type;
- vehicle generation;
- championship;
- season;
- revision;
- source authority;
- language;
- page and section location.

Unknown metadata remains unknown until it can be verified. The ingestion process
must not infer a value and store it as a confirmed fact.

### No retrieval method is trusted alone

Lexical search handles exact identifiers and technical terms. Semantic search
handles related concepts and natural-language questions. RaceVault combines both
result sets before reranking them against the full query.

## Retrieval pipeline

```text
Query
  -> metadata filters
  -> BM25 lexical search
  -> BGE-M3 semantic search
  -> Reciprocal Rank Fusion
  -> BGE cross-encoder reranking
  -> cited evidence
```

Document processing uses a strategy based on document type:

| Document type | Processing strategy |
| --- | --- |
| Regulations | Clause-based chunks |
| Technical manuals | Section and evidence-based chunks |
| Large reference books | Chapter, section, and passage hierarchy |
| Tyre books and part catalogues | Text, table, and page-aware chunks |

## Technology stack

| Area | Technology | Purpose |
| --- | --- | --- |
| PDF processing | Docling and PyMuPDF | Extract text, headings, tables, page boundaries, and structure |
| Semantic retrieval | BGE-M3 | Generate local dense and sparse document representations |
| Lexical retrieval | OpenSearch and BM25 | Search exact terms, identifiers, and clauses |
| Vector storage | PostgreSQL and pgvector | Store document metadata, chunks, and embeddings |
| Rank fusion | Reciprocal Rank Fusion | Combine lexical and semantic rankings |
| Reranking | BGE-Reranker-v2-M3 | Score candidate evidence against the full query |
| API | FastAPI | Provide ingestion, retrieval, filtering, citation, and comparison services |
| Web interface | Next.js and TypeScript | Provide search, filters, citations, source inspection, and comparison |
| Deployment | Docker Compose | Run all services on the local workstation |
| Visual retrieval | ColQwen family | Retrieve evidence from page layout, tables, diagrams, and figures |

## System architecture

```text
                       RaceVault
                           |
              +------------+------------+
              |                         |
        Document ingestion          Query service
              |                         |
      Docling + PyMuPDF        Metadata validation
              |                         |
      Structured evidence        +------+------+
              |                  |             |
      +-------+-------+       OpenSearch    pgvector
      |               |          BM25        BGE-M3
  PostgreSQL      OpenSearch       |             |
  metadata         text index      +------+------+
      |                                     |
      +-------------------------------> RRF
                                            |
                                         Reranker
                                            |
                                      Cited evidence
```

The source library is mounted read-only. Generated extraction artifacts,
indexes, embeddings, and metadata records are stored separately.

## Version scope

### V1: hybrid text retrieval

V1 covers documents where the required evidence can be represented as extracted
text and structured tables. It includes:

- document registration and metadata management;
- page-aware PDF extraction;
- document classification and type-specific chunking;
- BM25 lexical retrieval;
- BGE-M3 semantic retrieval;
- metadata filtering;
- rank fusion and reranking;
- source citations and document comparison.

### V2: multimodal retrieval

V2 adds visual page retrieval for evidence that text extraction cannot represent
reliably. Examples include:

- suspension and component diagrams;
- aerodynamic maps;
- tyre graphs;
- setup illustrations;
- complex tables;
- equations;
- relationships defined by page layout.

Visual indexing is applied only to documents and pages where it improves
retrieval quality. Text retrieval remains the primary method for documents such
as sporting regulations.

## Local setup

### Prerequisites

- Docker Desktop with at least 4 GB of memory available to containers
- Python 3.12 to 3.14 for local backend development

On Windows, OpenSearch can require the following Docker VM setting:

```powershell
wsl -d docker-desktop sysctl -w vm.max_map_count=262144
```

### Start the services

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose ps
```

Check service readiness:

```powershell
Invoke-RestMethod http://localhost:8000/health/ready
```

Open the API documentation at <http://localhost:8000/docs>.

### Run backend checks

```powershell
python -m pip install -e ".\backend[dev]"
python -m pytest backend/tests
python -m ruff check backend scripts
python -m mypy --config-file backend/pyproject.toml backend/src
python scripts/validate_corpus.py
```

### Extract a document

Install the optional extraction dependencies and extract a document from the
representative manifest:

```powershell
python -m pip install -e ".\backend[dev,extraction]"
python -m racevault.extraction.cli extract --role tyre_data
```

See [PDF extraction](docs/extraction.md) for artifact fields, extraction options,
and validation commands.

### Stop the services

```powershell
docker compose down
```

This command preserves PostgreSQL and OpenSearch data in Docker volumes.

## Repository layout

```text
backend/        API, database models, migrations, and tests
corpus/         Source manifests
docs/           Design and delivery documentation
scripts/        Repository validation tools
AI & ML Reference File Database/
                Original engineering document library
```

See [Document identity and metadata](docs/metadata-model.md) for the source
identity and authority model.

## Non-goals

RaceVault is not designed to:

- act as a generic PDF chatbot;
- provide uncited technical answers;
- resolve source conflicts without showing the underlying evidence;
- replace the original engineering documents;
- depend on a hosted embedding or language-model API.
