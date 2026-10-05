"""What to do next: a checklist of missing documents, or a draft appeal letter."""

import json
import re

from app.core.llm_client import LLMClient, LLMResponse
from app.services.prompt_loader import load_prompt
from app.services.prompt_safety import wrap_untrusted_text
from app.services.verdict import facts_for_prompt

PLACEHOLDER_PATTERN = re.compile(r"\[[A-Z_]+\]")


def find_section_for_chunk(chunk_id: int | None, retrieved_chunks: list[dict]) -> str | None:
    """Section title of a retrieved chunk, looked up by id."""
    for chunk_summary in retrieved_chunks:
        if chunk_summary["chunk_id"] == chunk_id:
            return chunk_summary["section_title"]
    return None


def build_missing_information_checklist(
    requirement_checks: list[dict], retrieved_chunks: list[dict]
) -> list[dict]:
    """One item per requirement that is not met or unclear, linked to its policy section."""
    checklist = []
    for requirement_check in requirement_checks:
        if requirement_check["status"] == "met":
            continue
        what_to_add = requirement_check.get("evidence_needed")
        if not what_to_add:
            what_to_add = f"Documentation showing: {requirement_check['requirement']}"
        checklist.append(
            {
                "what_to_add": what_to_add,
                "requirement": requirement_check["requirement"],
                "policy_section": find_section_for_chunk(
                    requirement_check.get("chunk_id"), retrieved_chunks
                ),
                "chunk_id": requirement_check.get("chunk_id"),
            }
        )
    return checklist


def build_appeal_letter_prompt(
    extracted_fields: dict,
    verdict_reason: str,
    requirement_checks: list[dict],
    verified_citations: list[dict],
) -> str:
    """Facts, unmet requirements and cited sections, fenced off as data."""
    unmet_requirements = []
    for requirement_check in requirement_checks:
        if requirement_check["status"] != "met":
            unmet_requirements.append(requirement_check["requirement"])

    cited_sections = []
    for citation in verified_citations:
        cited_sections.append(
            {"section": citation["section_title"], "policy_text": citation["quote"]}
        )

    case_details = (
        "Case facts:\n"
        + json.dumps(facts_for_prompt(extracted_fields), indent=2)
        + "\n\nWhy the request is likely to be denied:\n"
        + verdict_reason
        + "\n\nRequirements not met:\n"
        + json.dumps(unmet_requirements, indent=2)
        + "\n\nPolicy sections involved:\n"
        + json.dumps(cited_sections, indent=2)
    )
    return wrap_untrusted_text("case_details", case_details) + "\n\nWrite the letter now."


def draft_appeal_letter(
    extracted_fields: dict,
    verdict_reason: str,
    requirement_checks: list[dict],
    verified_citations: list[dict],
    llm_client: LLMClient,
    prompt_version: str,
) -> LLMResponse:
    """Ask the model for a letter that uses placeholders instead of private details."""
    return llm_client.complete(
        "appeal_letter",
        load_prompt("appeal_letter", prompt_version),
        build_appeal_letter_prompt(
            extracted_fields, verdict_reason, requirement_checks, verified_citations
        ),
        max_output_tokens=1200,
    )


def fill_placeholders(text: str, pii_values: dict[str, list[str]]) -> str:
    """Put the real details back in, for display on the reviewer's screen only.

    The filled version is never stored or logged; it is built when the page asks for it.
    Placeholders without a known value (e.g. [PROVIDER_NAME]) are left for a human to fill.
    """

    def replacement_for(match: re.Match) -> str:
        placeholder = match.group(0)
        original_values = pii_values.get(placeholder)
        if original_values:
            return original_values[0]
        return placeholder

    return PLACEHOLDER_PATTERN.sub(replacement_for, text)
