"""The reviewer's decision and the audit log."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.schemas.case import CaseDetailResponse
from app.schemas.review import AuditLogEntryResponse, ReviewRequest
from app.services import audit_log, case_presenter, case_service, review

router = APIRouter(prefix="/cases/{case_id}", tags=["review"])


@router.post("/review", response_model=CaseDetailResponse)
def review_case(
    case_id: str,
    review_request: ReviewRequest,
    database_session: Session = Depends(get_database_session),
) -> CaseDetailResponse:
    """Accept the AI suggestion, or override it with a reason."""
    found_case = case_service.get_case_or_404(database_session, case_id)
    reviewed_case = review.apply_review(database_session, found_case, review_request)
    return case_presenter.build_case_detail(reviewed_case)


@router.get("/audit-log", response_model=list[AuditLogEntryResponse])
def get_audit_log(
    case_id: str,
    database_session: Session = Depends(get_database_session),
) -> list[AuditLogEntryResponse]:
    """Every recorded event for a case, oldest first."""
    case_service.get_case_or_404(database_session, case_id)
    entries = []
    for entry in audit_log.list_events(database_session, case_id):
        entries.append(AuditLogEntryResponse.model_validate(entry))
    return entries
