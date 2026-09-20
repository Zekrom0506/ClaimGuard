"""Unit tests for the PII masker."""

from app.services.privacy_masker import (
    DATE_OF_BIRTH,
    MEMBER_ID,
    PATIENT_NAME,
    PHONE,
    find_labelled_values,
    mask_private_information,
)

SAMPLE_REQUEST = """Patient Name: Jordan Testcase
Member ID: FAKE-MBR-123456
Date of Birth: 1970-01-15
Phone: (312) 555-0147
Address: 12 Sample Street, Testville, ZZ 00000
CPT Code: 72148
Testcase reports back pain for 8 weeks. Previous MRI on 2026-02-01 was normal.
"""


def test_labelled_fields_are_found() -> None:
    pii_values = find_labelled_values(SAMPLE_REQUEST)
    assert pii_values[PATIENT_NAME][0] == "Jordan Testcase"
    assert pii_values[MEMBER_ID] == ["FAKE-MBR-123456"]
    assert pii_values[DATE_OF_BIRTH] == ["1970-01-15"]
    assert pii_values[PHONE] == ["(312) 555-0147"]


def test_patient_surname_in_notes_is_masked() -> None:
    result = mask_private_information(SAMPLE_REQUEST)
    assert "Testcase" not in result.masked_text
    assert "[PATIENT_NAME] reports back pain" in result.masked_text


def test_clinical_details_are_kept() -> None:
    result = mask_private_information(SAMPLE_REQUEST)
    assert "72148" in result.masked_text
    assert "8 weeks" in result.masked_text
    # Only the date of birth is private; other dates are clinical facts.
    assert "2026-02-01" in result.masked_text


def test_unlabelled_member_id_and_phone_in_notes_are_masked() -> None:
    text = "Call the member on (415) 555-0199 about FAKE-MBR-654321."
    result = mask_private_information(text)
    assert "555-0199" not in result.masked_text
    assert "FAKE-MBR-654321" not in result.masked_text
    assert "[PHONE]" in result.masked_text
    assert "[MEMBER_ID]" in result.masked_text


def test_unlabelled_person_name_is_masked() -> None:
    result = mask_private_information("The patient was referred by Margaret Thompson last week.")
    assert "Margaret Thompson" not in result.masked_text


def test_original_values_are_kept_for_filling_letters_back_in() -> None:
    result = mask_private_information(SAMPLE_REQUEST)
    assert "FAKE-MBR-123456" in result.all_original_values()


def test_placeholders_are_not_masked_again() -> None:
    result = mask_private_information(SAMPLE_REQUEST)
    assert "[[" not in result.masked_text
