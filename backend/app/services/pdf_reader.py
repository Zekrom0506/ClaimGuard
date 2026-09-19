"""Extract text from PDF files with PyMuPDF."""

import unicodedata
from dataclasses import dataclass

import pymupdf


class PdfReadError(Exception):
    """The file could not be opened as a PDF or has no readable text."""


@dataclass
class PdfPage:
    """The text of one page and its 1-based page number."""

    page_number: int
    text: str


def normalize_text(text: str) -> str:
    """Clean up PDF text so searching and quote checking work.

    NFKC turns typographic ligatures such as "ﬂ" back into normal letters
    ("fl"); without it, "red ﬂag" would never match the word "flag".
    """
    normalized = unicodedata.normalize("NFKC", text)
    return normalized.replace(" ", " ")


def read_pdf_pages(pdf_bytes: bytes) -> list[PdfPage]:
    """Return the normalized text of every page."""
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise PdfReadError("The file is not a readable PDF.") from error

    pages = []
    with document:
        for page_index, page in enumerate(document):
            pages.append(PdfPage(page_number=page_index + 1, text=normalize_text(page.get_text())))
    return pages


def read_pdf_text(pdf_bytes: bytes) -> str:
    """Return the text of the whole PDF as one string."""
    pages = read_pdf_pages(pdf_bytes)
    page_texts = []
    for page in pages:
        page_texts.append(page.text.strip())
    full_text = "\n\n".join(page_texts).strip()
    if full_text == "":
        # Scanned PDFs have images instead of text; OCR would be needed.
        raise PdfReadError("The PDF contains no extractable text.")
    return full_text
