"""Helpers for building fake pipelines from recorded model responses."""

from pathlib import Path

from app.core.config import get_settings
from app.core.llm_client import FakeLLMClient
from app.services.pipeline import PipelineDependencies

RECORDED_RESPONSES_DIRECTORY = Path(__file__).parent / "recorded_responses"


def load_recorded_response(file_name: str) -> str:
    """Return the text of tests/recorded_responses/<file_name>."""
    return (RECORDED_RESPONSES_DIRECTORY / file_name).read_text(encoding="utf-8")


def make_fake_pipeline(recorded_responses: dict[str, list[str]]) -> PipelineDependencies:
    """Pipeline dependencies whose language model only replays recorded answers."""
    return PipelineDependencies(
        settings=get_settings(),
        llm_client=FakeLLMClient(recorded_responses),
    )


def default_recorded_responses() -> dict[str, list[str]]:
    """Recorded answers for a straightforward case (EVAL-001)."""
    return {"extraction": [load_recorded_response("extraction_eval_001.json")]}
