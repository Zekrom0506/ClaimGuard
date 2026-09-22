"""Ask the language model for the request's facts as JSON, and validate them.

This is "structured output": instead of free text we ask for a fixed JSON
shape, then check it with Pydantic. The model can still return broken JSON or
a wrong value (for example a 4-digit CPT code), so we never trust it blindly:
invalid answers get one retry with the error message, and if that also fails
the case is sent to a human.
"""

import json
import logging
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.core.llm_client import LLMClient, LLMResponse
from app.schemas.extraction import ExtractedCaseFields
from app.services.prompt_loader import load_prompt
from app.services.prompt_safety import wrap_untrusted_text
from app.services.text_matching import text_contains_quote

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class InvalidModelOutput(Exception):
    """The model's answer was not valid JSON or did not match the schema."""


@dataclass
class ExtractionOutcome:
    """What happened when we asked for the case fields."""

    fields: ExtractedCaseFields | None
    attempts: int
    last_error: str | None = None
    unverified_source_fields: list[str] = field(default_factory=list)
    responses: list[LLMResponse] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """True when valid fields were extracted."""
        return self.fields is not None


def parse_json_object(model_text: str) -> dict:
    """Pull the JSON object out of the model's answer.

    Models sometimes wrap JSON in ```json fences or add a sentence before it,
    so we take the text from the first "{" to the last "}".
    """
    first_brace = model_text.find("{")
    last_brace = model_text.rfind("}")
    if first_brace == -1 or last_brace <= first_brace:
        raise InvalidModelOutput("The answer did not contain a JSON object.")
    try:
        parsed = json.loads(model_text[first_brace : last_brace + 1])
    except json.JSONDecodeError as error:
        raise InvalidModelOutput(f"The JSON could not be parsed: {error}") from error
    if not isinstance(parsed, dict):
        raise InvalidModelOutput("The JSON was not an object.")
    return parsed


def build_extraction_user_prompt(masked_text: str) -> str:
    """The user message: the masked document inside data tags."""
    return (
        wrap_untrusted_text("request_document", masked_text)
        + "\n\nReturn the JSON object for this request now."
    )


def build_retry_prompt(original_prompt: str, error_message: str) -> str:
    """Repeat the request and tell the model exactly what was wrong last time."""
    return (
        original_prompt
        + "\n\nYour previous answer was rejected for this reason:\n"
        + error_message
        + "\nReturn a corrected JSON object only."
    )


def validate_extraction(model_text: str) -> ExtractedCaseFields:
    """Parse and validate one answer, raising InvalidModelOutput if it is not acceptable."""
    parsed_json = parse_json_object(model_text)
    try:
        return ExtractedCaseFields.model_validate(parsed_json)
    except ValidationError as error:
        raise InvalidModelOutput(str(error)) from error


def find_unverified_sources(fields: ExtractedCaseFields, masked_text: str) -> list[str]:
    """Names of fields whose source sentence does not actually appear in the document."""
    unverified_field_names = []
    for field_name, sourced_field in fields.sourced_fields().items():
        source_sentence = sourced_field.source_sentence
        if source_sentence is None:
            continue
        if not text_contains_quote(masked_text, source_sentence):
            unverified_field_names.append(field_name)
    return unverified_field_names


def extract_case_fields(
    masked_text: str,
    llm_client: LLMClient,
    prompt_version: str,
) -> ExtractionOutcome:
    """Ask the model for the case fields, retrying once if the answer is invalid."""
    system_prompt = load_prompt("extraction", prompt_version)
    first_prompt = build_extraction_user_prompt(masked_text)
    user_prompt = first_prompt

    outcome = ExtractionOutcome(fields=None, attempts=0)
    while outcome.attempts < MAX_ATTEMPTS:
        outcome.attempts += 1
        response = llm_client.complete("extraction", system_prompt, user_prompt)
        outcome.responses.append(response)
        try:
            outcome.fields = validate_extraction(response.text)
        except InvalidModelOutput as error:
            outcome.last_error = str(error)
            logger.warning("Extraction attempt %d was invalid", outcome.attempts)
            user_prompt = build_retry_prompt(first_prompt, outcome.last_error)
            continue

        outcome.last_error = None
        outcome.unverified_source_fields = find_unverified_sources(outcome.fields, masked_text)
        return outcome

    return outcome
