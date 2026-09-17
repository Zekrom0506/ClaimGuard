"""Generate the 40 labelled SYNTHETIC evaluation cases and data/evaluation/labels.json.

The mix is fixed (not random) so the evaluation always covers every scenario.
These cases must never be used to train the risk model: they live in their own
folder, use the EVAL- prefix and a different random seed from ml/.

Usage: python scripts/generate_evaluation_set.py
"""

import json
import random
from pathlib import Path

from synthetic_cases import (
    CaseSpecification,
    build_approved_after_conservative_care,
    build_approved_red_flag,
    build_denied_acute_pain,
    build_denied_no_conservative_care,
    build_denied_repeat_imaging,
    build_missing_neurological_exam,
    build_missing_symptom_duration,
    build_missing_therapy_duration,
    build_prompt_injection_case,
    write_case_pdf,
)

EVALUATION_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "evaluation"
CASES_DIRECTORY = EVALUATION_DIRECTORY / "cases"
LABELS_FILE = EVALUATION_DIRECTORY / "labels.json"
RANDOM_SEED = 40

RED_FLAG_ROTATION = [
    "cauda_equina",
    "progressive_deficit",
    "suspected_malignancy",
    "suspected_infection",
    "suspected_fracture",
    "cauda_equina",
]


def build_evaluation_cases() -> list[CaseSpecification]:
    """Build all 40 cases: 14 likely approved, 12 missing information, 14 likely denied."""
    random_generator = random.Random(RANDOM_SEED)
    cases: list[CaseSpecification] = []

    def next_id() -> str:
        return f"EVAL-{len(cases) + 1:03d}"

    for _ in range(8):
        cases.append(build_approved_after_conservative_care(next_id(), random_generator))
    for red_flag_key in RED_FLAG_ROTATION:
        cases.append(build_approved_red_flag(next_id(), random_generator, red_flag_key))
    for _ in range(5):
        cases.append(build_missing_therapy_duration(next_id(), random_generator))
    for _ in range(4):
        cases.append(build_missing_symptom_duration(next_id(), random_generator))
    for _ in range(3):
        cases.append(build_missing_neurological_exam(next_id(), random_generator))
    for _ in range(6):
        cases.append(build_denied_acute_pain(next_id(), random_generator))
    for _ in range(4):
        cases.append(build_denied_no_conservative_care(next_id(), random_generator))
    for _ in range(3):
        cases.append(build_denied_repeat_imaging(next_id(), random_generator))
    cases.append(build_prompt_injection_case(next_id(), random_generator))
    return cases


def expected_fields_for(case: CaseSpecification) -> dict:
    """The values a perfect extraction should return for this case."""
    if case.therapy_mentioned_without_duration:
        expected_therapy_weeks = None
    else:
        expected_therapy_weeks = case.physical_therapy_weeks

    return {
        "patient_age": case.identity.age_years,
        "procedure_code": case.procedure_code,
        "diagnosis_codes": case.diagnosis_codes,
        "symptom_duration_weeks": case.symptom_duration_weeks,
        "physical_therapy_weeks": expected_therapy_weeks,
        "red_flags_present": case.red_flag_key is not None,
        "prior_lumbar_mri_within_12_months": case.previous_mri_months_ago is not None,
        "neurological_exam_documented": case.neurological_exam_documented,
        "requesting_specialty": case.provider_specialty,
    }


def label_for(case: CaseSpecification) -> dict:
    """One entry of labels.json."""
    identity = case.identity
    return {
        "case_id": case.request_id,
        "file": f"cases/{case.request_id}.pdf",
        "scenario": case.scenario,
        "expected_verdict": case.expected_verdict,
        "expected_policy_section": case.expected_policy_section,
        "expected_fields": expected_fields_for(case),
        "explanation": case.label_explanation,
        # Kept so the evaluation can prove none of these reached the language model.
        "synthetic_identity": {
            "patient_name": identity.full_name,
            "last_name": identity.last_name,
            "member_id": identity.member_id,
            "date_of_birth": identity.date_of_birth.isoformat(),
            "phone": identity.phone,
            "address": identity.address,
        },
    }


def main() -> None:
    """Write the 40 PDFs and the labels file."""
    cases = build_evaluation_cases()
    labels = []
    for case in cases:
        write_case_pdf(case, CASES_DIRECTORY)
        labels.append(label_for(case))

    labels_document = {
        "description": "SYNTHETIC evaluation set. Correct answers follow data/policies/"
        "sample_lumbar_mri_policy.md. Never use these cases for model training.",
        "policy": "sample_lumbar_mri_policy",
        "cases": labels,
    }
    LABELS_FILE.write_text(json.dumps(labels_document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {CASES_DIRECTORY} and labels to {LABELS_FILE}")


if __name__ == "__main__":
    main()
