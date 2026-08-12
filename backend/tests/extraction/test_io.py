from __future__ import annotations

import json
from pathlib import Path

import pytest

from racevault.extraction.io import (
    canonical_json_bytes,
    resolve_corpus_source,
    sha256_file,
)


def test_canonical_json_is_sorted_and_replaces_non_finite_numbers() -> None:
    first = canonical_json_bytes({"z": float("nan"), "a": [2, 1]})
    second = canonical_json_bytes({"a": [2, 1], "z": float("nan")})

    assert first == second
    assert json.loads(first) == {"a": [2, 1], "z": None}


def test_sha256_file_uses_file_contents(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"racevault")

    assert sha256_file(source) == (
        "ac0aada010714561c82ba897187d21af3d6ac7b0c50311afffb42b0b89d97958"
    )


def test_resolve_corpus_source_rejects_path_escape(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()

    with pytest.raises(ValueError, match="inside the corpus root"):
        resolve_corpus_source(corpus, "../outside.pdf")
