"""The shape the language model's extraction answer must have.

Pydantic checks the model's JSON against these classes. Anything missing, of
the wrong type or out of range is rejected before it can reach the rest of
the system.
"""

import re

from pydantic import BaseModel, Field, field_validator

CPT_CODE_PATTERN = re.compile(r"^\d{5}$")
# Letter, two digits, optional dot and up to four more characters, e.g. M54.16 or S32.009A.
ICD10_CODE_PATTERN = re.compile(r"^[A-Z]\d{2}(\.[A-Z0-9]{1,4})?$")


class SourcedText(BaseModel):
    """A text value and the sentence it came from."""

    value: str | None
    source_sentence: str | None = None


class SourcedNumber(BaseModel):
    """A number and the sentence it came from."""

    value: float | None = Field(default=None, ge=0, le=1000)
    source_sentence: str | None = None


class SourcedBoolean(BaseModel):
    """A yes/no value and the sentence it came from."""

    value: bool | None
    source_sentence: str | None = None


class SourcedTextList(BaseModel):
    """A list of values and the sentence they came from."""

    value: list[str] = Field(default_factory=list)
    source_sentence: str | None = None


class ExtractedCaseFields(BaseModel):
    """All facts ClaimGuard needs from one request."""

    patient_age: SourcedNumber
    procedure_code: SourcedText
    diagnosis_codes: SourcedTextList
    symptom_duration_weeks: SourcedNumber
    physical_therapy_weeks: SourcedNumber
    other_conservative_treatments: SourcedTextList
    red_flags: SourcedTextList
    neurological_exam_documented: SourcedBoolean
    prior_lumbar_mri_within_12_months: SourcedBoolean
    requesting_specialty: SourcedText
    clinical_summary: str = Field(max_length=800)

    @field_validator("procedure_code")
    @classmethod
    def check_procedure_code(cls, procedure_code: SourcedText) -> SourcedText:
        """CPT codes are exactly five digits."""
        if procedure_code.value is not None and not CPT_CODE_PATTERN.match(procedure_code.value):
            raise ValueError(f"'{procedure_code.value}' is not a 5-digit CPT code")
        return procedure_code

    @field_validator("diagnosis_codes")
    @classmethod
    def check_diagnosis_codes(cls, diagnosis_codes: SourcedTextList) -> SourcedTextList:
        """Every code must look like an ICD-10 code."""
        for code in diagnosis_codes.value:
            if not ICD10_CODE_PATTERN.match(code):
                raise ValueError(f"'{code}' is not a valid ICD-10 code")
        return diagnosis_codes

    def sourced_fields(self) -> dict[str, BaseModel]:
        """Every field that carries a source sentence, by name."""
        fields = {}
        for field_name in type(self).model_fields:
            field_value = getattr(self, field_name)
            if hasattr(field_value, "source_sentence"):
                fields[field_name] = field_value
        return fields
