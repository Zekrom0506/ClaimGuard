"""Tests for loading the risk model, predicting and explaining with SHAP."""

import json

import joblib
import pytest

from app.services.case_processor import models_disagree
from app.services.risk_model import DenialRiskModel, features_from_extraction, reason_sentence
from tests.fakes import load_recorded_response, train_small_risk_model


def fields_from(file_name: str) -> dict:
    return json.loads(load_recorded_response(file_name))


@pytest.mark.parametrize("model_type", ["xgboost", "logistic_regression"])
def test_case_meeting_policy_is_low_risk_and_case_without_therapy_is_high(model_type: str) -> None:
    risk_model = train_small_risk_model(model_type)
    approved_case = risk_model.predict(fields_from("extraction_eval_001.json"))
    no_therapy_case = risk_model.predict(fields_from("extraction_eval_033.json"))
    assert approved_case.denial_probability < 0.5
    assert no_therapy_case.denial_probability > 0.5


@pytest.mark.parametrize("model_type", ["xgboost", "logistic_regression"])
def test_prediction_has_three_plain_english_reasons(model_type: str) -> None:
    prediction = train_small_risk_model(model_type).predict(fields_from("extraction_eval_033.json"))
    assert len(prediction.top_reasons) == 3
    for reason in prediction.top_reasons:
        assert reason.endswith("the denial risk.")
    assert "Physical therapy shorter than 6 weeks (0 weeks) increased the denial risk." in (
        prediction.top_reasons
    )


def test_missing_therapy_length_can_be_scored() -> None:
    extracted_fields = fields_from("extraction_eval_001.json")
    extracted_fields["physical_therapy_weeks"]["value"] = None
    prediction = train_small_risk_model().predict(extracted_fields)
    assert 0.0 <= prediction.denial_probability <= 1.0


def test_features_are_mapped_from_extraction() -> None:
    features = features_from_extraction(fields_from("extraction_eval_001.json"))
    assert features["primary_diagnosis_code"] == "M54.16"
    assert features["red_flag_present"] == 0
    assert features["neurological_exam_documented"] == 1


def test_one_hot_columns_map_back_to_their_feature() -> None:
    risk_model = train_small_risk_model()
    assert (
        risk_model.original_feature_for("categorical__requesting_specialty_Neurology")
        == "requesting_specialty"
    )
    assert (
        risk_model.original_feature_for("numeric__missingindicator_physical_therapy_weeks")
        == "physical_therapy_weeks"
    )


def test_reason_wording() -> None:
    assert reason_sentence("red_flag_present", 1, -0.8) == (
        "A documented red flag lowered the denial risk."
    )


def test_load_returns_none_when_file_is_missing(tmp_path) -> None:
    assert DenialRiskModel.load(tmp_path / "missing.joblib") is None


def test_load_from_saved_file(tmp_path) -> None:
    risk_model = train_small_risk_model()
    model_path = tmp_path / "model.joblib"
    joblib.dump(
        {
            "pipeline": risk_model.pipeline,
            "model_type": "xgboost",
            "numeric_features": risk_model.numeric_features,
            "binary_features": [
                "red_flag_present",
                "prior_lumbar_mri_within_12_months",
                "neurological_exam_documented",
            ],
            "categorical_features": ["primary_diagnosis_code", "requesting_specialty"],
            "background_sample": None,
        },
        model_path,
    )
    loaded_model = DenialRiskModel.load(model_path)
    assert loaded_model.model_type == "xgboost"
    assert loaded_model.predict(fields_from("extraction_eval_001.json")).denial_probability < 0.5


@pytest.mark.parametrize(
    ("verdict", "denial_probability", "expected"),
    [
        ("likely_approved", 0.9, True),
        ("likely_approved", 0.1, False),
        ("likely_denied", 0.1, True),
        ("likely_denied", 0.9, False),
        ("missing_information", 0.9, False),
        (None, 0.9, False),
    ],
)
def test_disagreement_rule(verdict, denial_probability, expected) -> None:
    assert models_disagree(verdict, denial_probability, threshold=0.5) is expected
