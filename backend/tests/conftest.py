"""Test fixtures that keep temporary files inside the writable workspace."""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_TEMP_ROOT = Path(__file__).resolve().parents[2] / ".test-work"


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    TEST_TEMP_ROOT.mkdir(exist_ok=True)
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)
        TEST_TEMP_ROOT.rmdir()
