"""The audit_log_entries table: an append-only record of what happened to each case.

It answers "which prompt, model, policy text and scores led to this suggestion,
and what did the human decide?" months later. It must never contain patient
details, so only ids, versions, labels and numbers are stored here.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.case import utc_now


class AuditEventType:
    """Allowed values for AuditLogEntry.event_type."""

    UPLOADED = "uploaded"
    PROCESSING_FINISHED = "processing_finished"
    REVIEWED = "reviewed"


class AuditLogEntry(Base):
    """One event in a case's history."""

    __tablename__ = "audit_log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    event_type: Mapped[str] = mapped_column(String(40))

    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    denial_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    reviewer_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
