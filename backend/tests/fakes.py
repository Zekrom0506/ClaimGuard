"""Helpers for building fake pipelines from recorded model responses."""

import hashlib
import math
import re
from pathlib import Path

from app.core.config import get_settings
from app.core.llm_client import FakeLLMClient
from app.models.policy_chunk import EMBEDDING_DIMENSIONS
from app.services.embeddings import Embedder
from app.services.pipeline import PipelineDependencies

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


def make_fake_pipeline(recorded_responses: dict[str, list[str]]) -> PipelineDependencies:
    """Pipeline dependencies whose language model only replays recorded answers."""
    return PipelineDependencies(
        settings=get_settings(),
        llm_client=FakeLLMClient(recorded_responses),
        embedder=FakeEmbedder(),
    )


def default_recorded_responses() -> dict[str, list[str]]:
    """Recorded answers for a straightforward case (EVAL-001)."""
    return {
        "extraction": [load_recorded_response("extraction_eval_001.json")],
        "verdict": [load_recorded_response("verdict_eval_001_approved.json")],
    }
