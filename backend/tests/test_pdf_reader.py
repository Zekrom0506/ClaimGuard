"""Tests for PDF text extraction."""

import pytest

from app.services.pdf_reader import PdfReadError, normalize_text, read_pdf_pages, read_pdf_text
from tests.conftest import evaluation_case_path, make_pdf_bytes


def test_reads_text_from_pdf() -> None:
    pdf_bytes = make_pdf_bytes("CPT Code: 72148")
    assert "CPT Code: 72148" in read_pdf_text(pdf_bytes)


def test_pages_are_numbered_from_one() -> None:
    pages = read_pdf_pages(evaluation_case_path("EVAL-001").read_bytes())
    assert pages[0].page_number == 1


def test_ligatures_are_normalized() -> None:
    assert normalize_text("red ﬂag") == "red flag"


def test_rejects_bytes_that_are_not_a_pdf() -> None:
    with pytest.raises(PdfReadError):
        read_pdf_text(b"this is not a pdf")


def test_rejects_pdf_without_text() -> None:
    with pytest.raises(PdfReadError):
        read_pdf_text(make_pdf_bytes(""))
