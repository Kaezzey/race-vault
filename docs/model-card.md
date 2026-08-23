# RaceVault model card

## Components

| Component | Pinned model | Role |
| --- | --- | --- |
| Dense retrieval | `BAAI/bge-m3` at `5617a9f...` | Query and chunk embeddings |
| Cross-encoder | `BAAI/bge-reranker-v2-m3` at `953dc6f...` | Fused candidate reranking |
| Generation | `qwen3.5:9b` through Ollama | Structured grounded answers |
| Visual experiment | `vidore/colqwen2.5-v0.2` at recorded revision | Page-image late interaction |

Every benchmark report records complete configured revisions. An Ollama status
response additionally records digest, parameter size, quantization, and
capabilities.

## Constraints

The default target is an RTX 4070 with 12 GB VRAM. Retrieval models are released
before generation to avoid simultaneous residency. This saves memory but can
increase cold latency. Generation concurrency is one by default.

The models were not trained specifically for binding motorsport regulations.
Metadata filtering, source provenance, conflict reporting, abstention, and
citation validation are application controls around the models; they do not
change the models' underlying knowledge.

## Evaluation policy

Model or prompt changes are evaluated on the development split first. The held-out
split is run only after configuration is frozen. Quality is reported alongside
cold/warm latency, RAM/VRAM, throughput, and index storage. Automatic claim judges
must be calibrated against 50 manually reviewed answers before their aggregate
scores are used.

Visual retrieval remains disabled unless its 40-query slice clears all quality,
confidence, latency, and storage gates implemented in
`racevault.evaluation.visual`.
