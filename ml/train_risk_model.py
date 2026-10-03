"""Train and compare two denial-risk models, then save the better one.

1. Logistic regression: a simple, explainable baseline.
2. XGBoost: gradient-boosted trees that can learn thresholds such as
   "physical therapy under 6 weeks" and combinations of features.

The data is split 70% train / 15% validation / 15% test. Models are compared
on the validation set; the test set is used once, at the end, for the chosen
model only, so its scores are not tuned to the test data.

Every run is saved to ml/training_runs/ as JSON (date, model, settings, scores).

Usage: python ml/train_risk_model.py
"""

import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

ML_DIRECTORY = Path(__file__).resolve().parent
TRAINING_DATA_FILE = ML_DIRECTORY / "data" / "training_records.csv"
MODEL_FILE = ML_DIRECTORY / "models" / "denial_risk_model.joblib"
TRAINING_RUNS_DIRECTORY = ML_DIRECTORY / "training_runs"

NUMERIC_FEATURES = ["age", "symptom_duration_weeks", "physical_therapy_weeks"]
BINARY_FEATURES = [
    "red_flag_present",
    "prior_lumbar_mri_within_12_months",
    "neurological_exam_documented",
]
CATEGORICAL_FEATURES = ["primary_diagnosis_code", "requesting_specialty"]
ALL_FEATURES = NUMERIC_FEATURES + BINARY_FEATURES + CATEGORICAL_FEATURES
LABEL_COLUMN = "denied"
RANDOM_SEED = 42
DECISION_THRESHOLD = 0.5
BACKGROUND_SAMPLE_SIZE = 200

LOGISTIC_REGRESSION_SETTINGS = {"max_iter": 1000, "C": 1.0}
XGBOOST_SETTINGS = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.1,
    "subsample": 0.9,
    "eval_metric": "logloss",
}


def load_training_data() -> tuple[pandas.DataFrame, pandas.Series]:
    """Features and labels from the synthetic CSV."""
    records = pandas.read_csv(TRAINING_DATA_FILE)
    # Safety net: the evaluation cases must never be used for training.
    assert not records["record_id"].str.startswith("EVAL-").any()
    return records[ALL_FEATURES], records[LABEL_COLUMN]


def build_preprocessor() -> ColumnTransformer:
    """Turn raw columns into numbers the models can use.

    - Numbers: missing values are filled with the median, and an extra 0/1
      column records that the value was missing ("not documented" is itself a
      strong signal). Then scaled, which logistic regression needs.
    - Yes/no columns are already 0/1.
    - Categories become one 0/1 column per value (one-hot encoding).
    """
    numeric_steps = Pipeline(
        [
            ("fill_missing", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_steps, NUMERIC_FEATURES),
            ("binary", "passthrough", BINARY_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )


def build_candidate_models() -> dict[str, Pipeline]:
    """Both models, each with its own copy of the preprocessing."""
    return {
        "logistic_regression": Pipeline(
            [
                ("preprocess", build_preprocessor()),
                ("model", LogisticRegression(**LOGISTIC_REGRESSION_SETTINGS)),
            ]
        ),
        "xgboost": Pipeline(
            [
                ("preprocess", build_preprocessor()),
                ("model", XGBClassifier(random_state=RANDOM_SEED, **XGBOOST_SETTINGS)),
            ]
        ),
    }


def score_model(model: Pipeline, features: pandas.DataFrame, labels: pandas.Series) -> dict:
    """Precision, recall, F1, ROC-AUC and accuracy for "denied" as the positive class."""
    denial_probabilities = model.predict_proba(features)[:, 1]
    predicted_denied = (denial_probabilities >= DECISION_THRESHOLD).astype(int)
    return {
        "precision": round(float(precision_score(labels, predicted_denied)), 4),
        "recall": round(float(recall_score(labels, predicted_denied)), 4),
        "f1": round(float(f1_score(labels, predicted_denied)), 4),
        "roc_auc": round(float(roc_auc_score(labels, denial_probabilities)), 4),
        "accuracy": round(float(accuracy_score(labels, predicted_denied)), 4),
    }


def split_data(features: pandas.DataFrame, labels: pandas.Series) -> dict:
    """70/15/15 split, keeping the share of denials the same in every part (stratify)."""
    train_features, rest_features, train_labels, rest_labels = train_test_split(
        features, labels, test_size=0.30, stratify=labels, random_state=RANDOM_SEED
    )
    validation_features, test_features, validation_labels, test_labels = train_test_split(
        rest_features, rest_labels, test_size=0.50, stratify=rest_labels, random_state=RANDOM_SEED
    )
    return {
        "train": (train_features, train_labels),
        "validation": (validation_features, validation_labels),
        "test": (test_features, test_labels),
    }


def save_model(model: Pipeline, model_type: str, train_features: pandas.DataFrame) -> None:
    """Save the model with everything the API needs to use and explain it."""
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    background_sample = train_features.sample(
        n=min(BACKGROUND_SAMPLE_SIZE, len(train_features)), random_state=RANDOM_SEED
    )
    joblib.dump(
        {
            "pipeline": model,
            "model_type": model_type,
            "numeric_features": NUMERIC_FEATURES,
            "binary_features": BINARY_FEATURES,
            "categorical_features": CATEGORICAL_FEATURES,
            # Typical rows, used by SHAP as the "average case" to compare against.
            "background_sample": background_sample,
            "trained_at": datetime.now().isoformat(timespec="seconds"),
            "data": "SYNTHETIC",
        },
        MODEL_FILE,
    )


def save_training_run(run_record: dict) -> Path:
    """Write this run's settings and scores to ml/training_runs/run_<timestamp>.json."""
    TRAINING_RUNS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    run_path = TRAINING_RUNS_DIRECTORY / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    run_path.write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
    return run_path


def main() -> None:
    """Train both models, pick the better one on validation ROC-AUC, test it, save it."""
    features, labels = load_training_data()
    data_splits = split_data(features, labels)
    train_features, train_labels = data_splits["train"]
    validation_features, validation_labels = data_splits["validation"]
    test_features, test_labels = data_splits["test"]

    validation_scores = {}
    trained_models = {}
    for model_type, model in build_candidate_models().items():
        model.fit(train_features, train_labels)
        trained_models[model_type] = model
        validation_scores[model_type] = score_model(model, validation_features, validation_labels)
        print(f"{model_type} validation: {validation_scores[model_type]}")

    best_model_type = max(
        validation_scores, key=lambda model_type: validation_scores[model_type]["roc_auc"]
    )
    best_model = trained_models[best_model_type]
    test_scores = score_model(best_model, test_features, test_labels)
    print(f"Chosen: {best_model_type}. Test: {test_scores}")

    save_model(best_model, best_model_type, train_features)
    run_path = save_training_run(
        {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "data": "SYNTHETIC",
            "training_file": TRAINING_DATA_FILE.name,
            "row_counts": {
                "train": len(train_features),
                "validation": len(validation_features),
                "test": len(test_features),
            },
            "denied_share": round(float(labels.mean()), 4),
            "settings": {
                "logistic_regression": LOGISTIC_REGRESSION_SETTINGS,
                "xgboost": XGBOOST_SETTINGS,
                "decision_threshold": DECISION_THRESHOLD,
                "random_seed": RANDOM_SEED,
            },
            "validation_scores": validation_scores,
            "chosen_model": best_model_type,
            "test_scores_for_chosen_model": test_scores,
        }
    )
    print(f"Saved model to {MODEL_FILE} and run record to {run_path}")


if __name__ == "__main__":
    main()
