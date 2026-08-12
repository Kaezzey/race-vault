from __future__ import annotations

from pathlib import Path

import pytest

from racevault.extraction.pymupdf_reader import read_pdf_pages

pymupdf = pytest.importorskip("pymupdf")


def test_reader_preserves_page_geometry_text_and_blocks(tmp_path: Path) -> None:
    source = tmp_path / "fixture.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    page.insert_text((30, 40), "RaceVault evidence")
    document.save(source)
    document.close()

    page_count, pages, version = read_pdf_pages(source, 1, None)

    assert page_count == 1
    assert version
    assert pages[0].page_number == 1
    assert pages[0].width == 300
    assert pages[0].height == 400
    assert pages[0].text == "RaceVault evidence"
    assert pages[0].blocks[0].text == "RaceVault evidence"

