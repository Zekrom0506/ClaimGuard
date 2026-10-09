"""Tests for the evaluation scoring functions."""

from evaluation.metrics import (
    accuracy,
    citation_section_accuracy,
    compare_llm_with_risk_model,
    confusion_matrix,
    extraction_accuracy_by_field,
    field_is_correct,
    hallucination_rate,
    mean_reciprocal_rank,
    recall_at_k,
    section_matches,
)


def test_accuracy_counts_exact_matches() -> None:
    assert accuracy(["a", "b", "c", "d"], ["a", "b", "x", None]) == 0.5


def test_confusion_matrix_counts_missing_prediction_as_none() -> None:
    matrix = confusion_matrix(["yes", "yes", "no"], ["yes", None, "yes"], ["yes", "no"])
    assert matrix["yes"] == {"yes": 1, "no": 0, "none": 1}
    assert matrix["no"]["yes"] == 1


def test_numbers_allow_one_week_difference() -> None:
    assert field_is_correct("symptom_duration_weeks", 12, 13)
    assert not field_is_correct("symptom_duration_weeks", 12, 14)


def test_none_only_matches_none() -> None:
    assert field_is_correct("physical_therapy_weeks", None, None)
    assert not field_is_correct("physical_therapy_weeks", None, 0)


def test_diagnosis_codes_ignore_order_and_case() -> None:
    assert field_is_correct("diagnosis_codes", ["M54.16", "M48.061"], ["m48.061", "M54.16"])


def test_extraction_accuracy_counts_failed_extraction_as_wrong() -> None:
    expected = {
        "patient_age": 50,
        "procedure_code": "72148",
        "diagnosis_codes": ["M54.16"],
        "symptom_duration_weeks": 8,
        "physical_therapy_weeks": 6,
        "red_flags_present": False,
        "prior_lumbar_mri_within_12_months": False,
        "neurological_exam_documented": True,
        "requesting_specialty": "Neurology",
    }
    extracted = {}
    for field_name, value in expected.items():
        extracted[field_name] = {"value": value}
    extracted["red_flags"] = {"value": []}

    accuracy_by_field = extraction_accuracy_by_field([expected, expected], [extracted, None])
    assert accuracy_by_field["procedure_code"] == 0.5
    assert accuracy_by_field["red_flags_present"] == 0.5


def test_section_matching() -> None:
    assert section_matches("2.2 Persistent Symptoms", "2.2")
    assert section_matches("Section 4 Documentation", "4")
    assert not section_matches("2.1 Red Flag Conditions", "2")
    assert not section_matches(None, "2")


def test_citation_section_accuracy_needs_one_correct_citation() -> None:
    citations_per_case = [
        [{"section_title": "6 Coding"}, {"section_title": "2.2 Persistent"}],
        [{"section_title": "6 Coding"}],
    ]
    assert citation_section_accuracy(["2.2", "3"], citations_per_case) == 0.5


def test_hallucination_rate() -> None:
    assert hallucination_rate(10, 1) == 0.1
    assert hallucination_rate(0, 0) is None


def test_recall_and_mrr() -> None:
    retrieved = [["1 Purpose", "2.2 Persistent"], ["6 Coding", "1 Purpose"]]
    assert recall_at_k(["2.2", "3"], retrieved) == 0.5
    # Case one finds it at position 2 (1/2), case two never (0): average 0.25.
    assert mean_reciprocal_rank(["2.2", "3"], retrieved) == 0.25


def test_llm_and_risk_model_comparison() -> None:
    comparison = compare_llm_with_risk_model(
        expected_verdicts=["likely_approved", "likely_denied", "likely_denied", "likely_approved"],
        predicted_verdicts=["likely_approved", "likely_approved", "likely_denied", None],
        denial_probabilities=[0.1, 0.9, 0.8, None],
        disagreement_flags=[False, True, False, False],
    )
    # Case 2 is a language model mistake that the disagreement flag caught.
    assert comparison["llm_mistakes"] == 2
    assert comparison["llm_mistakes_flagged_by_disagreement"] == 1
    assert comparison["risk_model_approved_vs_not_accuracy"] == 1.0
    assert comparison["llm_approved_vs_not_accuracy"] == round(2 / 3, 4)
    assert comparison["disagreement_rate"] == round(1 / 3, 4)
    assert comparison["llm_verdict_accuracy_when_models_agree"] == 1.0
