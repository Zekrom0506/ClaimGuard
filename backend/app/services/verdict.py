"""Ask the model for a verdict with proof, then check that proof in code."""

import json
from dataclasses import dataclass, field

from app.core.llm_client import LLMClient, LLMResponse
from app.schemas.verdict import VerdictAnswer
from app.services.citation_checker import CheckedCitation, check_citations
from app.services.prompt_loader import load_prompt
from app.services.prompt_safety import escape_attribute, wrap_untrusted_text
from app.services.retriever import RetrievedChunk
from app.services.structured_output import request_structured_answer

FLAG_CITATION_FAILED = "citation_failed"
FLAG_NO_VALID_CITATIONS = "no_valid_citations"
FLAG_INCONSISTENT_VERDICT = "verdict_inconsistent_with_requirements"
FLAG_VERDICT_INVALID = "verdict_invalid"


@dataclass
class VerdictOutcome:
    """The model's verdict after all code checks."""

    answer: VerdictAnswer | None
    verified_citations: list[CheckedCitation] = field(default_factory=list)
    failed_citations: list[CheckedCitation] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    responses: list[LLMResponse] = field(default_factory=list)


def facts_for_prompt(extracted_fields: dict) -> dict:
    """Just the extracted values (source sentences are for humans, not the verdict)."""
    facts = {}
    for field_name, field_value in extracted_fields.items():
        if isinstance(field_value, dict) and "value" in field_value:
            facts[field_name] = field_value["value"]
        else:
            facts[field_name] = field_value
    return facts


def format_policy_excerpt(chunk: RetrievedChunk) -> str:
    """One chunk inside a <policy_excerpt> tag that carries its id, section and page."""
    attributes = (
        f'id="{chunk.chunk_id}" policy="{escape_attribute(chunk.policy_name)}" '
        f'section="{escape_attribute(chunk.section_title)}" page="{chunk.page_number}"'
    )
    return wrap_untrusted_text("policy_excerpt", chunk.text, attributes)


def build_verdict_user_prompt(
    extracted_fields: dict, masked_text: str, retrieved_chunks: list[RetrievedChunk]
) -> str:
    """Case details and policy excerpts, each fenced off as data."""
    case_details = (
        "Extracted facts:\n"
        + json.dumps(facts_for_prompt(extracted_fields), indent=2)
        + "\n\nClinical notes from the request:\n"
        + masked_text
    )
    prompt_parts = [wrap_untrusted_text("case_details", case_details)]
    for chunk in retrieved_chunks:
        prompt_parts.append(format_policy_excerpt(chunk))
    prompt_parts.append("Return the JSON verdict now.")
    return "\n\n".join(prompt_parts)


def find_consistency_problems(answer: VerdictAnswer) -> list[str]:
    """Catch verdicts that contradict their own requirement list.

    Example: "likely_approved" while one requirement is "not_met". That can
    happen when an injected instruction pushes the model towards approval;
    a simple rule in code catches it whatever the model was told.
    """
    statuses = []
    for requirement in answer.requirements:
        statuses.append(requirement.status)

    if answer.verdict == "likely_approved" and "met" not in statuses:
        return [FLAG_INCONSISTENT_VERDICT]
    if answer.verdict == "likely_approved" and "not_met" in statuses:
        return [FLAG_INCONSISTENT_VERDICT]
    if answer.verdict == "likely_denied" and "not_met" not in statuses:
        return [FLAG_INCONSISTENT_VERDICT]
    return []


def generate_verdict(
    extracted_fields: dict,
    masked_text: str,
    retrieved_chunks: list[RetrievedChunk],
    llm_client: LLMClient,
    prompt_version: str,
) -> VerdictOutcome:
    """Get the verdict from the model and run every code check on it."""
    structured_answer = request_structured_answer(
        llm_client,
        task_name="verdict",
        system_prompt=load_prompt("verdict", prompt_version),
        user_prompt=build_verdict_user_prompt(extracted_fields, masked_text, retrieved_chunks),
        schema=VerdictAnswer,
    )
    outcome = VerdictOutcome(answer=structured_answer.parsed, responses=structured_answer.responses)
    if outcome.answer is None:
        outcome.flags.append(FLAG_VERDICT_INVALID)
        return outcome

    verified_citations, failed_citations = check_citations(
        outcome.answer.citations, retrieved_chunks
    )
    outcome.verified_citations = verified_citations
    outcome.failed_citations = failed_citations
    if failed_citations:
        outcome.flags.append(FLAG_CITATION_FAILED)
    if not verified_citations:
        outcome.flags.append(FLAG_NO_VALID_CITATIONS)
    outcome.flags.extend(find_consistency_problems(outcome.answer))
    return outcome
