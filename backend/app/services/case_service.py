"""Creating, validating and loading cases."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.audit_log import AuditEventType
from app.models.case import CaseStatus, PriorAuthCase
from app.services.audit_log import record_event

PDF_FILE_SIGNATURE = b"%PDF-"


def validate_pdf_upload(filename: str, file_bytes: bytes) -> None:
    """Reject anything that is not a PDF under the size limit."""
    settings = get_settings()
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise AppError(
            413,
            "file_too_large",
            f"The file is larger than {settings.max_upload_size_megabytes} MB.",
        )
    if len(file_bytes) == 0:
        raise AppError(400, "empty_file", "The uploaded file is empty.")
    # Check the file's first bytes, not just its name: a renamed .exe is not a PDF.
    if not filename.lower().endswith(".pdf") or not file_bytes.startswith(PDF_FILE_SIGNATURE):
        raise AppError(415, "unsupported_file_type", "Only PDF files are accepted.")


def create_case(database_session: Session, filename: str) -> PriorAuthCase:
    """Save a new case in the queued state and return it."""
    new_case = PriorAuthCase(original_filename=filename, status=CaseStatus.QUEUED)
    database_session.add(new_case)
    database_session.commit()
    database_session.refresh(new_case)
    record_event(database_session, new_case, AuditEventType.UPLOADED)
    return new_case


def list_cases(database_session: Session, limit: int) -> list[PriorAuthCase]:
    """Most recent cases first."""
    statement = select(PriorAuthCase).order_by(PriorAuthCase.created_at.desc()).limit(limit)
    return list(database_session.scalars(statement))


def get_case_or_404(database_session: Session, case_id: str) -> PriorAuthCase:
    """Load a case or raise a 404 error."""
    found_case = database_session.get(PriorAuthCase, case_id)
    if found_case is None:
        raise AppError(404, "case_not_found", f"No case with id {case_id}.")
    return found_case
