"""Load every policy PDF from data/policies/ into the database.

Usage (from the backend folder): python -m scripts.ingest_policies
"""

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_config import configure_logging
from app.services.embeddings import SentenceTransformerEmbedder
from app.services.policy_ingestion import ingest_policy_directory


def main() -> None:
    """Chunk, embed and store all policies, then print a summary."""
    settings = get_settings()
    configure_logging(settings.log_level)
    policies_directory = settings.project_root / "data" / "policies"
    embedder = SentenceTransformerEmbedder(settings.embedding_model_name)

    with SessionLocal() as database_session:
        chunk_counts = ingest_policy_directory(database_session, policies_directory, embedder)

    if not chunk_counts:
        print(f"No PDF files found in {policies_directory}")
    for file_name, chunk_count in chunk_counts.items():
        print(f"{file_name}: {chunk_count} chunks")


if __name__ == "__main__":
    main()
