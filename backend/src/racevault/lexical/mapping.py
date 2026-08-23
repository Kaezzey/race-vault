"""Versioned OpenSearch index mapping for BM25 retrieval."""

from __future__ import annotations

from racevault.lexical.synonyms import MOTORSPORT_SYNONYMS

# Bumped whenever the analysis chain changes, because stored tokens change with
# it. `OpenSearchClient.ensure_index` refuses to query an index built by an
# older chain rather than silently returning degraded results.
INDEX_SCHEMA_VERSION = "2.0"
DEFAULT_INDEX_NAME = "racevault-chunks-v2"


def index_definition() -> dict[str, object]:
    keyword = {"type": "keyword", "normalizer": "racevault_keyword"}
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "normalizer": {
                    "racevault_keyword": {
                        "type": "custom",
                        "filter": ["lowercase", "asciifolding"],
                    }
                },
                "tokenizer": {
                    "racevault_code_tokenizer": {
                        "type": "pattern",
                        "pattern": r"[^\p{L}\p{N}._/-]+",
                    }
                },
                "filter": {
                    "racevault_motorsport_synonyms": {
                        "type": "synonym_graph",
                        "lenient": False,
                        "synonyms": list(MOTORSPORT_SYNONYMS),
                    }
                },
                "analyzer": {
                    # Regulations distinguish "shall" from "should" from "may",
                    # so no stop-word filter is applied. Stemming is the light
                    # dictionary-based kstem rather than Porter, which would
                    # conflate distinct technical terms.
                    "racevault_technical": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "kstem"],
                    },
                    # Synonyms expand at search time only, so the vocabulary can
                    # grow without reindexing the corpus.
                    "racevault_technical_search": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "asciifolding",
                            "racevault_motorsport_synonyms",
                            "kstem",
                        ],
                    },
                    "racevault_codes": {
                        "type": "custom",
                        "tokenizer": "racevault_code_tokenizer",
                        "filter": ["lowercase", "asciifolding"],
                    },
                },
            },
        },
        "mappings": {
            "dynamic": "strict",
            "_meta": {"racevault_schema_version": INDEX_SCHEMA_VERSION},
            "properties": {
                "chunk_id": {"type": "keyword"},
                "artifact_id": {"type": "keyword"},
                "ordinal": {"type": "integer"},
                "source_sha256": {"type": "keyword"},
                "source_path": {"type": "keyword", "index": False},
                "source_filename": {
                    "type": "text",
                    "analyzer": "racevault_technical",
                    "search_analyzer": "racevault_technical_search",
                    "fields": {
                        "codes": {"type": "text", "analyzer": "racevault_codes"}
                    },
                },
                "source_role": keyword,
                "source_metadata": {"type": "object", "enabled": False},
                "document_class": keyword,
                "strategy": keyword,
                "kind": keyword,
                "evidence_text": {"type": "text", "index": False},
                "evidence_sha256": {"type": "keyword", "index": False},
                "contextual_text": {
                    "type": "text",
                    "analyzer": "racevault_technical",
                    "search_analyzer": "racevault_technical_search",
                    "fields": {
                        "codes": {"type": "text", "analyzer": "racevault_codes"}
                    },
                },
                "contextual_sha256": {"type": "keyword", "index": False},
                "section_path": keyword,
                "section_text": {
                    "type": "text",
                    "analyzer": "racevault_technical",
                    "search_analyzer": "racevault_technical_search",
                    "fields": {
                        "codes": {"type": "text", "analyzer": "racevault_codes"}
                    },
                },
                "clause_reference": keyword,
                "page_start": {"type": "short"},
                "page_end": {"type": "short"},
                "page_numbers": {"type": "short"},
                "element_ids": {"type": "keyword", "index": False},
                "table_ids": {"type": "keyword", "index": False},
                "provenance": {"type": "object", "enabled": False},
                "character_count": {"type": "integer"},
                "oversize": {"type": "boolean"},
                "authority": keyword,
                "vehicle_generation": keyword,
                "championship": keyword,
                "season": {"type": "short"},
                "revision": keyword,
            },
        },
    }
