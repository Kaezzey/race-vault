from __future__ import annotations

import json

import httpx

from racevault.lexical.client import OpenSearchClient
from racevault.lexical.documents import build_index_document
from racevault.lexical.models import LexicalSearchRequest
from tests.lexical.factories import chunking_artifact


def test_index_artifact_creates_index_replaces_source_and_checks_count() -> None:
    artifact = chunking_artifact()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        if request.method == "PUT":
            return httpx.Response(200, json={"acknowledged": True})
        if "_delete_by_query" in request.url.path:
            return httpx.Response(200, json={"deleted": 2})
        if request.url.path == "/_bulk":
            return httpx.Response(200, json={"errors": False, "items": []})
        if request.url.path.endswith("/_refresh"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/_count"):
            return httpx.Response(200, json={"count": len(artifact.chunks)})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    with OpenSearchClient(
        base_url="http://test",
        index_name="racevault-test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.index_artifact(artifact)

    assert result.indexed_chunks == len(artifact.chunks)
    assert result.removed_chunks == 2
    bulk_position = next(
        number
        for number, request in enumerate(requests)
        if request.url.path == "/_bulk"
    )
    delete_position = next(
        number
        for number, request in enumerate(requests)
        if "_delete_by_query" in request.url.path
    )
    assert bulk_position < delete_position
    bulk = next(request for request in requests if request.url.path == "/_bulk")
    lines = bulk.content.decode().strip().splitlines()
    assert len(lines) == len(artifact.chunks) * 2
    assert json.loads(lines[1])["evidence_text"] == artifact.chunks[0].evidence_text


def test_search_parses_citation_ready_hit() -> None:
    artifact = chunking_artifact()
    document = build_index_document(artifact, artifact.chunks[0])

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "hits": {
                    "total": {"value": 1, "relation": "eq"},
                    "hits": [
                        {
                            "_score": 4.25,
                            "_source": document,
                            "highlight": {
                                "contextual_text": ["<mark>ABS M5</mark>"]
                            },
                        }
                    ],
                }
            },
        )

    with OpenSearchClient(
        base_url="http://test",
        index_name="racevault-test",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = client.search(LexicalSearchRequest(query="ABS M5"))

    assert response.total == 1
    assert response.hits[0].chunk_id == artifact.chunks[0].chunk_id
    assert response.hits[0].page_numbers == (2,)
    assert response.hits[0].highlights == ("<mark>ABS M5</mark>",)


def test_delete_source_uses_source_hash_filter() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"deleted": 7})

    with OpenSearchClient(
        base_url="http://test",
        index_name="racevault-test",
        transport=httpx.MockTransport(handler),
    ) as client:
        deleted = client.delete_source("a" * 64)

    assert deleted == 7
    assert requests[0].method == "POST"
    assert json.loads(requests[0].content)["query"] == {
        "term": {"source_sha256": "a" * 64}
    }
