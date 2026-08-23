from __future__ import annotations

from racevault.evaluation.experiment import canonical_sha256


def test_configuration_fingerprint_is_order_independent() -> None:
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256(
        {"b": 2, "a": 1}
    )
