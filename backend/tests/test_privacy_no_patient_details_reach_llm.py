"""PRIVACY TEST: no patient name, member id or phone number may reach the language model.

Runs the real reading and masking steps on all 40 synthetic evaluation
documents, sends the result through the pipeline with a fake model that
records every prompt, and checks that none of the fake identity values appear
in anything the model received.
"""

import json
import re

import pytest

from app.core.config import get_settings
from app.models.case import PriorAuthCase
from app.services.case_processor import extract_fields, read_and_mask
from tests.fakes import default_recorded_responses, make_fake_pipeline

LABELS_FILE = get_settings().project_root / "data" / "evaluation" / "labels.json"


def load_labelled_cases() -> list[dict]:
    """All 40 evaluation cases with their fake identities."""
    return json.loads(LABELS_FILE.read_text())["cases"]


def everything_sent_to_model(labelled_case: dict) -> str:
    """Run the pipeline steps for one case and return all prompt text the model saw."""
    pipeline = make_fake_pipeline(default_recorded_responses())
    case = PriorAuthCase(original_filename="test.pdf")
    pdf_bytes = (LABELS_FILE.parent / labelled_case["file"]).read_bytes()

    read_and_mask(case, pdf_bytes)
    extract_fields(case, pipeline)

    sent_text_parts = []
    for sent_prompt in pipeline.llm_client.sent_prompts:
        sent_text_parts.append(sent_prompt.system_prompt)
        sent_text_parts.append(sent_prompt.user_prompt)
    return "\n".join(sent_text_parts).lower()


def contains_whole_value(text: str, value: str) -> bool:
    """True if value appears as a whole word or phrase.

    Whole-word matching matters: one fake surname is "Placeholder", and the
    prompt's own instructions mention "placeholders".
    """
    pattern = r"(?<!\w)" + re.escape(value.lower()) + r"(?!\w)"
    return re.search(pattern, text) is not None


@pytest.mark.parametrize("labelled_case", load_labelled_cases(), ids=lambda case: case["case_id"])
def test_privacy_no_identity_value_reaches_the_model(labelled_case: dict) -> None:
    sent_text = everything_sent_to_model(labelled_case)
    assert sent_text != ""

    for field_name, private_value in labelled_case["synthetic_identity"].items():
        assert not contains_whole_value(sent_text, private_value), f"{field_name} reached the model"
