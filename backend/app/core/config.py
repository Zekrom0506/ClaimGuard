"""Application settings, read from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repository root is three folders up from "app".
DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All configuration for ClaimGuard.

    Values come from environment variables (or a local .env file), so no
    secrets ever live in the code.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ClaimGuard"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://claimguard:claimguard@localhost:5432/claimguard"
    redis_url: str = "redis://localhost:6379/0"

    project_root: Path = DEFAULT_PROJECT_ROOT

    llm_provider: str = "anthropic"
    llm_model_name: str = "claude-sonnet-5"
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    # USD per million tokens, used to estimate cost per case. Check current pricing.
    llm_input_price_per_million_tokens: float = 2.0
    llm_output_price_per_million_tokens: float = 10.0

    extraction_prompt_version: str = "v1"
    verdict_prompt_version: str = "v1"

    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    # "hybrid" (vector + keyword) or "vector" (used by the evaluation comparison).
    retrieval_search_mode: str = "hybrid"
    spacy_model_name: str = "en_core_web_lg"

    max_upload_size_megabytes: int = 10
    uploads_per_minute_limit: int = 10

    @property
    def max_upload_size_bytes(self) -> int:
        """Upload limit converted to bytes."""
        return self.max_upload_size_megabytes * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return the settings object, created once and reused."""
    return Settings()
