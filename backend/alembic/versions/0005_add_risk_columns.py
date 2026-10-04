"""Add the risk model's score, reasons and the disagreement flag to cases.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_COLUMNS = [
    sa.Column("denial_probability", sa.Float(), nullable=True),
    sa.Column("risk_reasons", sa.JSON(), nullable=True),
    sa.Column("risk_model_type", sa.String(50), nullable=True),
    sa.Column("model_disagreement", sa.Boolean(), nullable=True),
]


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column("prior_auth_cases", column)


def downgrade() -> None:
    for column in reversed(NEW_COLUMNS):
        op.drop_column("prior_auth_cases", column.name)
