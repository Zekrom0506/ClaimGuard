"""Turn case rows into API responses."""

from app.models.case import PriorAuthCase
from app.schemas.case import CaseDetailResponse, CaseSummaryResponse
from app.services.next_steps import fill_placeholders


def build_case_summary(case: PriorAuthCase) -> CaseSummaryResponse:
    """The short version used in the history list."""
    return CaseSummaryResponse(
        case_id=case.id,
        original_filename=case.original_filename,
        status=case.status,
        verdict=case.verdict,
        denial_probability=case.denial_probability,
        model_disagreement=case.model_disagreement,
        final_verdict=case.final_verdict,
        review_flag_count=len(case.review_flags or []),
        created_at=case.created_at,
    )


def build_case_detail(case: PriorAuthCase) -> CaseDetailResponse:
    """The full version for the result page. Never includes the original text."""
    appeal_letter = None
    if case.appeal_letter_draft:
        appeal_letter = fill_placeholders(case.appeal_letter_draft, case.pii_values or {})

    return CaseDetailResponse(
        case_id=case.id,
        original_filename=case.original_filename,
        status=case.status,
        treatment_type=case.treatment_type,
        error_message=case.error_message,
        masked_text=case.masked_text,
        extracted_fields=case.extracted_fields,
        retrieved_chunks=case.retrieved_chunks or [],
        verdict=case.verdict,
        verdict_reason=case.verdict_reason,
        requirement_checks=case.requirement_checks or [],
        citations=case.citations or [],
        failed_citations=case.failed_citations or [],
        denial_probability=case.denial_probability,
        risk_reasons=case.risk_reasons or [],
        risk_model_type=case.risk_model_type,
        model_disagreement=case.model_disagreement,
        missing_info_checklist=case.missing_info_checklist or [],
        appeal_letter=appeal_letter,
        reviewer_decision=case.reviewer_decision,
        final_verdict=case.final_verdict,
        reviewer_name=case.reviewer_name,
        reviewer_reason=case.reviewer_reason,
        reviewed_at=case.reviewed_at,
        review_flags=case.review_flags or [],
        llm_model_name=case.llm_model_name,
        llm_cost_usd=case.llm_cost_usd,
        processing_seconds=case.processing_seconds,
        created_at=case.created_at,
    )
