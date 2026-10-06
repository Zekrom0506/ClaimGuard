"""Apply a human reviewer's decision to a case."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.audit_log import AuditEventType
from app.models.case import CaseStatus, PriorAuthCase
from app.schemas.review import ReviewRequest
from app.services.audit_log import record_event

REVIEWABLE_STATUSES = {CaseStatus.DONE, CaseStatus.NEEDS_HUMAN_REVIEW}


def apply_review(
    database_session: Session, case: PriorAuthCase, review_request: ReviewRequest
) -> PriorAuthCase:
    """Record the reviewer's final decision. The AI's own suggestion is kept unchanged."""
    if case.status not in REVIEWABLE_STATUSES:
        raise AppError(
            409, "case_not_ready", f"A case in status '{case.status}' cannot be reviewed."
        )

    if review_request.decision == "accept":
        if case.verdict is None:
            raise AppError(
                409,
                "nothing_to_accept",
                "There is no AI suggestion to accept. Override with your own decision.",
            )
        case.final_verdict = case.verdict
    else:
        case.final_verdict = review_request.final_verdict

    case.reviewer_decision = review_request.decision
    case.reviewer_name = review_request.reviewer_name
    case.reviewer_reason = review_request.reason
    case.reviewed_at = datetime.now(UTC)
    database_session.commit()

    record_event(database_session, case, AuditEventType.REVIEWED)
    return case
