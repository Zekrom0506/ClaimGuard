"""Load policy PDFs into the policy_chunks table."""

import logging
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.policy_chunk import PolicyChunk
from app.services.embeddings import Embedder
from app.services.pdf_reader import read_pdf_pages
from app.services.policy_chunker import chunk_policy

logger = logging.getLogger(__name__)


def policy_name_from_file(pdf_path: Path) -> str:
    """'sample_lumbar_mri_policy.pdf' -> 'Sample Lumbar Mri Policy'."""
    return pdf_path.stem.replace("_", " ").replace("-", " ").title()


def ingest_policy_pdf(
    database_session: Session,
    pdf_path: Path,
    embedder: Embedder,
    treatment_type: str = "lumbar_spine_mri",
) -> int:
    """Chunk, embed and store one policy. Re-running replaces its old chunks."""
    pages = read_pdf_pages(pdf_path.read_bytes())
    chunks = chunk_policy(pages)
    if not chunks:
        logger.warning("No text found in %s", pdf_path.name)
        return 0

    chunk_texts = []
    for chunk in chunks:
        chunk_texts.append(chunk.text)
    vectors = embedder.embed_documents(chunk_texts)

    database_session.execute(delete(PolicyChunk).where(PolicyChunk.source_file == pdf_path.name))
    policy_name = policy_name_from_file(pdf_path)
    for chunk, vector in zip(chunks, vectors, strict=True):
        database_session.add(
            PolicyChunk(
                treatment_type=treatment_type,
                policy_name=policy_name,
                source_file=pdf_path.name,
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding=vector,
            )
        )
    database_session.commit()
    logger.info("Stored %d chunks from %s", len(chunks), pdf_path.name)
    return len(chunks)


def ingest_policy_directory(
    database_session: Session, policies_directory: Path, embedder: Embedder
) -> dict[str, int]:
    """Ingest every PDF in a folder. Returns chunk counts per file."""
    chunk_counts = {}
    for pdf_path in sorted(policies_directory.glob("*.pdf")):
        chunk_counts[pdf_path.name] = ingest_policy_pdf(database_session, pdf_path, embedder)
    return chunk_counts
