"""Generate SYNTHETIC structured records for training the denial-risk model.

IMPORTANT LIMITATION: labels come from the same rules as the sample policy,
plus random noise. A model trained on this data mostly learns those rules
back; its scores say nothing about how real insurers decide. At a real company
the training data would be historical prior-authorization requests joined to
the insurer's actual decisions (approved, denied, returned for information).

These records are created from scratch with their own seed. The 40 labelled
evaluation cases are never used here.

Usage: python ml/generate_training_data.py
"""

import csv
import random
from pathlib import Path

OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "training_records.csv"
RECORD_COUNT = 5000
RANDOM_SEED = 7
# Share of records whose label is flipped: real decisions are not perfectly consistent.
LABEL_NOISE_RATE = 0.10

SPECIALTIES = [
    "Primary Care",
    "Orthopedic Surgery",
    "Neurosurgery",
    "Physical Medicine and Rehabilitation",
    "Neurology",
    "Chiropractic",
]
DIAGNOSES_WITHOUT_RED_FLAG = ["M54.50", "M54.16", "M54.17", "M51.26", "M48.061", "M48.062"]
DIAGNOSES_WITH_RED_FLAG = ["G83.4", "C79.51", "S32.009A", "M54.17"]

COLUMNS = [
    "record_id",
    "age",
    "primary_diagnosis_code",
    "symptom_duration_weeks",
    "physical_therapy_weeks",
    "red_flag_present",
    "prior_lumbar_mri_within_12_months",
    "neurological_exam_documented",
    "requesting_specialty",
    "denied",
]


def make_clinical_profile(random_generator: random.Random) -> dict:
    """Pick one kind of request, roughly in a realistic mix, and fill in its facts."""
    record = {
        "age": random_generator.randint(18, 90),
        "requesting_specialty": random_generator.choice(SPECIALTIES),
        "red_flag_present": 0,
        "prior_lumbar_mri_within_12_months": 0,
        "neurological_exam_documented": 1,
        "primary_diagnosis_code": random_generator.choice(DIAGNOSES_WITHOUT_RED_FLAG),
    }
    profile_roll = random_generator.random()

    if profile_roll < 0.35:  # persistent symptoms after conservative care
        record["symptom_duration_weeks"] = random_generator.randint(6, 40)
        record["physical_therapy_weeks"] = random_generator.randint(6, 16)
    elif profile_roll < 0.47:  # red flag
        record["red_flag_present"] = 1
        record["primary_diagnosis_code"] = random_generator.choice(DIAGNOSES_WITH_RED_FLAG)
        record["symptom_duration_weeks"] = random_generator.randint(0, 6)
        record["physical_therapy_weeks"] = random_generator.choice([0, 0, 0, 2])
    elif profile_roll < 0.70:  # acute pain
        record["symptom_duration_weeks"] = random_generator.randint(0, 5)
        record["physical_therapy_weeks"] = random_generator.randint(0, 3)
    elif profile_roll < 0.82:  # long symptoms, little or no therapy
        record["symptom_duration_weeks"] = random_generator.randint(6, 40)
        record["physical_therapy_weeks"] = random_generator.randint(0, 5)
    elif profile_roll < 0.90:  # repeat imaging
        record["symptom_duration_weeks"] = random_generator.randint(8, 52)
        record["physical_therapy_weeks"] = random_generator.randint(6, 12)
        record["prior_lumbar_mri_within_12_months"] = 1
    else:  # incomplete request
        record["symptom_duration_weeks"] = random_generator.randint(6, 20)
        record["physical_therapy_weeks"] = random_generator.randint(6, 12)
        record["neurological_exam_documented"] = random_generator.choice([0, 1])
        if random_generator.random() < 0.5:
            record["symptom_duration_weeks"] = ""
        if random_generator.random() < 0.5:
            record["physical_therapy_weeks"] = ""
    return record


def is_missing(value: object) -> bool:
    """Empty cells stand for 'not documented'."""
    return value == ""


def decide_by_policy(record: dict) -> int:
    """1 = denied, 0 = approved, following the sample policy's rules."""
    if record["red_flag_present"] == 1:
        return 0
    if is_missing(record["symptom_duration_weeks"]) or is_missing(record["physical_therapy_weeks"]):
        return 1  # incomplete requests are returned, which counts as not approved
    if record["neurological_exam_documented"] == 0:
        return 1
    if record["prior_lumbar_mri_within_12_months"] == 1:
        return 1
    if record["symptom_duration_weeks"] >= 6 and record["physical_therapy_weeks"] >= 6:
        return 0
    return 1


def main() -> None:
    """Write RECORD_COUNT records to ml/data/training_records.csv."""
    random_generator = random.Random(RANDOM_SEED)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    flipped_count = 0
    denied_count = 0
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=COLUMNS)
        writer.writeheader()
        for record_number in range(1, RECORD_COUNT + 1):
            record = make_clinical_profile(random_generator)
            record["record_id"] = f"TRAIN-{record_number:05d}"
            denied = decide_by_policy(record)
            if random_generator.random() < LABEL_NOISE_RATE:
                denied = 1 - denied
                flipped_count += 1
            record["denied"] = denied
            denied_count += denied
            writer.writerow(record)

    print(f"Wrote {RECORD_COUNT} SYNTHETIC records to {OUTPUT_FILE}")
    denied_share = denied_count / RECORD_COUNT
    print(f"Denied: {denied_count} ({denied_share:.0%}), labels flipped: {flipped_count}")


if __name__ == "__main__":
    main()
