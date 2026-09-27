"""The shared objects every processing step needs, created once at startup."""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.llm_client import LLMClient, create_llm_client
from app.services.embeddings import Embedder, SentenceTransformerEmbedder


@dataclass
class PipelineDependencies:
    """Long-lived helpers passed to the background job.

    Bundling them makes it easy for tests and the evaluation script to swap in
    fakes (for example a FakeLLMClient) without touching the processing code.
    """

    settings: Settings
    llm_client: LLMClient
    embedder: Embedder


def build_pipeline_dependencies(settings: Settings) -> PipelineDependencies:
    """Create the real dependencies from settings."""
    return PipelineDependencies(
        settings=settings,
        llm_client=create_llm_client(settings),
        embedder=SentenceTransformerEmbedder(settings.embedding_model_name),
    )
