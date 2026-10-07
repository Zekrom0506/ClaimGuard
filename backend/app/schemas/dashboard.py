"""Shapes for the dashboard and evaluation endpoints."""

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Four numbers and one chart. All data in this project is synthetic."""

    data_label: str
    total_cases: int
    latest_verdict_accuracy: float | None
    latest_evaluation_run_at: str | None
    reviewed_cases: int
    override_rate: float | None
    average_processing_seconds: float | None
    verdict_counts: dict[str, int]


class EvaluationSummary(BaseModel):
    """Headline numbers from the most recent full evaluation run."""

    run_at: str
    case_count: int
    search_mode: str
    model_name: str | None
    verdict_accuracy: float | None
    citation_section_accuracy: float | None
    hallucination_rate: float | None
    privacy_leaks: int | None
    average_seconds_per_case: float | None
    average_cost_usd_per_case: float | None
