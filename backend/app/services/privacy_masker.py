"""Hide private patient details before any text reaches the language model.

Masking runs in two layers:

1. Labelled fields. Request forms label private details ("Patient Name:",
   "Member ID:" ...). We read those values and replace every occurrence in the
   document, including just the surname used later in the notes ("Testcase
   reports..."), which a statistical model can easily miss.
2. Presidio. Catches anything the form labels did not cover, for example a
   name or phone number written inside the clinical notes.

The result keeps a map of placeholder -> original values so the final appeal
letter can be filled back in on screen. That map is stored in the database only.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.core.config import get_settings

PATIENT_NAME = "[PATIENT_NAME]"
MEMBER_ID = "[MEMBER_ID]"
DATE_OF_BIRTH = "[DATE_OF_BIRTH]"
PHONE = "[PHONE]"
ADDRESS = "[ADDRESS]"
PERSON = "[PERSON]"
EMAIL = "[EMAIL]"
SSN = "[SSN]"

# Form labels we trust to mark private values, and the placeholder for each.
LABELLED_FIELD_PLACEHOLDERS = {
    "patient name": PATIENT_NAME,
    "patient": PATIENT_NAME,
    "member name": PATIENT_NAME,
    "member id": MEMBER_ID,
    "member number": MEMBER_ID,
    "subscriber id": MEMBER_ID,
    "date of birth": DATE_OF_BIRTH,
    "dob": DATE_OF_BIRTH,
    "phone": PHONE,
    "telephone": PHONE,
    "address": ADDRESS,
}

LABELLED_FIELD_PATTERN = re.compile(
    r"^\s*(?P<label>patient name|patient|member name|member id|member number|subscriber id|"
    r"date of birth|dob|phone|telephone|address)\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Presidio entity type -> our placeholder.
PRESIDIO_ENTITY_PLACEHOLDERS = {
    "PERSON": PERSON,
    "PHONE_NUMBER": PHONE,
    "US_PHONE": PHONE,
    "EMAIL_ADDRESS": EMAIL,
    "US_SSN": SSN,
    "LOCATION": ADDRESS,
    "MEMBER_ID": MEMBER_ID,
    "DATE_OF_BIRTH": DATE_OF_BIRTH,
}

# Below this confidence Presidio's guesses are mostly noise.
PRESIDIO_SCORE_THRESHOLD = 0.5

# Words that look like names to spaCy in clinical text but are not people.
NOT_A_PERSON = {"straight leg raise", "ibuprofen", "prednisone", "mri", "sciatica"}

PLACEHOLDER_PATTERN = re.compile(r"\[[A-Z_]+\]")


@dataclass
class MaskingResult:
    """Masked text plus the original values behind each placeholder."""

    masked_text: str
    pii_values: dict[str, list[str]] = field(default_factory=dict)

    def all_original_values(self) -> list[str]:
        """Every private value that was removed (useful for tests)."""
        values = []
        for original_values in self.pii_values.values():
            values.extend(original_values)
        return values


def build_member_id_recognizer() -> PatternRecognizer:
    """Member ids in our synthetic documents look like FAKE-MBR-123456."""
    return PatternRecognizer(
        supported_entity="MEMBER_ID",
        patterns=[Pattern(name="synthetic member id", regex=r"\bFAKE-MBR-\d{6}\b", score=0.95)],
    )


def build_phone_recognizer() -> PatternRecognizer:
    """US-style phone numbers with separators, e.g. (312) 555-0147.

    Presidio's built-in phone recognizer validates numbers and rejects the
    555-01xx range reserved for fiction, so we add a simple pattern.
    """
    return PatternRecognizer(
        supported_entity="US_PHONE",
        patterns=[
            Pattern(
                name="us phone with separators",
                regex=r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b",
                score=0.7,
            )
        ],
    )


def build_date_of_birth_recognizer() -> PatternRecognizer:
    """Dates count as private only when words like "born" or "DOB" are nearby.

    A low base score plus context words means other dates (for example the
    date of a previous MRI) stay readable for the model.
    """
    return PatternRecognizer(
        supported_entity="DATE_OF_BIRTH",
        patterns=[
            Pattern(name="iso date", regex=r"\b\d{4}-\d{2}-\d{2}\b", score=0.2),
            Pattern(name="us date", regex=r"\b\d{1,2}/\d{1,2}/\d{4}\b", score=0.2),
        ],
        context=["born", "birth", "dob", "birthday"],
    )


@lru_cache
def get_analyzer() -> AnalyzerEngine:
    """Create the Presidio analyzer once; loading the spaCy model takes a few seconds."""
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": get_settings().spacy_model_name}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    analyzer.registry.add_recognizer(build_member_id_recognizer())
    analyzer.registry.add_recognizer(build_phone_recognizer())
    analyzer.registry.add_recognizer(build_date_of_birth_recognizer())
    return analyzer


def remember_value(pii_values: dict[str, list[str]], placeholder: str, value: str) -> None:
    """Add a value under its placeholder, without duplicates."""
    if placeholder not in pii_values:
        pii_values[placeholder] = []
    if value not in pii_values[placeholder]:
        pii_values[placeholder].append(value)


def find_labelled_values(text: str) -> dict[str, list[str]]:
    """Read private values from labelled form fields like "Member ID: FAKE-MBR-123456"."""
    pii_values: dict[str, list[str]] = {}
    for match in LABELLED_FIELD_PATTERN.finditer(text):
        label = match.group("label").lower()
        value = match.group("value").strip()
        placeholder = LABELLED_FIELD_PLACEHOLDERS[label]
        remember_value(pii_values, placeholder, value)

        if placeholder == PATIENT_NAME:
            # Notes often refer to the patient by surname or first name only.
            for name_part in value.split():
                cleaned_part = name_part.strip(".,")
                if len(cleaned_part) >= 3:
                    remember_value(pii_values, PATIENT_NAME, cleaned_part)
    return pii_values


def replace_known_values(text: str, pii_values: dict[str, list[str]]) -> str:
    """Replace every occurrence of each known value with its placeholder."""
    replacements = []
    for placeholder, values in pii_values.items():
        for value in values:
            replacements.append((value, placeholder))

    # Longest first, so "Jordan Testcase" is replaced before "Jordan".
    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)

    masked_text = text
    for value, placeholder in replacements:
        value_pattern = re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)", re.IGNORECASE)
        masked_text = value_pattern.sub(placeholder, masked_text)
    return masked_text


def mask_with_presidio(text: str, pii_values: dict[str, list[str]]) -> str:
    """Find remaining private details with Presidio and replace them."""
    analyzer = get_analyzer()
    findings = analyzer.analyze(
        text=text,
        language="en",
        entities=list(PRESIDIO_ENTITY_PLACEHOLDERS.keys()),
        score_threshold=PRESIDIO_SCORE_THRESHOLD,
    )

    existing_placeholder_spans = find_placeholder_spans(text)

    # Replace from the end of the text backwards so earlier positions stay valid.
    findings.sort(key=lambda finding: finding.start, reverse=True)
    masked_text = text
    last_replaced_start = len(text) + 1
    for finding in findings:
        if finding.end > last_replaced_start:
            continue  # overlaps a finding we already replaced
        if overlaps_any_span(finding.start, finding.end, existing_placeholder_spans):
            continue  # spaCy sometimes reads "DATE_OF_BIRTH" inside a placeholder as a name
        finding_end = cut_at_line_break(text, finding.start, finding.end)
        original_value = text[finding.start : finding_end]
        if is_false_positive(original_value):
            continue
        placeholder = PRESIDIO_ENTITY_PLACEHOLDERS[finding.entity_type]
        remember_value(pii_values, placeholder, original_value)
        masked_text = masked_text[: finding.start] + placeholder + masked_text[finding_end:]
        last_replaced_start = finding.start
    return masked_text


def cut_at_line_break(text: str, start: int, end: int) -> int:
    """Shorten a finding that runs onto the next line.

    spaCy sometimes joins a name with the label on the next line
    ("Riley Fictionson\\nSpecialty"); masking the label would hide useful data.
    """
    line_break_position = text.find("\n", start, end)
    if line_break_position == -1:
        return end
    return line_break_position


def find_placeholder_spans(text: str) -> list[tuple[int, int]]:
    """Start and end positions of placeholders already in the text."""
    spans = []
    for match in PLACEHOLDER_PATTERN.finditer(text):
        spans.append((match.start(), match.end()))
    return spans


def overlaps_any_span(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """True if the range start..end touches any of the spans."""
    for span_start, span_end in spans:
        if start < span_end and end > span_start:
            return True
    return False


def is_false_positive(value: str) -> bool:
    """Skip known clinical words that spaCy sometimes mistakes for names."""
    return value.strip().lower() in NOT_A_PERSON


def mask_private_information(text: str) -> MaskingResult:
    """Return the text with private details replaced by placeholders."""
    pii_values = find_labelled_values(text)
    partly_masked_text = replace_known_values(text, pii_values)
    fully_masked_text = mask_with_presidio(partly_masked_text, pii_values)
    return MaskingResult(masked_text=fully_masked_text, pii_values=pii_values)
