"""Tests for the missing-documents checklist and the appeal letter."""

from app.core.llm_client import FakeLLMClient
from app.services.next_steps import (
    build_appeal_letter_prompt,
    build_missing_information_checklist,
    draft_appeal_letter,
    fill_placeholders,
)

RETRIEVED_CHUNKS = [
    {"chunk_id": 5, "section_title": "2.2 Persistent Symptoms", "page_number": 1},
    {"chunk_id": 8, "section_title": "4 Documentation Requirements", "page_number": 2},
]
REQUIREMENT_CHECKS = [
    {"requirement": "Symptoms for six weeks", "status": "met", "chunk_id": 5},
    {
        "requirement": "Six weeks of conservative therapy",
        "status": "unclear",
        "evidence_needed": "Physical therapy records with dates",
        "chunk_id": 5,
    },
    {"requirement": "Neurological exam findings", "status": "not_met", "chunk_id": 8},
]


def test_checklist_has_one_item_per_unmet_requirement() -> None:
    checklist = build_missing_information_checklist(REQUIREMENT_CHECKS, RETRIEVED_CHUNKS)
    assert len(checklist) == 2
    assert checklist[0]["what_to_add"] == "Physical therapy records with dates"
    assert checklist[0]["policy_section"] == "2.2 Persistent Symptoms"


def test_checklist_item_without_evidence_text_gets_a_default() -> None:
    checklist = build_missing_information_checklist(REQUIREMENT_CHECKS, RETRIEVED_CHUNKS)
    assert checklist[1]["what_to_add"] == "Documentation showing: Neurological exam findings"
    assert checklist[1]["policy_section"] == "4 Documentation Requirements"


def test_fill_placeholders_uses_first_original_value() -> None:
    pii_values = {"[PATIENT_NAME]": ["Jordan Testcase", "Testcase"], "[MEMBER_ID]": ["FAKE-1"]}
    filled = fill_placeholders("For [PATIENT_NAME] ([MEMBER_ID]).", pii_values)
    assert filled == "For Jordan Testcase (FAKE-1)."


def test_unknown_placeholders_are_left_for_a_human() -> None:
    assert fill_placeholders("Signed, [PROVIDER_NAME]", {}) == "Signed, [PROVIDER_NAME]"


def test_appeal_prompt_lists_only_unmet_requirements_and_cited_sections() -> None:
    prompt = build_appeal_letter_prompt(
        {"physical_therapy_weeks": {"value": 0}},
        "No therapy documented.",
        REQUIREMENT_CHECKS,
        [{"section_title": "2.2 Persistent Symptoms", "quote": "six weeks of therapy"}],
    )
    assert "Six weeks of conservative therapy" in prompt
    assert '"Symptoms for six weeks"' not in prompt
    assert "2.2 Persistent Symptoms" in prompt
    assert prompt.startswith("<case_details>")


def test_draft_appeal_letter_calls_the_letter_task() -> None:
    fake_client = FakeLLMClient({"appeal_letter": ["Dear reviewer, [PATIENT_NAME]"]})
    response = draft_appeal_letter({}, "reason", REQUIREMENT_CHECKS, [], fake_client, "v1")
    assert response.text == "Dear reviewer, [PATIENT_NAME]"
    assert fake_client.sent_prompts[0].task_name == "appeal_letter"
