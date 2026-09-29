"""Upload a request PDF and read back the case."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.rate_limiter import enforce_upload_rate_limit
from app.models.case import PriorAuthCase
from app.schemas.case import CaseCreatedResponse, CaseDetailResponse
from app.services import case_processor, case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post(
    "",
    status_code=202,
    response_model=CaseCreatedResponse,
    dependencies=[Depends(enforce_upload_rate_limit)],
)
async def upload_case(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    database_session: Session = Depends(get_database_session),
) -> CaseCreatedResponse:
    """Accept a PDF, create a queued case, and process it in the background."""
    file_bytes = await file.read()
    filename = file.filename or "upload.pdf"
    case_service.validate_pdf_upload(filename, file_bytes)

    new_case = case_service.create_case(database_session, filename)
    background_tasks.add_task(
        case_processor.process_case, new_case.id, file_bytes, request.app.state.pipeline
    )
    return CaseCreatedResponse(case_id=new_case.id, status=new_case.status)


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: str,
    database_session: Session = Depends(get_database_session),
) -> CaseDetailResponse:
    """Return the current state of one case."""
    found_case = case_service.get_case_or_404(database_session, case_id)
    return build_case_detail(found_case)


def build_case_detail(case: PriorAuthCase) -> CaseDetailResponse:
    """Convert the database row to the response shape (never includes original text)."""
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
        review_flags=case.review_flags or [],
        llm_model_name=case.llm_model_name,
        llm_cost_usd=case.llm_cost_usd,
        processing_seconds=case.processing_seconds,
        created_at=case.created_at,
    )
