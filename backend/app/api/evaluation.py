"""The latest evaluation results."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.dashboard import EvaluationSummary
from app.services.evaluation_reports import find_latest_full_report, summarise_report

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/latest", response_model=EvaluationSummary)
def latest_evaluation() -> EvaluationSummary:
    """Headline numbers from the most recent full evaluation run."""
    latest_report = find_latest_full_report(get_settings().evaluation_reports_directory)
    if latest_report is None:
        raise AppError(404, "no_evaluation", "No full evaluation has been run yet.")
    return summarise_report(latest_report)
