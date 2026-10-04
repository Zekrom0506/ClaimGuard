"""The shared objects every processing step needs, created once at startup."""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.llm_client import LLMClient, create_llm_client
from app.services.embeddings import Embedder, SentenceTransformerEmbedder
from app.services.risk_model import DenialRiskModel


@dataclass
class PipelineDependencies:
    """Long-lived helpers passed to the background job.

    Bundling them makes it easy for tests and the evaluation script to swap in
    fakes (for example a FakeLLMClient) without touching the processing code.
    """

    settings: Settings
    llm_client: LLMClient
    embedder: Embedder
    risk_model: DenialRiskModel | None = None


def build_pipeline_dependencies(settings: Settings) -> PipelineDependencies:
    """Create the real dependencies from settings. The risk model is loaded once, here."""
    return PipelineDependencies(
        settings=settings,
        llm_client=create_llm_client(settings),
        embedder=SentenceTransformerEmbedder(settings.embedding_model_name),
        risk_model=DenialRiskModel.load(settings.resolved_risk_model_path),
    )
