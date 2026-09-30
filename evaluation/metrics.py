"""Scoring functions for the evaluation. Pure functions: no database, no model calls."""

NUMBER_TOLERANCE_WEEKS = 1.0

EXTRACTION_FIELDS_TO_SCORE = [
    "patient_age",
    "procedure_code",
    "diagnosis_codes",
    "symptom_duration_weeks",
    "physical_therapy_weeks",
    "red_flags_present",
    "prior_lumbar_mri_within_12_months",
    "neurological_exam_documented",
    "requesting_specialty",
]


def accuracy(expected_values: list, predicted_values: list) -> float | None:
    """Share of positions where the prediction equals the expected value (None if empty)."""
    if not expected_values:
        return None
    correct_count = 0
    for expected, predicted in zip(expected_values, predicted_values, strict=True):
        if expected == predicted:
            correct_count += 1
    return round(correct_count / len(expected_values), 4)


def confusion_matrix(
    expected_labels: list[str], predicted_labels: list[str | None], label_names: list[str]
) -> dict[str, dict[str, int]]:
    """Counts of (expected -> predicted). A missing prediction is counted as "none"."""
    column_names = label_names + ["none"]
    matrix = {}
    for expected_name in label_names:
        matrix[expected_name] = {}
        for column_name in column_names:
            matrix[expected_name][column_name] = 0

    for expected, predicted in zip(expected_labels, predicted_labels, strict=True):
        predicted_column = predicted
        if predicted_column is None:
            predicted_column = "none"
        matrix[expected][predicted_column] += 1
    return matrix


def predicted_field_value(field_name: str, extracted_fields: dict) -> object:
    """Read the value to compare for one field from the model's extraction."""
    if field_name == "red_flags_present":
        return len(extracted_fields["red_flags"]["value"]) > 0
    return extracted_fields[field_name]["value"]


def field_is_correct(field_name: str, expected_value: object, predicted_value: object) -> bool:
    """Compare one field, allowing for harmless differences."""
    if expected_value is None or predicted_value is None:
        return expected_value is None and predicted_value is None

    if field_name in ("symptom_duration_weeks", "physical_therapy_weeks", "patient_age"):
        # "3 months" can fairly be 12 or 13 weeks.
        return abs(float(expected_value) - float(predicted_value)) <= NUMBER_TOLERANCE_WEEKS

    if field_name == "diagnosis_codes":
        expected_codes = set()
        for code in expected_value:
            expected_codes.add(code.upper())
        predicted_codes = set()
        for code in predicted_value:
            predicted_codes.add(code.upper())
        return expected_codes == predicted_codes

    if field_name == "requesting_specialty":
        return str(expected_value).lower() in str(predicted_value).lower()

    return expected_value == predicted_value


def extraction_accuracy_by_field(
    expected_fields_per_case: list[dict], extracted_fields_per_case: list[dict | None]
) -> dict[str, float | None]:
    """Accuracy for each field over all cases. A failed extraction counts as wrong."""
    accuracy_by_field = {}
    for field_name in EXTRACTION_FIELDS_TO_SCORE:
        correct_count = 0
        for expected_fields, extracted_fields in zip(
            expected_fields_per_case, extracted_fields_per_case, strict=True
        ):
            if extracted_fields is None:
                continue
            predicted_value = predicted_field_value(field_name, extracted_fields)
            if field_is_correct(field_name, expected_fields[field_name], predicted_value):
                correct_count += 1
        total = len(expected_fields_per_case)
        accuracy_by_field[field_name] = round(correct_count / total, 4) if total else None
    return accuracy_by_field


def section_matches(section_title: str | None, expected_section: str) -> bool:
    """True if a chunk's section title is the expected section (e.g. "2.2 ..." for "2.2")."""
    if section_title is None:
        return False
    first_word = section_title.strip().split(" ")[0].rstrip(".")
    if first_word.lower() == "section":
        first_word = section_title.strip().split(" ")[1].rstrip(".")
    return first_word == expected_section


def citation_section_accuracy(
    expected_sections: list[str], verified_citations_per_case: list[list[dict]]
) -> float | None:
    """Share of cases where at least one verified citation is from the correct section."""
    if not expected_sections:
        return None
    correct_count = 0
    for expected_section, citations in zip(
        expected_sections, verified_citations_per_case, strict=True
    ):
        for citation in citations:
            if section_matches(citation.get("section_title"), expected_section):
                correct_count += 1
                break
    return round(correct_count / len(expected_sections), 4)


def hallucination_rate(total_citations: int, failed_citations: int) -> float | None:
    """Share of all citations that failed the code check."""
    if total_citations == 0:
        return None
    return round(failed_citations / total_citations, 4)


def recall_at_k(
    expected_sections: list[str], retrieved_sections_per_case: list[list[str]]
) -> float:
    """Share of cases whose correct section appears anywhere in the retrieved chunks."""
    found_count = 0
    for expected_section, retrieved_sections in zip(
        expected_sections, retrieved_sections_per_case, strict=True
    ):
        for section_title in retrieved_sections:
            if section_matches(section_title, expected_section):
                found_count += 1
                break
    return round(found_count / len(expected_sections), 4)


def mean_reciprocal_rank(
    expected_sections: list[str], retrieved_sections_per_case: list[list[str]]
) -> float:
    """Average of 1/position of the first correct chunk (0 if it was not retrieved).

    Recall only asks "was it found?"; MRR also rewards finding it near the top.
    """
    reciprocal_ranks_total = 0.0
    for expected_section, retrieved_sections in zip(
        expected_sections, retrieved_sections_per_case, strict=True
    ):
        for position, section_title in enumerate(retrieved_sections):
            if section_matches(section_title, expected_section):
                reciprocal_ranks_total += 1.0 / (position + 1)
                break
    return round(reciprocal_ranks_total / len(expected_sections), 4)


def average(values: list[float]) -> float | None:
    """Mean of a list, or None if it is empty."""
    if not values:
        return None
    return round(sum(values) / len(values), 4)
