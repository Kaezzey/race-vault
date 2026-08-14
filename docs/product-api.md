# Product API

RaceVault exposes retrieval and corpus operations through a versioned FastAPI
interface. The V1 base path is `/v1`.

Use the interactive OpenAPI documentation at <http://localhost:8000/docs>.
Use the machine-readable schema at <http://localhost:8000/openapi.json>.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health/live` | Check API process liveness. |
| `GET` | `/health/ready` | Check PostgreSQL and OpenSearch readiness. |
| `POST` | `/v1/retrieval/search` | Run filtered BM25 and BGE-M3 retrieval, RRF, and reranking. |
| `POST` | `/v1/sources/compare` | Retrieve evidence independently from two selected sources. |
| `GET` | `/v1/sources` | List and filter source documents. |
| `GET` | `/v1/sources/{source_sha256}` | Read one source record. |
| `GET` | `/v1/sources/{source_sha256}/chunks` | Inspect source chunks by page or kind. |
| `GET` | `/v1/corpus/status` | Check document, chunk, embedding, and index consistency. |
| `GET` | `/v1/ingestion/status` | Read API-trigger state and the latest ingestion checkpoint. |
| `POST` | `/v1/ingestion/runs` | Start one resumable ingestion run. |

## Search for evidence

Send a query, optional metadata filters, and retrieval depth limits:

```http
POST /v1/retrieval/search
Content-Type: application/json

{
  "query": "Joker Tyre",
  "filters": {
    "document_class": "regulation",
    "season": 2026,
    "revision": "Version 2"
  },
  "options": {
    "channel_limit": 50,
    "fusion_limit": 30,
    "rerank_limit": 15,
    "result_limit": 10
  }
}
```

RaceVault applies the filters independently in OpenSearch and PostgreSQL before
fusion. Supported filters are:

- `source_sha256`
- `source_role`
- `document_class`
- `authority`
- `vehicle_generation`
- `championship`
- `season`
- `revision`
- `page_number`
- `chunk_kind`
- `oversize`

Each result includes:

- exact evidence text;
- document and chunk classification;
- source metadata;
- source, page, section, clause, element, table, and evidence hashes;
- extraction provenance;
- lexical, semantic, RRF, and reranker diagnostics;
- pinned embedding and reranker model identities.

The response is retrieval evidence. It is not a generated answer.

## Compare two sources

Document comparison runs the complete retrieval pipeline twice. Each run uses a
different source SHA-256 prefilter.

```http
POST /v1/sources/compare
Content-Type: application/json

{
  "query": "How is brake balance adjusted?",
  "left_source_sha256": "<64-character SHA-256>",
  "right_source_sha256": "<64-character SHA-256>",
  "result_limit": 5
}
```

The sources must exist and must have different hashes. The response contains a
left and right retrieval result. RaceVault does not resolve conflicts between
the sources.

## Inspect sources

Filter the source catalogue with query parameters:

```http
GET /v1/sources?document_class=technical_manual&vehicle_generation=992.2&limit=20
```

Supported source filters are `document_class`, `authority`,
`vehicle_generation`, `championship`, `season`, and `revision`.

Inspect the chunks for one source:

```http
GET /v1/sources/{source_sha256}/chunks?page=17&kind=table&limit=50
```

Chunk responses include exact evidence and extraction provenance. Use `limit`
and `offset` for pagination.

## Check corpus consistency

`GET /v1/corpus/status` returns counts for PostgreSQL documents, chunks,
model-versioned embeddings, embedded documents, and OpenSearch chunks.
`consistent` is `true` only when:

- every PostgreSQL chunk has an embedding for the pinned BGE-M3 revision;
- OpenSearch contains the same number of chunks;
- every registered document has embedded chunks.

## Run ingestion

API-triggered ingestion is disabled by default. Set
`RACEVAULT_API_INGESTION_ENABLED=true` only on a trusted local deployment.

Select explicit manifest roles:

```http
POST /v1/ingestion/runs
Content-Type: application/json

{
  "roles": ["tyre_data", "regulation_current"],
  "through": "semantic"
}
```

Or select the complete manifest:

```json
{
  "all_documents": true,
  "through": "semantic"
}
```

Valid stages are `extract`, `chunk`, `lexical`, and `semantic`. Only one run can
be active. The endpoint returns `202 Accepted` with a run ID. Read progress from
`GET /v1/ingestion/status`.

The status response separates:

- `trigger_enabled`: whether new API runs are allowed;
- `available`: whether an ingestion checkpoint exists;
- `active`: whether a run is active.

## Error format

V1 errors use one response shape:

```json
{
  "error": {
    "code": "source_not_found",
    "message": "The requested source does not exist.",
    "details": null
  }
}
```

Clients should branch on `error.code`. Messages and details are diagnostic text.
Common status codes are:

| Status | Meaning |
| --- | --- |
| `403` | API-triggered ingestion is disabled. |
| `404` | A requested source does not exist. |
| `409` | An ingestion run is already active. |
| `422` | Request validation failed. |
| `503` | PostgreSQL, OpenSearch, or retrieval is unavailable. |

## Run the API

The default Compose configuration runs the API on CPU and mounts the corpus as
read-only. It stores generated artifacts and model downloads outside the image.

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
```

Use the NVIDIA GPU override for model inference and extraction:

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
```

The GPU configuration requires Docker Desktop GPU support and a compatible
NVIDIA driver. The first retrieval request loads the pinned BGE-M3 and reranker
models. Later requests reuse them within the API process. Local inference is
serialized to avoid concurrent GPU model access.

## Configure browser access

Set `RACEVAULT_API_CORS_ORIGINS` to a JSON array of allowed origins:

```dotenv
RACEVAULT_API_CORS_ORIGINS=["http://localhost:3000"]
```

V1 allows `GET` and `POST` requests with the `Content-Type` header. It does not
enable browser credentials.
