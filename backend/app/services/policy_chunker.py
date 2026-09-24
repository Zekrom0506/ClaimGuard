"""Split policy documents into overlapping chunks that keep their section and page.

We first split the policy into sections using its headings, then cut each
section into windows of about 500 words that overlap by 50 words. Chunks never
cross a section boundary, so every chunk belongs to exactly one section; the
overlap means a sentence cut at the end of one chunk still appears whole at
the start of the next.
"""

import re
from dataclasses import dataclass, field

from app.services.pdf_reader import PdfPage

CHUNK_SIZE_WORDS = 500
CHUNK_OVERLAP_WORDS = 50
MAX_HEADING_WORDS = 12
FIRST_SECTION_TITLE = "Introduction"

# "2.1 Red Flag Conditions", "Section 4 Documentation Requirements", "3. Coverage".
NUMBERED_HEADING_PATTERN = re.compile(r"^(section\s+)?\d+(\.\d+)*\.?\s+[A-Z]", re.IGNORECASE)
SECTION_NUMBER_PATTERN = re.compile(r"^(?:section\s+)?(\d+(?:\.\d+)*)", re.IGNORECASE)


@dataclass
class PolicySection:
    """The words of one section, each paired with the page it was on."""

    title: str
    words_with_pages: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class TextChunk:
    """One chunk ready to be embedded and stored."""

    section_title: str
    page_number: int
    chunk_index: int
    text: str


def is_heading(line: str) -> bool:
    """Guess whether a line is a section heading.

    Headings are short, do not end with a full stop, and either start with a
    section number or are written in capitals.
    """
    stripped_line = line.strip()
    if stripped_line == "" or stripped_line.endswith("."):
        return False
    if len(stripped_line.split()) > MAX_HEADING_WORDS:
        return False
    if NUMBERED_HEADING_PATTERN.match(stripped_line):
        return True
    letters_only = re.sub(r"[^A-Za-z]", "", stripped_line)
    return len(letters_only) >= 4 and letters_only.isupper()


def section_number(section_title: str) -> str | None:
    """Return "2.1" for "2.1 Red Flag Conditions", or None if the title has no number."""
    match = SECTION_NUMBER_PATTERN.match(section_title.strip())
    if match is None:
        return None
    return match.group(1)


def split_into_sections(pages: list[PdfPage]) -> list[PolicySection]:
    """Walk through every line, starting a new section at each heading."""
    sections = [PolicySection(title=FIRST_SECTION_TITLE)]
    for page in pages:
        for line in page.text.splitlines():
            if is_heading(line):
                sections.append(PolicySection(title=line.strip()))
                continue
            for word in line.split():
                sections[-1].words_with_pages.append((word, page.page_number))

    non_empty_sections = []
    for section in sections:
        if section.words_with_pages:
            non_empty_sections.append(section)
    return non_empty_sections


def chunk_section(section: PolicySection, first_chunk_index: int) -> list[TextChunk]:
    """Cut one section into overlapping windows of words."""
    chunks = []
    step = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS
    total_words = len(section.words_with_pages)
    window_start = 0
    while window_start < total_words:
        window = section.words_with_pages[window_start : window_start + CHUNK_SIZE_WORDS]
        window_words = []
        for word, _page_number in window:
            window_words.append(word)
        chunks.append(
            TextChunk(
                section_title=section.title,
                page_number=window[0][1],
                chunk_index=first_chunk_index + len(chunks),
                text=" ".join(window_words),
            )
        )
        if window_start + CHUNK_SIZE_WORDS >= total_words:
            break
        window_start += step
    return chunks


def chunk_policy(pages: list[PdfPage]) -> list[TextChunk]:
    """Split a whole policy into chunks, numbered in reading order."""
    all_chunks: list[TextChunk] = []
    for section in split_into_sections(pages):
        all_chunks.extend(chunk_section(section, first_chunk_index=len(all_chunks)))
    return all_chunks
