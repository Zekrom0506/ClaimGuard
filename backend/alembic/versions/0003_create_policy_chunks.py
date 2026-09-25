"""Enable pgvector, create policy_chunks and store retrieved chunks on cases.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("treatment_type", sa.String(50), nullable=False),
        sa.Column("policy_name", sa.String(255), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("section_title", sa.String(255), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
        ),
    )
    op.create_index("ix_policy_chunks_treatment_type", "policy_chunks", ["treatment_type"])
    op.create_index("ix_policy_chunks_source_file", "policy_chunks", ["source_file"])
    op.create_index(
        "ix_policy_chunks_search_vector",
        "policy_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.add_column("prior_auth_cases", sa.Column("retrieved_chunks", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("prior_auth_cases", "retrieved_chunks")
    op.drop_table("policy_chunks")
