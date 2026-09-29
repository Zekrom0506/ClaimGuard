"""Tests for checking the model's citations against the chunks it was given."""

from app.schemas.verdict import Citation
from app.services.citation_checker import (
    REASON_QUOTE_NOT_FOUND,
    REASON_UNKNOWN_CHUNK,
    check_citations,
)
from app.services.retriever import RetrievedChunk

SENT_CHUNK = RetrievedChunk(
    chunk_id=5,
    policy_name="Sample Policy",
    section_title="2.2 Persistent Symptoms",
    page_number=1,
    text="Requests with symptoms for six weeks or longer but no conservative\ntherapy do "
    "not meet this section.",
    fused_score=0.03,
    vector_rank=1,
    keyword_rank=2,
)


def test_exact_quote_from_sent_chunk_is_verified() -> None:
    citation = Citation(chunk_id=5, quote="symptoms for six weeks or longer but no conservative")
    verified, failed = check_citations([citation], [SENT_CHUNK])
    assert len(verified) == 1
    assert failed == []
    assert verified[0].section_title == "2.2 Persistent Symptoms"


def test_quote_matches_across_line_breaks_and_case() -> None:
    citation = Citation(chunk_id=5, quote="No Conservative Therapy do not meet this section.")
    verified, _failed = check_citations([citation], [SENT_CHUNK])
    assert len(verified) == 1


def test_made_up_quote_fails() -> None:
    citation = Citation(chunk_id=5, quote="MRI is always covered after four weeks.")
    verified, failed = check_citations([citation], [SENT_CHUNK])
    assert verified == []
    assert failed[0].failure_reason == REASON_QUOTE_NOT_FOUND


def test_chunk_that_was_not_sent_fails() -> None:
    citation = Citation(chunk_id=42, quote="symptoms for six weeks or longer")
    _verified, failed = check_citations([citation], [SENT_CHUNK])
    assert failed[0].failure_reason == REASON_UNKNOWN_CHUNK


def test_paraphrased_quote_fails() -> None:
    citation = Citation(chunk_id=5, quote="requests lacking conservative therapy fail this section")
    verified, _failed = check_citations([citation], [SENT_CHUNK])
    assert verified == []
