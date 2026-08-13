"""Versioned OpenSearch index mapping for BM25 retrieval."""

from __future__ import annotations

INDEX_SCHEMA_VERSION = "1.0"
DEFAULT_INDEX_NAME = "racevault-chunks-v1"


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
                "analyzer": {
                    "racevault_technical": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding"],
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
                    "fields": {
                        "codes": {"type": "text", "analyzer": "racevault_codes"}
                    },
                },
                "contextual_sha256": {"type": "keyword", "index": False},
                "section_path": keyword,
                "section_text": {
                    "type": "text",
                    "analyzer": "racevault_technical",
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
