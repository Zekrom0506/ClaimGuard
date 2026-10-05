"""Add next steps and reviewer decision to cases, and the audit log table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_CASE_COLUMNS = [
    sa.Column("missing_info_checklist", sa.JSON(), nullable=True),
    sa.Column("appeal_letter_draft", sa.Text(), nullable=True),
    sa.Column("reviewer_decision", sa.String(20), nullable=True),
    sa.Column("final_verdict", sa.String(30), nullable=True),
    sa.Column("reviewer_name", sa.String(100), nullable=True),
    sa.Column("reviewer_reason", sa.Text(), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
]


def upgrade() -> None:
    for column in NEW_CASE_COLUMNS:
        op.add_column("prior_auth_cases", column)

    op.create_table(
        "audit_log_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("prior_auth_cases.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("prompt_versions", sa.JSON(), nullable=True),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("verdict", sa.String(30), nullable=True),
        sa.Column("denial_probability", sa.Float(), nullable=True),
        sa.Column("review_flags", sa.JSON(), nullable=True),
        sa.Column("reviewer_decision", sa.String(20), nullable=True),
        sa.Column("final_verdict", sa.String(30), nullable=True),
    )
    op.create_index("ix_audit_log_entries_case_id", "audit_log_entries", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_entries_case_id", table_name="audit_log_entries")
    op.drop_table("audit_log_entries")
    for column in reversed(NEW_CASE_COLUMNS):
        op.drop_column("prior_auth_cases", column.name)
