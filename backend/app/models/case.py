"""The prior_auth_cases table: one row per uploaded request."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaseStatus:
    """Allowed values for PriorAuthCase.status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


def utc_now() -> datetime:
    """Current time in UTC (used as a column default)."""
    return datetime.now(UTC)


def new_case_id() -> str:
    """A random id that does not reveal how many cases exist."""
    return str(uuid.uuid4())


class PriorAuthCase(Base):
    """A prior-authorization request and everything ClaimGuard worked out about it."""

    __tablename__ = "prior_auth_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_case_id)
    original_filename: Mapped[str] = mapped_column(String(255))
    treatment_type: Mapped[str] = mapped_column(String(50), default="lumbar_spine_mri")
    status: Mapped[str] = mapped_column(String(30), default=CaseStatus.QUEUED, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Original text contains patient details. It is stored here and nowhere else:
    # never logged, never sent to the language model.
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Placeholder -> original values, e.g. {"[PATIENT_NAME]": ["Jordan Testcase"]}.
    pii_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    processing_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
