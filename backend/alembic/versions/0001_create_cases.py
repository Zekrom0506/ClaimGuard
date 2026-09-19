"""Create the prior_auth_cases table.

Revision ID: 0001
Revises:
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prior_auth_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("treatment_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("masked_text", sa.Text(), nullable=True),
        sa.Column("pii_values", sa.JSON(), nullable=True),
        sa.Column("processing_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prior_auth_cases_status", "prior_auth_cases", ["status"])


def downgrade() -> None:
    op.drop_index("ix_prior_auth_cases_status", table_name="prior_auth_cases")
    op.drop_table("prior_auth_cases")
