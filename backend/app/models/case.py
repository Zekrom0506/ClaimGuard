"""The prior_auth_cases table: one row per uploaded request."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
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

    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Which policy chunks the search returned: ids, sections and scores (no text).
    retrieved_chunks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # The AI's suggestion. Never a final decision: a reviewer always decides.
    verdict: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    verdict_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    failed_citations: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Second opinion from the trained risk model.
    denial_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_model_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_disagreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Next steps: a checklist for "missing_information", a letter for "likely_denied".
    missing_info_checklist: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Stored WITH placeholders; real details are filled in only when shown on screen.
    appeal_letter_draft: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The human decision. Only a reviewer sets final_verdict.
    reviewer_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewer_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reasons a human should look closer, e.g. "extraction_invalid".
    review_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    llm_model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    processing_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
