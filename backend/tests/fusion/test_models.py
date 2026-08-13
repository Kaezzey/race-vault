from __future__ import annotations

import pytest

from racevault.fusion.models import HybridSearchRequest


def test_hybrid_request_validates_query_and_depths() -> None:
    with pytest.raises(ValueError, match="query must contain text"):
        HybridSearchRequest(query="   ")

    with pytest.raises(ValueError, match="rerank_limit"):
        HybridSearchRequest(query="brakes", fusion_limit=10, rerank_limit=11)

    with pytest.raises(ValueError, match="result_limit"):
        HybridSearchRequest(query="brakes", rerank_limit=5, result_limit=6)
