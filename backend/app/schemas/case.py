"""Shapes of the case endpoints' responses."""

from datetime import datetime

from pydantic import BaseModel


class CaseCreatedResponse(BaseModel):
    """Returned straight after upload, before processing has finished."""

    case_id: str
    status: str


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
    review_flags: list[str]
    llm_model_name: str | None
    llm_cost_usd: float | None
    processing_seconds: float | None
    created_at: datetime
