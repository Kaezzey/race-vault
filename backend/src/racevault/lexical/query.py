"""OpenSearch BM25 query construction."""

from __future__ import annotations

from racevault.lexical.models import LexicalSearchRequest
from racevault.retrieval.models import SearchFilters

FILTER_FIELDS = {
    "source_sha256": "source_sha256",
    "source_role": "source_role",
    "document_class": "document_class",
    "authority": "authority",
    "vehicle_generation": "vehicle_generation",
    "championship": "championship",
    "season": "season",
    "revision": "revision",
    "page_number": "page_numbers",
    "chunk_kind": "kind",
    "oversize": "oversize",
}


def _filter_clauses(filters: SearchFilters) -> list[dict[str, object]]:
    values = filters.model_dump(exclude_none=True)
    return [
        {"term": {FILTER_FIELDS[name]: value}} for name, value in values.items()
    ]


def build_search_body(request: LexicalSearchRequest) -> dict[str, object]:
    return {
        "size": request.limit,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": request.query,
                            "type": "best_fields",
                            "operator": "and",
                            "fields": [
                                "contextual_text^4",
                                "contextual_text.codes^6",
                                "section_text^2",
                                "section_text.codes^3",
                                "source_filename",
                                "source_filename.codes^2",
                            ],
                            "tie_breaker": 0.2,
                        }
                    }
                ],
                "filter": _filter_clauses(request.filters),
            }
        },
        "highlight": {
            "fields": {
                "contextual_text": {
                    "fragment_size": 240,
                    "number_of_fragments": 2,
                }
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        },
        "sort": [{"_score": "desc"}, {"chunk_id": "asc"}],
    }
