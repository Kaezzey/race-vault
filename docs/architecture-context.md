# RaceVault: architecture and design rationale

*Context brief for a university project report, prepared from the repository on 27 September 2026. Approximately three pages, depending on formatting.*

## Purpose and scope

RaceVault is a document retrieval and question-answering component for a larger sponsored university project. It helps users find and compare evidence in motorsport PDFs, including championship regulations, vehicle manuals, component specifications, tyre data, and parts catalogues. Its contribution is to turn a document collection into searchable, source-linked engineering information. The repository does not establish the sponsor's identity, the wider project's architecture, or formal sponsor requirements; those should be supplied separately.

The core design is retrieval-augmented generation (RAG): retrieve relevant passages first, then give a language model those passages to formulate an answer. This keeps document knowledge outside model weights and allows answers to point back to specific pages and revisions. It also makes updating the corpus possible without retraining the generator. These are architectural benefits inferred from the implementation; the documented decisions more specifically emphasise correct document scope, complementary search methods, provenance, and measurable performance.

## System structure

RaceVault has a modular Python backend, a separate web interface, and dedicated storage and model services. It is best described as a modular application with supporting services: extraction, retrieval, and generation are modules within one backend, rather than independently deployed microservices.

| Component | Responsibility and design benefit |
| --- | --- |
| Next.js, React, and TypeScript frontend | Provides questions and answers, a source catalogue, PDF upload/removal, and side-by-side source comparison. A typed HTTP client separates presentation from backend processing. |
| FastAPI backend | Coordinates ingestion, retrieval, evidence selection, and answer validation. Separate modules and injectable service interfaces allow stages to be tested or replaced independently. |
| PostgreSQL with pgvector | Stores document metadata, chunks, and model-versioned embeddings. Relational links keep vectors associated with their source evidence. |
| OpenSearch | Maintains a lexical search index for exact terminology, clauses, and identifiers. It is a derived index that can be rebuilt from chunk artifacts. |
| Ollama | Serves the local Qwen 3.5 9B answer model. The default Compose setup connects to Ollama on the host machine. |
| Filesystem artifacts | Retain source PDFs and intermediate extraction/chunk records for inspection, reuse, and recovery. |

The two main data flows are:

```text
Ingestion: PDF -> extraction -> structured chunks -> lexical index + vectors
Answering: question -> scope filters -> two retrieval channels -> rank fusion
           -> reranking -> evidence selection -> local generation -> validation
           -> answer with citations and source evidence
```

Docker Compose runs the frontend, API, PostgreSQL, and OpenSearch with persistent storage and health checks. GPU and observability overrides support different local setups. Local inference enables processing without sending document content to an external generation API, although initial model downloads may need network access. This is a local deployment design, not evidence of a production security certification.

## Preparing documents without losing their meaning

Ingestion uses Docling for document structure and PyMuPDF for page-level information. The pipeline creates normalized JSON alongside the original Docling export. It records source hashes, extraction settings, page information, headings, tables, and bounding boxes. Keeping intermediate artifacts makes it possible to investigate whether an incorrect answer originated in extraction, chunking, retrieval, or generation.

Chunking follows document structure rather than applying one fixed window to every PDF. Regulations are grouped around clauses; manuals around sections; tyre data and parts catalogues around pages and tables. Tables form separate chunks. The default size target is 2,400 characters, but structural boundaries take precedence and oversized elements are flagged rather than arbitrarily split. This responds to a practical problem: separating a numerical value from its heading, units, or operating conditions can destroy its meaning.

Each chunk stores both unchanged `evidence_text` and `contextual_text`, which adds section or clause context for retrieval. This lets the search models use context while users inspect the original extracted wording. Page references, source identity, and metadata travel with the chunk throughout the pipeline. Source and configuration hashes identify artifacts, and compatible outputs and embeddings can be reused on repeat ingestion. Checkpoint reports record progress and failures, reducing the cost of restarting long imports.

## Retrieving the right evidence

Document applicability is resolved before ranking. Metadata includes championship, vehicle generation, season, revision, and authority. Both retrieval channels receive the same filters so that an otherwise relevant passage from the wrong championship or season does not consume the candidate budget. When a championship is resolved and no year is specified, the latest-edition policy can select its newest available edition; explicit year requests take precedence. “Latest” means latest in the indexed collection, not an independently verified current regulation.

RaceVault combines two complementary retrieval methods. OpenSearch BM25 finds lexical matches, which matters for part numbers, model codes, and clause references. Its analyzers distinguish prose from identifiers, while search-time synonyms handle alternatives such as “tyre/tire” and “damper/shock absorber.” BGE-M3 encodes contextual text into normalized 1,024-dimensional vectors and uses pgvector cosine search to find conceptual matches even when the wording differs.

Reciprocal rank fusion combines the two rankings without treating their different raw scores as directly comparable. A BGE cross-encoder reranker then reads the question against each shortlisted passage to refine relevance. Applying this more expensive model to a shortlist controls computation. The tradeoff is additional models and two search stores to maintain, in return for coverage of both exact identifiers and paraphrased questions.

## Controlling generation and exposing evidence

The generator does not search databases itself. A deterministic evidence controller selects a bounded context from retrieved candidates. It suppresses near-duplicates, balances relevance with diversity, and preserves coverage across named championships. Compound questions can trigger bounded searches for individual subtopics. These controls address cases where simply taking the highest-ranked passages would fill the context with repeated evidence or leave part of a comparison unanswered.

An optional reranker-score threshold allows the system to abstain before generation when evidence is weak. The repository documents a calibrated value of 0.2377, but the Python settings default is unset: deployments must configure the threshold explicitly. A retrieval score is a relevance signal, not a probability that the answer is correct.

Qwen returns structured statements with evidence identifiers. The backend validates the response schema and checks that cited identifiers refer to evidence actually supplied to the model. It can attempt a bounded correction after invalid output. The interface receives the answer, citations, exact evidence, and diagnostic information. This makes an answer inspectable, but identifier validation cannot prove that a passage supports every generated claim. The original document remains authoritative.

## Practical tradeoffs and evidence for the design

The implementation favours a workstation-scale deployment. By default, one answer job runs at a time and four more can queue; excess requests receive HTTP 429. Ingestion also uses local background coordination rather than a distributed worker system. These choices keep execution manageable on limited hardware, but imply further work for distributed or high-concurrency deployment.

Performance work focused on measured overhead. Current settings retain retrieval models and keep Ollama's model loaded for five minutes, avoiding repeated loading when memory permits. Smaller GPUs can enable eviction at the cost of latency. The repository reports a mean steady-state answer improvement from 26.0 to 7.8 seconds on an RTX 4070 with 12 GB VRAM after model-loading and connection changes. These are recorded measurements, not measurements repeated for this brief.

Evaluation separates document families between development and test to reduce leakage. The documented corpus contains 64 documents, 4,888 pages, and 9,212 passages; the evaluation set contains 40 questions. Reported held-out retrieval results improve from BM25 MRR 0.847 to reranked MRR 0.944. The configured abstention threshold accepted all nine answerable test questions and rejected all four unanswerable ones. This small, author-verified benchmark supports regression checking; it does not establish general accuracy or independently verified answer grounding. The evidence controller's wider grounding benefit still requires evaluation.

Tests cover pipeline stages, API behavior, citation validation, and queue handling. Optional metrics and tracing support diagnosis without exporting raw questions or evidence by default. Remaining limits include extraction errors, OCR being disabled by default, complex tables and figures, incomplete metadata, and missing documents. Answering is single-turn and non-streaming; visual retrieval remains experimental. The architecture makes failures easier to locate and evidence easier to inspect, while leaving engineering decisions with the user.

## Notes for adapting this into the wider report

This brief distinguishes implemented behavior from documented measurements and inferred architectural benefits. Do not invent sponsor requirements, claim that all alternatives were experimentally compared, or describe the reported benchmark as a guarantee. Add the wider project's aims, this component's integration points, and the team's actual decision-making history where known.

Repository evidence: `compose.yaml`; `frontend/lib/api.ts`; `backend/src/racevault/main.py`; `config.py`; `extraction/pipeline.py`; `semantic/store.py`; `fusion/pipeline.py`; `generation/service.py`; and the documentation in `docs/design-decisions.md`, `docs/chunking.md`, `docs/evidence-controller.md`, `docs/operations.md`, and `docs/system-card.md`. Backend paths after `main.py` are relative to `backend/src/racevault/`. Where older prose conflicts with runtime defaults, this brief follows the implementation.
