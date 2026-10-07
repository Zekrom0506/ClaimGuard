"""Dashboard numbers."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_session
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import build_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    database_session: Session = Depends(get_database_session),
) -> DashboardSummary:
    """Four numbers and the verdict split for the dashboard."""
    return build_dashboard_summary(database_session, get_settings().evaluation_reports_directory)
