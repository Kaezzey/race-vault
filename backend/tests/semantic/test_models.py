from __future__ import annotations

import pytest

from racevault.semantic.models import DenseVector, SemanticSearchRequest
from tests.semantic.factories import unit_vector


def test_dense_vector_requires_1024_normalized_finite_values() -> None:
    assert len(unit_vector().values) == 1024

    with pytest.raises(ValueError, match="1024"):
        DenseVector(values=(1.0, 0.0))

    with pytest.raises(ValueError, match="L2-normalized"):
        DenseVector(values=tuple([0.5] + [0.0] * 1023))


def test_semantic_query_rejects_whitespace() -> None:
    with pytest.raises(ValueError, match="query must contain text"):
        SemanticSearchRequest(query="   ")
