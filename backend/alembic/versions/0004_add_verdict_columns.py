"""Add the AI verdict, requirement checks and checked citations to cases.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_COLUMNS = [
    sa.Column("verdict", sa.String(30), nullable=True),
    sa.Column("verdict_reason", sa.Text(), nullable=True),
    sa.Column("requirement_checks", sa.JSON(), nullable=True),
    sa.Column("citations", sa.JSON(), nullable=True),
    sa.Column("failed_citations", sa.JSON(), nullable=True),
]


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column("prior_auth_cases", column)
    op.create_index("ix_prior_auth_cases_verdict", "prior_auth_cases", ["verdict"])


def downgrade() -> None:
    op.drop_index("ix_prior_auth_cases_verdict", table_name="prior_auth_cases")
    for column in reversed(NEW_COLUMNS):
        op.drop_column("prior_auth_cases", column.name)
