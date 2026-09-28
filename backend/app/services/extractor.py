"""Ask the language model for the request's facts as validated JSON."""

from dataclasses import dataclass, field

from app.core.llm_client import LLMClient, LLMResponse
from app.schemas.extraction import ExtractedCaseFields
from app.services.prompt_loader import load_prompt
from app.services.prompt_safety import wrap_untrusted_text
from app.services.structured_output import request_structured_answer
from app.services.text_matching import text_contains_quote


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


def build_extraction_user_prompt(masked_text: str) -> str:
    """The user message: the masked document inside data tags."""
    return (
        wrap_untrusted_text("request_document", masked_text)
        + "\n\nReturn the JSON object for this request now."
    )


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
    answer = request_structured_answer(
        llm_client,
        task_name="extraction",
        system_prompt=load_prompt("extraction", prompt_version),
        user_prompt=build_extraction_user_prompt(masked_text),
        schema=ExtractedCaseFields,
    )
    outcome = ExtractionOutcome(
        fields=answer.parsed,
        attempts=answer.attempts,
        last_error=answer.last_error,
        responses=answer.responses,
    )
    if outcome.fields is not None:
        outcome.unverified_source_fields = find_unverified_sources(outcome.fields, masked_text)
    return outcome
