"""Tests for splitting policies into chunks."""

from app.services.pdf_reader import PdfPage
from app.services.policy_chunker import (
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    chunk_policy,
    is_heading,
    section_number,
)


def numbered_words(prefix: str, count: int) -> str:
    """'a0 a1 a2 ...' so we can see exactly which words ended up where."""
    words = []
    for i in range(count):
        words.append(f"{prefix}{i}")
    return " ".join(words)


def test_recognises_numbered_and_capital_headings() -> None:
    assert is_heading("2.1 Red Flag Conditions")
    assert is_heading("Section 4 Documentation Requirements")
    assert is_heading("COVERAGE CRITERIA")


def test_sentences_are_not_headings() -> None:
    assert not is_heading("MRI is covered when symptoms last six weeks.")
    assert not is_heading("72148, MRI lumbar spine without contrast; 72149, with contrast")
    assert not is_heading("")


def test_section_number_is_read_from_title() -> None:
    assert section_number("2.1 Red Flag Conditions") == "2.1"
    assert section_number("Section 4 Documentation") == "4"
    assert section_number("Introduction") is None


def test_long_section_is_split_with_overlap() -> None:
    pages = [PdfPage(1, "1 Purpose\n" + numbered_words("w", 1200))]
    chunks = chunk_policy(pages)

    assert len(chunks) == 3
    first_chunk_words = chunks[0].text.split()
    second_chunk_words = chunks[1].text.split()
    assert len(first_chunk_words) == CHUNK_SIZE_WORDS
    # The last 50 words of one chunk are the first 50 of the next.
    assert first_chunk_words[-CHUNK_OVERLAP_WORDS:] == second_chunk_words[:CHUNK_OVERLAP_WORDS]


def test_chunks_never_cross_sections_and_keep_titles() -> None:
    pages = [PdfPage(1, "1 Purpose\nshort purpose text\n2 Coverage\ncoverage text here")]
    chunks = chunk_policy(pages)
    assert [chunk.section_title for chunk in chunks] == ["1 Purpose", "2 Coverage"]
    assert chunks[1].text == "coverage text here"


def test_page_number_is_page_of_first_word() -> None:
    pages = [
        PdfPage(1, "1 Purpose\nfirst page words"),
        PdfPage(2, "2 Coverage\nsecond page words"),
    ]
    chunks = chunk_policy(pages)
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2


def test_text_before_first_heading_goes_to_introduction() -> None:
    chunks = chunk_policy([PdfPage(1, "Policy title text\n1 Purpose\nbody")])
    assert chunks[0].section_title == "Introduction"


def test_chunk_indexes_run_in_reading_order() -> None:
    pages = [PdfPage(1, "1 A\n" + numbered_words("a", 600) + "\n2 B\nb words")]
    indexes = [chunk.chunk_index for chunk in chunk_policy(pages)]
    assert indexes == [0, 1, 2]
