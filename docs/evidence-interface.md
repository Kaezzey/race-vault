# Evidence interface

RaceVault provides a local web interface for grounded questions, hybrid
retrieval, source inspection, and document comparison. The interface runs at
<http://localhost:3000>.

## Work areas

### Ask

The default view uses a conversation layout with one active engineering
question. A request runs the complete grounded-answer pipeline:

```text
Metadata prefilters
  -> BM25 and BGE-M3
  -> RRF
  -> BGE reranker
  -> bounded evidence
  -> Qwen 3.5 9B
  -> citation validation
  -> grounded answer and evidence cards
```

The generated answer appears before the evidence. Inline evidence identifiers
such as `E1` are buttons. Select one to move to the matching evidence card and
update the citation inspector.

Conflicts and limitations are displayed separately when the V2 response
contains them. The answer footer shows the local model, citation count, and
total retrieval and generation time.

Each evidence card shows:

- final rank and normalized reranker score;
- source filename, page, and clause;
- exact evidence text;
- document type, vehicle, championship, season, and revision when available.

Select a card to open the citation inspector. The inspector shows the section,
source and evidence hashes, chunk identifier, page-region count, and rank at
each retrieval stage.

### Filters

The filter panel supports:

- document type;
- vehicle generation;
- championship;
- season;
- revision;
- source authority.

The selected filters are sent with every answer request. The API applies them
inside both retrieval channels before fusion.

### Sources

The source catalogue lists all loaded documents. It shows page count, chunk
count, vector coverage, source metadata, and a shortened source hash.

Use the catalogue search field to filter the loaded list by filename, document
type, vehicle generation, or revision.

Drop a PDF into the upload area or use **Select PDF**. Select a document type
when known so RaceVault applies the correct chunking strategy. The status text
tracks extraction, chunking, indexing, and embedding. Processing one uploaded
source does not rebuild existing sources.

Use **Search only** to apply the source SHA-256 as a retrieval prefilter. Both
BM25 and BGE-M3 then search only that source.

Use **Remove** to delete the source from OpenSearch and delete its PostgreSQL
document, chunks, and embeddings. Other sources and the original PDF files are
not changed.

### Compare

Comparison runs one question against two source hashes independently. The
default selection uses the 992.1 and 992.2 technical manuals when both are
available.

The result uses two evidence columns:

- Source A uses a blue marker.
- Source B uses a red marker.

Each side contains up to five page-cited passages. Results from one document
cannot enter the other column.

## Run with Docker Compose

Start the complete CPU stack:

```powershell
docker compose up --build -d
```

Start the API with NVIDIA GPU access:

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
```

Open:

- Web interface: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>

## Run locally

Keep the API running on port 8000, then start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Run frontend checks:

```powershell
npm run typecheck
npm run lint
npm run build
```

## Configure the API address

The browser uses `http://localhost:8000` by default. Set the public API address
before building when the API uses another host or port:

```dotenv
NEXT_PUBLIC_RACEVAULT_API_URL=http://localhost:8000
```

Next.js includes public environment variables in the browser bundle at build
time. Rebuild the web image after changing this value.

## Responsive behavior

On wide screens, RaceVault uses a persistent navigation rail and citation
inspector. On smaller screens:

- navigation moves to a bottom tab bar;
- evidence and comparison columns stack;
- grounded answers and evidence headings remove their desktop offset;
- the query composer remains available above the navigation;
- source catalogue details are reduced to the essential fields.

The interface supports keyboard focus indicators and reduced-motion browser
preferences.
