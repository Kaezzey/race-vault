<!-- Extracted from README.md to keep the README readable in one pass. -->

# Design decisions

Each row records a problem measured in the pipeline, the change made, and
the result. Each decision is general behaviour. None of them depends on a fixed
list of user questions.

| Problem observed | Decision | Result |
| --- | --- | --- |
| Relevant passages from the wrong championship or season entered the candidate pool. | Resolve metadata from the query and pre-filter both retrieval channels. | BM25 and BGE-M3 search the same valid scope instead of discarding invalid results after fusion. |
| Exact identifiers and natural-language synonyms need different matching behaviour. | Use BM25 and BGE-M3 as complementary channels. | BM25 handles clauses, part numbers, and model codes. BGE-M3 handles paraphrases. |
| BM25 missed a passage whenever the document and the question named a part differently. | Add a search-time synonym graph and a light stemmer to the lexical analyzer. | A question about `tire pressure` matches a regulation that says `tyre pressures`. Lexical MRR on the legacy query set rose from 0.717 to 0.788, with no query ranking worse. |
| A question that named no season retrieved from superseded and current regulations equally. | Derive the revision from the filename, then narrow a resolved championship to its newest edition. | An unqualified question returns the regulations in force, and a comparison narrows each side on its own. |
| Retrieval returned candidates for questions the corpus cannot answer, so generation produced an answer anyway. | Calibrate a reranker-score threshold on the development split alone, then freeze it. | The system answers 9 of 9 answerable held-out queries and abstains on 4 of 4 out-of-corpus ones. |
| One oversized table chunk ended evidence packing and cost every lower-ranked passage its slot. | Skip the oversized passage and keep packing. Cut a truncated passage at a line boundary. | A large table no longer empties the evidence set, and a truncated table never leaves a row split across its columns. |
| A table of hand-written phrase expansions decomposed compound questions. | Read the structure of the question instead, and leave terminology to the synonym graph. | Decomposition works on phrasings nobody tested, and 150 lines of per-question rules are gone. |
| A multi-championship question could spend the candidate budget on the first scopes found. | Run retrieval per named scope and interleave scoped candidates before reranking. | Comparisons retain evidence coverage for each requested championship. |
| Retrieval lost the origin of extracted text. | Carry page, section, clause, coordinates, hashes, and source metadata through every pipeline stage. | Every answer exposes the passage and the retrieval trace behind it. |
| A local model could return truncated JSON at a small output limit. | Increase the output budget, simplify the response schema, and validate every cited evidence identifier. | The API rejects invalid or incomplete model output instead of presenting it as a grounded answer. |
| Embedding, reranking, and generation appeared to compete for limited GPU memory, so the pipeline evicted each model after use. | Measure the memory first. The embedder and reranker occupy 1.1 GB each, and all three models fit on a 12 GB card at the same time. | Keeping the models resident removed 13.7 seconds of reloading per answer. Eviction remains available for smaller GPUs. |
| Every call to Ollama opened a connection, and `localhost` resolved to `::1` before `127.0.0.1`. | Hold one HTTP connection for the process, and resolve the model identity one time instead of before every generation. | A connection cost 2.04 seconds and now costs 0.5 milliseconds. The mean answer fell from 26.0 to 7.8 seconds. |
| Small backend changes triggered installation and export of the full ML dependency layer. | Install locked dependencies before copying application source and bind-mount source in development. | Python edits reload without rebuilding Torch, CUDA, Docling, or Transformers. |
| PDF import failed in the Linux image with `libxcb.so.1` missing. | Install the required native XCB runtime libraries in the API image. | Docling and its OpenCV dependencies can import during ingestion. |
| Inconsistent championship metadata prevented valid pre-filters. | Canonicalize metadata and refresh stored source and chunk metadata. | Explicit scopes map to the intended corpus documents without hard-coded question rules. |

Each decision is general pipeline behaviour. None of them depends on a fixed list of user questions.
