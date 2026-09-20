"""PRIVACY TEST: no patient name, member id or phone number may reach the language model.

Runs the masker on all 40 synthetic evaluation documents and checks that none
of the fake identity values survive in the text that would be sent onwards.
"""

import json

import pytest

from app.core.config import get_settings
from app.services.pdf_reader import read_pdf_text
from app.services.privacy_masker import mask_private_information

LABELS_FILE = get_settings().project_root / "data" / "evaluation" / "labels.json"


def load_labelled_cases() -> list[dict]:
    """All 40 evaluation cases with their fake identities."""
    return json.loads(LABELS_FILE.read_text())["cases"]


@pytest.mark.parametrize("labelled_case", load_labelled_cases(), ids=lambda case: case["case_id"])
def test_privacy_masked_text_contains_no_identity_values(labelled_case: dict) -> None:
    pdf_path = LABELS_FILE.parent / labelled_case["file"]
    original_text = read_pdf_text(pdf_path.read_bytes())
    masked_text = mask_private_information(original_text).masked_text.lower()

    for field_name, private_value in labelled_case["synthetic_identity"].items():
        assert private_value.lower() not in masked_text, f"{field_name} leaked"
