"""Small OpenSearch HTTP client for index management and BM25 retrieval."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Self, cast

import httpx

from racevault.chunking.models import ChunkingArtifact
from racevault.lexical.documents import artifact_identity, build_index_document
from racevault.lexical.mapping import INDEX_SCHEMA_VERSION, index_definition
from racevault.lexical.models import (
    IndexingResult,
    LexicalSearchHit,
    LexicalSearchRequest,
    LexicalSearchResponse,
)
from racevault.lexical.query import build_search_body


class OpenSearchError(RuntimeError):
    """Raised when OpenSearch rejects a RaceVault operation."""


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OpenSearchError(f"invalid OpenSearch response: expected {context}")
    return cast(Mapping[str, Any], value)


def _ndjson_line(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


class OpenSearchClient:
    def __init__(
        self,
        *,
        base_url: str,
        index_name: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.index_name = index_name
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        allowed_statuses: tuple[int, ...] = (),
    ) -> httpx.Response:
        try:
            response = self._client.request(
                method,
                path,
                json=json_body,
                content=content,
                headers=headers,
            )
        except httpx.RequestError as error:
            raise OpenSearchError(f"OpenSearch request failed: {error}") from error
        if response.status_code not in allowed_statuses:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                detail = response.text[:500]
                raise OpenSearchError(
                    f"OpenSearch returned {response.status_code}: {detail}"
                ) from error
        return response

    def ensure_index(self) -> bool:
        response = self._request(
            "GET", f"/{self.index_name}", allowed_statuses=(404,)
        )
        if response.status_code == 404:
            self._request("PUT", f"/{self.index_name}", json_body=index_definition())
            return True

        body = _mapping(response.json(), "index mapping")
        index = _mapping(body.get(self.index_name), "named index mapping")
        mappings = _mapping(index.get("mappings"), "mappings")
        metadata = _mapping(mappings.get("_meta"), "mapping metadata")
        version = metadata.get("racevault_schema_version")
        if version != INDEX_SCHEMA_VERSION:
            raise OpenSearchError(
                f"index schema mismatch: expected {INDEX_SCHEMA_VERSION}, got {version}"
            )
        return False

    def delete_index(self) -> bool:
        response = self._request(
            "DELETE", f"/{self.index_name}", allowed_statuses=(404,)
        )
        return response.status_code != 404

    def _remove_stale_source(
        self, source_sha256: str, current_artifact_id: str
    ) -> int:
        response = self._request(
            "POST",
            f"/{self.index_name}/_delete_by_query?refresh=true&conflicts=proceed",
            json_body={
                "query": {
                    "bool": {
                        "filter": [{"term": {"source_sha256": source_sha256}}],
                        "must_not": [
                            {"term": {"artifact_id": current_artifact_id}}
                        ],
                    }
                }
            },
        )
        body = _mapping(response.json(), "delete response")
        deleted = body.get("deleted", 0)
        if not isinstance(deleted, int):
            raise OpenSearchError("invalid OpenSearch delete count")
        return deleted

    def _bulk_index(self, artifact: ChunkingArtifact, batch_size: int = 250) -> None:
        for start in range(0, len(artifact.chunks), batch_size):
            lines: list[bytes] = []
            for chunk in artifact.chunks[start : start + batch_size]:
                action = {"index": {"_index": self.index_name, "_id": chunk.chunk_id}}
                lines.append(_ndjson_line(action))
                document = build_index_document(artifact, chunk)
                lines.append(_ndjson_line(document))
            content = b"\n".join(lines) + b"\n"
            response = self._request(
                "POST",
                "/_bulk?refresh=false",
                content=content,
                headers={"Content-Type": "application/x-ndjson"},
            )
            body = _mapping(response.json(), "bulk response")
            if body.get("errors") is True:
                items = body.get("items")
                raise OpenSearchError(
                    f"OpenSearch bulk indexing failed: {json.dumps(items)[:1000]}"
                )
        self._request("POST", f"/{self.index_name}/_refresh")

    def index_artifact(self, artifact: ChunkingArtifact) -> IndexingResult:
        self.ensure_index()
        self._bulk_index(artifact)
        removed = self._remove_stale_source(
            artifact.source.sha256, artifact_identity(artifact)
        )
        indexed = self.count(source_sha256=artifact.source.sha256)
        if indexed != len(artifact.chunks):
            expected = len(artifact.chunks)
            raise OpenSearchError(
                f"indexed chunk count mismatch: expected {expected}, got {indexed}"
            )
        return IndexingResult(
            index_name=self.index_name,
            source_sha256=artifact.source.sha256,
            indexed_chunks=indexed,
            removed_chunks=removed,
        )

    def count(self, source_sha256: str | None = None) -> int:
        query: dict[str, object] = {"match_all": {}}
        if source_sha256 is not None:
            query = {"term": {"source_sha256": source_sha256}}
        response = self._request(
            "POST", f"/{self.index_name}/_count", json_body={"query": query}
        )
        body = _mapping(response.json(), "count response")
        count = body.get("count")
        if not isinstance(count, int):
            raise OpenSearchError("invalid OpenSearch count")
        return count

    def search(self, request: LexicalSearchRequest) -> LexicalSearchResponse:
        response = self._request(
            "POST",
            f"/{self.index_name}/_search",
            json_body=build_search_body(request),
        )
        body = _mapping(response.json(), "search response")
        hits_container = _mapping(body.get("hits"), "hits")
        total_value = hits_container.get("total", 0)
        if isinstance(total_value, Mapping):
            total = _mapping(total_value, "total hits").get("value", 0)
        else:
            total = total_value
        if not isinstance(total, int):
            raise OpenSearchError("invalid OpenSearch total hit count")

        raw_hits = hits_container.get("hits", [])
        if not isinstance(raw_hits, list):
            raise OpenSearchError("invalid OpenSearch hits list")
        parsed: list[LexicalSearchHit] = []
        for raw_hit in raw_hits:
            hit = _mapping(raw_hit, "search hit")
            source = dict(_mapping(hit.get("_source"), "search hit source"))
            score = hit.get("_score", 0.0)
            if not isinstance(score, int | float):
                score = 0.0
            highlight = hit.get("highlight", {})
            fragments: object = []
            if isinstance(highlight, Mapping):
                fragments = highlight.get("contextual_text", [])
            if not isinstance(fragments, list) or not all(
                isinstance(item, str) for item in fragments
            ):
                fragments = []
            hit_fields = LexicalSearchHit.model_fields
            result = {
                name: value for name, value in source.items() if name in hit_fields
            }
            result["score"] = float(score)
            result["highlights"] = fragments
            parsed.append(LexicalSearchHit.model_validate(result))
        return LexicalSearchResponse(
            query=request.query, total=total, hits=tuple(parsed)
        )
