"""Numbers for the dashboard."""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import PriorAuthCase
from app.schemas.dashboard import DashboardSummary
from app.schemas.verdict import VERDICT_LABELS
from app.services.evaluation_reports import find_latest_full_report, summarise_report


def count_verdicts(database_session: Session) -> dict[str, int]:
    """How many cases got each AI verdict (every label appears, even with 0)."""
    verdict_counts = {}
    for verdict_label in VERDICT_LABELS:
        verdict_counts[verdict_label] = 0
    statement = (
        select(PriorAuthCase.verdict, func.count())
        .where(PriorAuthCase.verdict.is_not(None))
        .group_by(PriorAuthCase.verdict)
    )
    for verdict_label, count in database_session.execute(statement):
        verdict_counts[verdict_label] = count
    return verdict_counts


def calculate_override_rate(database_session: Session) -> tuple[int, float | None]:
    """(number of reviewed cases, share of them where the reviewer overrode the AI)."""
    reviewed_count = database_session.scalar(
        select(func.count()).where(PriorAuthCase.reviewer_decision.is_not(None))
    )
    if not reviewed_count:
        return 0, None
    override_count = database_session.scalar(
        select(func.count()).where(PriorAuthCase.reviewer_decision == "override")
    )
    return reviewed_count, round(override_count / reviewed_count, 4)


def build_dashboard_summary(database_session: Session, reports_directory: Path) -> DashboardSummary:
    """Collect the four numbers and the chart data."""
    total_cases = database_session.scalar(select(func.count()).select_from(PriorAuthCase))
    average_seconds = database_session.scalar(select(func.avg(PriorAuthCase.processing_seconds)))
    reviewed_count, override_rate = calculate_override_rate(database_session)

    latest_accuracy = None
    latest_run_at = None
    latest_report = find_latest_full_report(reports_directory)
    if latest_report is not None:
        evaluation_summary = summarise_report(latest_report)
        latest_accuracy = evaluation_summary.verdict_accuracy
        latest_run_at = evaluation_summary.run_at

    if average_seconds is not None:
        average_seconds = round(float(average_seconds), 2)

    return DashboardSummary(
        data_label="SYNTHETIC DATA",
        total_cases=total_cases or 0,
        latest_verdict_accuracy=latest_accuracy,
        latest_evaluation_run_at=latest_run_at,
        reviewed_cases=reviewed_count,
        override_rate=override_rate,
        average_processing_seconds=average_seconds,
        verdict_counts=count_verdicts(database_session),
    )
