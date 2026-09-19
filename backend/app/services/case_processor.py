"""The background job that turns an uploaded PDF into a checked case."""

import logging
import time

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.case import CaseStatus, PriorAuthCase
from app.services.pdf_reader import PdfReadError, read_pdf_text
from app.services.privacy_masker import mask_private_information

logger = logging.getLogger(__name__)


def set_status(database_session: Session, case: PriorAuthCase, status: str) -> None:
    """Change the case status and save it right away so the frontend sees progress."""
    case.status = status
    database_session.commit()


def run_pipeline(database_session: Session, case: PriorAuthCase, pdf_bytes: bytes) -> None:
    """Read the PDF and mask private details."""
    case.original_text = read_pdf_text(pdf_bytes)
    masking_result = mask_private_information(case.original_text)
    case.masked_text = masking_result.masked_text
    case.pii_values = masking_result.pii_values
    database_session.commit()


def process_case(case_id: str, pdf_bytes: bytes) -> None:
    """Process one case from start to finish. Runs after the upload response is sent.

    Opens its own database session because the request's session is closed
    by the time a background task runs.
    """
    database_session = SessionLocal()
    started_at = time.perf_counter()
    try:
        case = database_session.get(PriorAuthCase, case_id)
        if case is None:
            logger.error("Case %s not found for processing", case_id)
            return

        set_status(database_session, case, CaseStatus.PROCESSING)
        try:
            run_pipeline(database_session, case, pdf_bytes)
            final_status = CaseStatus.DONE
        except PdfReadError as error:
            case.error_message = str(error)
            final_status = CaseStatus.FAILED
        except Exception:
            # Log the case id and the error type only: the message could contain document text.
            logger.exception("Processing failed for case %s", case_id)
            case.error_message = "Processing failed. Please try again."
            final_status = CaseStatus.FAILED

        case.processing_seconds = round(time.perf_counter() - started_at, 2)
        set_status(database_session, case, final_status)
        logger.info("Case %s finished with status %s", case_id, final_status)
    finally:
        database_session.close()
