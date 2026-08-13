"""OpenSearch-backed lexical retrieval."""

from racevault.lexical.client import OpenSearchClient
from racevault.lexical.models import LexicalSearchRequest, SearchFilters

__all__ = ["LexicalSearchRequest", "OpenSearchClient", "SearchFilters"]
