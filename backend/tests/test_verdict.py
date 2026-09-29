"""Tests for the verdict step: prompt building, checks and flags."""

import pytest

from app.core.llm_client import FakeLLMClient
from app.schemas.verdict import RequirementCheck, VerdictAnswer
from app.services.retriever import RetrievedChunk
from app.services.verdict import (
    FLAG_CITATION_FAILED,
    FLAG_INCONSISTENT_VERDICT,
    FLAG_NO_VALID_CITATIONS,
    FLAG_VERDICT_INVALID,
    build_verdict_user_prompt,
    find_consistency_problems,
    generate_verdict,
)
from tests.fakes import load_recorded_response

CHUNK_FIVE = RetrievedChunk(
    chunk_id=5,
    policy_name="Sample Lumbar Mri Policy",
    section_title="2.2 Persistent Symptoms After Conservative Therapy",
    page_number=1,
    text="In the absence of red flag conditions, imaging is considered medically necessary when "
    "both of the following are documented. Requests with symptoms for six weeks or longer but "
    "no conservative therapy do not meet this section.",
    fused_score=0.03,
    vector_rank=1,
    keyword_rank=1,
)
EXTRACTED_FIELDS = {
    "symptom_duration_weeks": {"value": 16, "source_sentence": "for 4 months"},
    "physical_therapy_weeks": {"value": 0, "source_sentence": "No physical therapy."},
    "clinical_summary": "Back pain for 4 months, no therapy.",
}


def run_verdict(recorded_answers: list[str]):
    fake_client = FakeLLMClient({"verdict": recorded_answers})
    outcome = generate_verdict(EXTRACTED_FIELDS, "masked notes", [CHUNK_FIVE], fake_client, "v1")
    return outcome, fake_client


def make_answer(verdict: str, statuses: list[str]) -> VerdictAnswer:
    requirements = []
    for status in statuses:
        requirements.append(RequirementCheck(requirement="some requirement", status=status))
    return VerdictAnswer(
        verdict=verdict,
        reason="A short reason for the test.",
        requirements=requirements,
        citations=[{"chunk_id": 5, "quote": "some quote text"}],
    )


def test_valid_verdict_with_real_citation_has_no_flags() -> None:
    outcome, _client = run_verdict([load_recorded_response("verdict_eval_033_denied.json")])
    assert outcome.answer.verdict == "likely_denied"
    assert len(outcome.verified_citations) == 1
    assert outcome.flags == []


def test_hallucinated_citations_are_removed_and_flagged() -> None:
    outcome, _client = run_verdict([load_recorded_response("verdict_hallucinated.json")])
    assert outcome.verified_citations == []
    assert len(outcome.failed_citations) == 2
    assert FLAG_CITATION_FAILED in outcome.flags
    assert FLAG_NO_VALID_CITATIONS in outcome.flags


def test_invalid_verdict_twice_is_flagged() -> None:
    outcome, client = run_verdict(['{"verdict": "probably fine"}'])
    assert outcome.answer is None
    assert FLAG_VERDICT_INVALID in outcome.flags
    assert len(client.sent_prompts) == 2


def test_prompt_contains_values_not_source_sentences() -> None:
    prompt = build_verdict_user_prompt(EXTRACTED_FIELDS, "masked notes", [CHUNK_FIVE])
    assert '"physical_therapy_weeks": 0' in prompt
    assert "source_sentence" not in prompt


def test_prompt_labels_each_excerpt_with_id_section_and_page() -> None:
    prompt = build_verdict_user_prompt(EXTRACTED_FIELDS, "masked notes", [CHUNK_FIVE])
    assert '<policy_excerpt id="5"' in prompt
    assert 'section="2.2 Persistent Symptoms After Conservative Therapy"' in prompt
    assert 'page="1"' in prompt


@pytest.mark.parametrize(
    ("verdict", "statuses", "is_consistent"),
    [
        ("likely_approved", ["met", "met"], True),
        ("likely_approved", ["met", "not_met"], False),
        ("likely_approved", ["unclear"], False),
        ("likely_denied", ["met", "not_met"], True),
        ("likely_denied", ["met", "unclear"], False),
        ("missing_information", ["met", "unclear"], True),
    ],
)
def test_consistency_rules(verdict: str, statuses: list[str], is_consistent: bool) -> None:
    problems = find_consistency_problems(make_answer(verdict, statuses))
    assert (problems == []) is is_consistent
    if not is_consistent:
        assert problems == [FLAG_INCONSISTENT_VERDICT]
