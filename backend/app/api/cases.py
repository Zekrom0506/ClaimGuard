"""Upload a request PDF, list cases and read one case."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.rate_limiter import enforce_upload_rate_limit
from app.schemas.case import CaseCreatedResponse, CaseDetailResponse, CaseSummaryResponse
from app.services import case_presenter, case_processor, case_service

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


@router.get("", response_model=list[CaseSummaryResponse])
def list_cases(
    limit: int = Query(default=50, ge=1, le=200),
    database_session: Session = Depends(get_database_session),
) -> list[CaseSummaryResponse]:
    """Case history, newest first."""
    summaries = []
    for case in case_service.list_cases(database_session, limit):
        summaries.append(case_presenter.build_case_summary(case))
    return summaries


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: str,
    database_session: Session = Depends(get_database_session),
) -> CaseDetailResponse:
    """Return the current state of one case."""
    found_case = case_service.get_case_or_404(database_session, case_id)
    return case_presenter.build_case_detail(found_case)
