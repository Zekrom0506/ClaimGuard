"""Shapes of the case endpoints' responses."""

from datetime import datetime

from pydantic import BaseModel


class CaseCreatedResponse(BaseModel):
    """Returned straight after upload, before processing has finished."""

    case_id: str
    status: str


class CaseSummaryResponse(BaseModel):
    """One row in the case history list."""

    case_id: str
    original_filename: str
    status: str
    verdict: str | None
    denial_probability: float | None
    model_disagreement: bool | None
    final_verdict: str | None
    review_flag_count: int
    created_at: datetime


class CaseDetailResponse(BaseModel):
    """Everything the result page needs about one case."""

    case_id: str
    original_filename: str
    status: str
    treatment_type: str
    error_message: str | None
    masked_text: str | None
    extracted_fields: dict | None
    retrieved_chunks: list[dict]
    verdict: str | None
    verdict_reason: str | None
    requirement_checks: list[dict]
    citations: list[dict]
    failed_citations: list[dict]
    denial_probability: float | None
    risk_reasons: list[str]
    risk_model_type: str | None
    model_disagreement: bool | None
    missing_info_checklist: list[dict]
    # The appeal letter with patient details filled back in, for this screen only.
    appeal_letter: str | None
    reviewer_decision: str | None
    final_verdict: str | None
    reviewer_name: str | None
    reviewer_reason: str | None
    reviewed_at: datetime | None
    review_flags: list[str]
    llm_model_name: str | None
    llm_cost_usd: float | None
    processing_seconds: float | None
    created_at: datetime
