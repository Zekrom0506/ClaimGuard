"""Write and read audit log entries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLogEntry
from app.models.case import PriorAuthCase


def record_event(database_session: Session, case: PriorAuthCase, event_type: str) -> None:
    """Add one entry describing the case's current state.

    Only non-identifying data is copied: ids, versions, labels and scores.
    Free text (document text, reasons, letters) is deliberately left out
    because it could contain patient details.
    """
    retrieved_chunk_ids = []
    for chunk_summary in case.retrieved_chunks or []:
        retrieved_chunk_ids.append(chunk_summary["chunk_id"])

    database_session.add(
        AuditLogEntry(
            case_id=case.id,
            event_type=event_type,
            status=case.status,
            model_name=case.llm_model_name,
            prompt_versions=case.prompt_versions,
            retrieved_chunk_ids=retrieved_chunk_ids,
            verdict=case.verdict,
            denial_probability=case.denial_probability,
            review_flags=case.review_flags,
            reviewer_decision=case.reviewer_decision,
            final_verdict=case.final_verdict,
        )
    )
    database_session.commit()


def list_events(database_session: Session, case_id: str) -> list[AuditLogEntry]:
    """All entries for a case, oldest first."""
    statement = (
        select(AuditLogEntry)
        .where(AuditLogEntry.case_id == case_id)
        .order_by(AuditLogEntry.created_at, AuditLogEntry.id)
    )
    return list(database_session.scalars(statement))
