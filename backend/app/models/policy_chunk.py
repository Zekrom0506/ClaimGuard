"""The policy_chunks table: coverage policy text split into searchable pieces."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# bge-small-en-v1.5 turns any text into a list of 384 numbers.
EMBEDDING_DIMENSIONS = 384


class PolicyChunk(Base):
    """About 500 words of one policy, with where it came from and two search indexes."""

    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    treatment_type: Mapped[str] = mapped_column(String(50), default="lumbar_spine_mri", index=True)
    policy_name: Mapped[str] = mapped_column(String(255))
    source_file: Mapped[str] = mapped_column(String(255), index=True)
    section_title: Mapped[str] = mapped_column(String(255))
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    # For meaning-based search (pgvector).
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    # For exact-word search. PostgreSQL fills this column itself whenever text changes.
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )

    __table_args__ = (
        Index("ix_policy_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )
