"""Add extraction results, review flags and model usage to cases.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_COLUMNS = [
    sa.Column("extracted_fields", sa.JSON(), nullable=True),
    sa.Column("review_flags", sa.JSON(), nullable=True),
    sa.Column("llm_model_name", sa.String(100), nullable=True),
    sa.Column("prompt_versions", sa.JSON(), nullable=True),
    sa.Column("llm_input_tokens", sa.Integer(), nullable=True),
    sa.Column("llm_output_tokens", sa.Integer(), nullable=True),
    sa.Column("llm_cost_usd", sa.Float(), nullable=True),
]


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column("prior_auth_cases", column)


def downgrade() -> None:
    for column in reversed(NEW_COLUMNS):
        op.drop_column("prior_auth_cases", column.name)
