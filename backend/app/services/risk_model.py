"""Serve the trained denial-risk model and explain each prediction with SHAP.

The model gives a second opinion next to the language model: it looks only at
structured facts (weeks of therapy, red flags, ...) and was trained on
(synthetic) past decisions. When the two disagree, a human should look closer.

SHAP splits one prediction into contributions from each feature: how much
"physical therapy = 2 weeks" pushed the risk up or down compared with an
average request. We turn the three biggest contributions into sentences.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy
import pandas
import shap

logger = logging.getLogger(__name__)

TOP_REASON_COUNT = 3
POLICY_MINIMUM_WEEKS = 6


@dataclass
class RiskPrediction:
    """The model's denial probability and its top reasons in plain English."""

    denial_probability: float
    top_reasons: list[str] = field(default_factory=list)
    model_type: str = ""


def features_from_extraction(extracted_fields: dict) -> dict:
    """Map the extracted case fields to the model's input columns."""
    diagnosis_codes = extracted_fields["diagnosis_codes"]["value"]
    primary_diagnosis_code = "unknown"
    if diagnosis_codes:
        primary_diagnosis_code = diagnosis_codes[0]

    def yes_no(field_name: str) -> int:
        """True -> 1; False or not stated -> 0."""
        return 1 if extracted_fields[field_name]["value"] else 0

    return {
        "age": extracted_fields["patient_age"]["value"],
        "symptom_duration_weeks": extracted_fields["symptom_duration_weeks"]["value"],
        "physical_therapy_weeks": extracted_fields["physical_therapy_weeks"]["value"],
        "red_flag_present": 1 if extracted_fields["red_flags"]["value"] else 0,
        "prior_lumbar_mri_within_12_months": yes_no("prior_lumbar_mri_within_12_months"),
        "neurological_exam_documented": yes_no("neurological_exam_documented"),
        "primary_diagnosis_code": primary_diagnosis_code,
        "requesting_specialty": extracted_fields["requesting_specialty"]["value"] or "unknown",
    }


def describe_weeks(label: str, weeks: float | None) -> str:
    """Wording for symptom or therapy duration, compared with the 6-week policy rule."""
    if weeks is None or numpy.isnan(weeks):
        return f"{label} not documented"
    if weeks < POLICY_MINIMUM_WEEKS:
        return f"{label} shorter than {POLICY_MINIMUM_WEEKS} weeks ({weeks:g} weeks)"
    return f"{label} of {weeks:g} weeks"


def describe_feature(feature_name: str, value: object) -> str:
    """A short phrase describing one feature's value."""
    if feature_name == "physical_therapy_weeks":
        return describe_weeks("Physical therapy", value)
    if feature_name == "symptom_duration_weeks":
        return describe_weeks("Symptoms", value)
    if feature_name == "red_flag_present":
        return "A documented red flag" if value == 1 else "No red flag symptoms"
    if feature_name == "prior_lumbar_mri_within_12_months":
        if value == 1:
            return "A lumbar MRI in the last 12 months"
        return "No recent lumbar MRI"
    if feature_name == "neurological_exam_documented":
        if value == 1:
            return "A documented neurological exam"
        return "No documented neurological exam"
    if feature_name == "age":
        return f"Age {value:g}" if value is not None else "Age not documented"
    if feature_name == "primary_diagnosis_code":
        return f"Diagnosis code {value}"
    if feature_name == "requesting_specialty":
        return f"Requesting specialty ({value})"
    return feature_name


def reason_sentence(feature_name: str, value: object, contribution: float) -> str:
    """'Physical therapy shorter than 6 weeks (2 weeks) increased the risk.'"""
    direction = "increased" if contribution > 0 else "lowered"
    return f"{describe_feature(feature_name, value)} {direction} the denial risk."


class DenialRiskModel:
    """A loaded model plus a SHAP explainer built once at startup."""

    def __init__(self, artifact: dict) -> None:
        self.pipeline = artifact["pipeline"]
        self.model_type = artifact["model_type"]
        self.numeric_features = artifact["numeric_features"]
        self.feature_names = (
            artifact["numeric_features"]
            + artifact["binary_features"]
            + artifact["categorical_features"]
        )
        self.preprocessor = self.pipeline.named_steps["preprocess"]
        self.estimator = self.pipeline.named_steps["model"]
        self.transformed_feature_names = list(self.preprocessor.get_feature_names_out())
        self.explainer = self._build_explainer(artifact["background_sample"])

    @classmethod
    def load(cls, model_path: Path) -> "DenialRiskModel | None":
        """Load the saved model, or return None (with a warning) if it is missing."""
        if not model_path.exists():
            logger.warning("Risk model not found at %s; risk scores are disabled", model_path)
            return None
        return cls(joblib.load(model_path))

    def _build_explainer(self, background_sample: pandas.DataFrame) -> shap.Explainer:
        """TreeExplainer for tree models, LinearExplainer for logistic regression."""
        if self.model_type == "xgboost":
            return shap.TreeExplainer(self.estimator)
        background_transformed = self.preprocessor.transform(background_sample)
        return shap.LinearExplainer(self.estimator, background_transformed)

    def original_feature_for(self, transformed_name: str) -> str:
        """Map a column after preprocessing back to the input it came from.

        One-hot encoding turns "requesting_specialty" into several columns
        ("categorical__requesting_specialty_Neurology", ...) and the imputer adds
        "numeric__missingindicator_physical_therapy_weeks". Their SHAP values
        are added back together so each input gets one total contribution.
        """
        name_without_step = transformed_name.split("__", 1)[1]
        name_without_step = name_without_step.removeprefix("missingindicator_")
        for feature_name in self.feature_names:
            if name_without_step == feature_name:
                return feature_name
            if name_without_step.startswith(feature_name + "_"):
                return feature_name
        return name_without_step

    def contributions_by_feature(self, transformed_row: numpy.ndarray) -> dict[str, float]:
        """SHAP value of each original feature for one row."""
        shap_values = numpy.asarray(self.explainer.shap_values(transformed_row))[0]
        totals: dict[str, float] = {}
        for column_index, transformed_name in enumerate(self.transformed_feature_names):
            feature_name = self.original_feature_for(transformed_name)
            totals[feature_name] = totals.get(feature_name, 0.0) + float(shap_values[column_index])
        return totals

    def predict(self, extracted_fields: dict) -> RiskPrediction:
        """Denial probability and top reasons for one case."""
        feature_values = features_from_extraction(extracted_fields)
        input_row = pandas.DataFrame([feature_values], columns=self.feature_names)
        # None (not documented) becomes NaN, which the model's imputer knows how to fill.
        for column_name in self.numeric_features:
            input_row[column_name] = input_row[column_name].astype(float)

        denial_probability = float(self.pipeline.predict_proba(input_row)[0, 1])
        transformed_row = self.preprocessor.transform(input_row)
        if hasattr(transformed_row, "toarray"):
            transformed_row = transformed_row.toarray()
        contributions = self.contributions_by_feature(transformed_row)

        ranked_features = sorted(
            contributions, key=lambda feature_name: abs(contributions[feature_name]), reverse=True
        )
        top_reasons = []
        for feature_name in ranked_features[:TOP_REASON_COUNT]:
            value = input_row.iloc[0][feature_name]
            top_reasons.append(reason_sentence(feature_name, value, contributions[feature_name]))

        return RiskPrediction(
            denial_probability=round(denial_probability, 4),
            top_reasons=top_reasons,
            model_type=self.model_type,
        )
