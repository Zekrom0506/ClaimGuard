"""Shapes for the reviewer's decision and the audit log."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.verdict import VerdictLabel

MINIMUM_REASON_LENGTH = 10


class ReviewRequest(BaseModel):
    """A reviewer accepts the AI suggestion or overrides it with a reason."""

    decision: Literal["accept", "override"]
    reviewer_name: str = Field(min_length=2, max_length=100)
    final_verdict: VerdictLabel | None = None
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_override_has_verdict_and_reason(self) -> "ReviewRequest":
        """Overrides must say what the decision is and why."""
        if self.decision == "override":
            if self.final_verdict is None:
                raise ValueError("An override needs a final_verdict.")
            reason_text = (self.reason or "").strip()
            if len(reason_text) < MINIMUM_REASON_LENGTH:
                raise ValueError(
                    f"An override needs a reason of at least {MINIMUM_REASON_LENGTH} characters."
                )
        return self


class AuditLogEntryResponse(BaseModel):
    """One audit log entry as returned by the API."""

    model_config = {"from_attributes": True}

    id: int
    case_id: str
    created_at: datetime
    event_type: str
    status: str | None
    model_name: str | None
    prompt_versions: dict | None
    retrieved_chunk_ids: list | None
    verdict: str | None
    denial_probability: float | None
    review_flags: list | None
    reviewer_decision: str | None
    final_verdict: str | None
