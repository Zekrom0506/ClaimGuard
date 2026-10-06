"""Helpers for building fake pipelines from recorded model responses."""

import hashlib
import math
import random
import re
import sys
from functools import lru_cache
from pathlib import Path

import pandas

from app.core.config import get_settings
from app.core.llm_client import FakeLLMClient
from app.models.policy_chunk import EMBEDDING_DIMENSIONS
from app.services.embeddings import Embedder
from app.services.pipeline import PipelineDependencies
from app.services.risk_model import DenialRiskModel

# The training code lives in ml/; tests reuse it so they test the real thing.
sys.path.insert(0, str(get_settings().project_root / "ml"))
import generate_training_data  # noqa: E402
import train_risk_model  # noqa: E402

RECORDED_RESPONSES_DIRECTORY = Path(__file__).parent / "recorded_responses"


def load_recorded_response(file_name: str) -> str:
    """Return the text of tests/recorded_responses/<file_name>."""
    return (RECORDED_RESPONSES_DIRECTORY / file_name).read_text(encoding="utf-8")


class FakeEmbedder(Embedder):
    """A tiny stand-in for the real embedding model, fast enough for unit tests.

    Each word is hashed to one of the 384 positions, so texts sharing words
    get similar vectors. It has no idea about meaning, but it lets tests run
    the real database search without downloading a model.
    """

    def embed_text(self, text: str) -> list[float]:
        """Bag-of-words vector, scaled to length 1."""
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for word in re.findall(r"[a-z0-9.]+", text.lower()):
            position = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIMENSIONS
            vector[position] += 1.0
        length = math.sqrt(sum(value * value for value in vector))
        if length == 0:
            vector[0] = 1.0
            return vector
        return [value / length for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectors for many texts."""
        return [self.embed_text(text) for text in texts]

    def embed_query(self, query_text: str) -> list[float]:
        """Vector for one query."""
        return self.embed_text(query_text)


def small_training_frame(record_count: int = 800) -> pandas.DataFrame:
    """Synthetic training records made with the real generator, without noise."""
    random_generator = random.Random(1)
    records = []
    for _ in range(record_count):
        record = generate_training_data.make_clinical_profile(random_generator)
        record["denied"] = generate_training_data.decide_by_policy(record)
        records.append(record)
    frame = pandas.DataFrame(records)
    for column_name in train_risk_model.NUMERIC_FEATURES:
        frame[column_name] = pandas.to_numeric(frame[column_name])
    return frame


@lru_cache
def train_small_risk_model(model_type: str = "xgboost") -> DenialRiskModel:
    """A small model trained with the real training code, kept for the whole test run."""
    frame = small_training_frame()
    features = frame[train_risk_model.ALL_FEATURES]
    model = train_risk_model.build_candidate_models()[model_type]
    model.fit(features, frame["denied"])
    return DenialRiskModel(
        {
            "pipeline": model,
            "model_type": model_type,
            "numeric_features": train_risk_model.NUMERIC_FEATURES,
            "binary_features": train_risk_model.BINARY_FEATURES,
            "categorical_features": train_risk_model.CATEGORICAL_FEATURES,
            "background_sample": features.head(100),
        }
    )


def make_fake_pipeline(
    recorded_responses: dict[str, list[str]], with_risk_model: bool = True
) -> PipelineDependencies:
    """Pipeline dependencies whose language model only replays recorded answers."""
    risk_model = None
    if with_risk_model:
        risk_model = train_small_risk_model()
    return PipelineDependencies(
        settings=get_settings(),
        llm_client=FakeLLMClient(recorded_responses),
        embedder=FakeEmbedder(),
        risk_model=risk_model,
    )


def default_recorded_responses() -> dict[str, list[str]]:
    """Recorded answers for a straightforward case (EVAL-001)."""
    return {
        "extraction": [load_recorded_response("extraction_eval_001.json")],
        "verdict": [load_recorded_response("verdict_eval_001_approved.json")],
        "appeal_letter": [load_recorded_response("appeal_letter_eval_033.txt")],
    }
