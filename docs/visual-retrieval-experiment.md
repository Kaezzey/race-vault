# Visual retrieval experiment

The experimental channel renders pages, hashes the exact image bytes, produces
multi-vector embeddings with pinned `vidore/colqwen2.5-v0.2`, and ranks pages with
MaxSim. The repository includes a dependency-free reference scorer so ranking and
tie behaviour can be unit-tested without loading the model.

Build a 40-query held-out visual slice covering diagrams, table geometry,
layout-dependent values, OCR failures, and page-level evidence. Compare text-only,
visual-only, and three-channel RRF under the same query set.

Feed the measured text/fused nDCG@10, paired bootstrap interval, added p95 latency,
index size, and query count to `racevault-visual-gate`. The visual channel remains
absent from production results unless the command exits successfully. A rejected
experiment is published with its reasons and cost measurements.
