"""Check every citation the model gives against the chunks we actually sent it.

Language models can "hallucinate": produce a confident quote that is not in
the source, or point at a section that does not exist. We do not ask the
model whether it is sure; we check in code. A citation is kept only if

1. its chunk id is one of the chunks we sent, and
2. its quote really appears in that chunk's text.

Anything else is removed and the case is flagged for a closer look.
"""

from dataclasses import dataclass

from app.schemas.verdict import Citation
from app.services.retriever import RetrievedChunk
from app.services.text_matching import text_contains_quote

REASON_UNKNOWN_CHUNK = "chunk_not_sent"
REASON_QUOTE_NOT_FOUND = "quote_not_in_chunk"


@dataclass
class CheckedCitation:
    """A citation after checking, with the chunk's details for the result page."""

    chunk_id: int
    quote: str
    is_verified: bool
    failure_reason: str | None = None
    policy_name: str | None = None
    section_title: str | None = None
    page_number: int | None = None
    chunk_text: str | None = None


def check_citation(citation: Citation, chunks_by_id: dict[int, RetrievedChunk]) -> CheckedCitation:
    """Check one citation."""
    chunk = chunks_by_id.get(citation.chunk_id)
    if chunk is None:
        return CheckedCitation(
            chunk_id=citation.chunk_id,
            quote=citation.quote,
            is_verified=False,
            failure_reason=REASON_UNKNOWN_CHUNK,
        )

    is_quote_found = text_contains_quote(chunk.text, citation.quote)
    failure_reason = None
    if not is_quote_found:
        failure_reason = REASON_QUOTE_NOT_FOUND
    return CheckedCitation(
        chunk_id=citation.chunk_id,
        quote=citation.quote,
        is_verified=is_quote_found,
        failure_reason=failure_reason,
        policy_name=chunk.policy_name,
        section_title=chunk.section_title,
        page_number=chunk.page_number,
        chunk_text=chunk.text,
    )


def check_citations(
    citations: list[Citation], sent_chunks: list[RetrievedChunk]
) -> tuple[list[CheckedCitation], list[CheckedCitation]]:
    """Split citations into (verified, failed)."""
    chunks_by_id = {}
    for chunk in sent_chunks:
        chunks_by_id[chunk.chunk_id] = chunk

    verified_citations = []
    failed_citations = []
    for citation in citations:
        checked_citation = check_citation(citation, chunks_by_id)
        if checked_citation.is_verified:
            verified_citations.append(checked_citation)
        else:
            failed_citations.append(checked_citation)
    return verified_citations, failed_citations
