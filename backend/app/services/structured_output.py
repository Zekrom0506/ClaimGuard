"""Ask the model for JSON of a known shape, validate it, and retry once if needed.

This is "structured output": instead of free text we ask for a fixed JSON
shape, then check it with Pydantic. The model can still return broken JSON or
a wrong value, so its answer is never trusted blindly. An invalid answer gets
one retry with the exact error message; if that also fails, the caller sends
the case to a human.
"""

import json
import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from app.core.llm_client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class InvalidModelOutput(Exception):
    """The model's answer was not valid JSON or did not match the schema."""


@dataclass
class StructuredAnswer:
    """The validated answer (or None) and how we got there."""

    parsed: BaseModel | None
    attempts: int = 0
    last_error: str | None = None
    responses: list[LLMResponse] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        """True when a valid answer was received."""
        return self.parsed is not None


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


def validate_answer(model_text: str, schema: type[BaseModel]) -> BaseModel:
    """Parse and validate one answer against a Pydantic schema."""
    parsed_json = parse_json_object(model_text)
    try:
        return schema.model_validate(parsed_json)
    except ValidationError as error:
        raise InvalidModelOutput(str(error)) from error


def build_retry_prompt(original_prompt: str, error_message: str) -> str:
    """Repeat the request and tell the model exactly what was wrong last time."""
    return (
        original_prompt
        + "\n\nYour previous answer was rejected for this reason:\n"
        + error_message
        + "\nReturn a corrected JSON object only."
    )


def request_structured_answer(
    llm_client: LLMClient,
    task_name: str,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    max_output_tokens: int = 2000,
) -> StructuredAnswer:
    """Call the model until it returns valid JSON for `schema`, at most twice."""
    answer = StructuredAnswer(parsed=None)
    current_prompt = user_prompt
    while answer.attempts < MAX_ATTEMPTS:
        answer.attempts += 1
        response = llm_client.complete(task_name, system_prompt, current_prompt, max_output_tokens)
        answer.responses.append(response)
        try:
            answer.parsed = validate_answer(response.text, schema)
            answer.last_error = None
            return answer
        except InvalidModelOutput as error:
            answer.last_error = str(error)
            logger.warning("%s attempt %d was invalid", task_name, answer.attempts)
            current_prompt = build_retry_prompt(user_prompt, answer.last_error)
    return answer
