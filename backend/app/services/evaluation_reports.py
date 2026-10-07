"""Read the reports written by evaluation/run_evaluation.py."""

import json
from pathlib import Path

from app.schemas.dashboard import EvaluationSummary


def find_latest_full_report(reports_directory: Path) -> dict | None:
    """The newest full-pipeline report, or None if none has been run yet.

    Report names contain their timestamp, so sorting by name sorts by date.
    """
    report_paths = sorted(reports_directory.glob("eval_full_*.json"))
    if not report_paths:
        return None
    return json.loads(report_paths[-1].read_text(encoding="utf-8"))


def summarise_report(report: dict) -> EvaluationSummary:
    """Headline numbers from the first (hybrid search) run in a report."""
    main_run = report["runs"][0]
    return EvaluationSummary(
        run_at=report["run_at"],
        case_count=report["case_count"],
        search_mode=main_run["search_mode"],
        model_name=main_run.get("model_name"),
        verdict_accuracy=main_run.get("verdict_accuracy"),
        citation_section_accuracy=main_run.get("citation_section_accuracy"),
        hallucination_rate=main_run.get("hallucination_rate"),
        privacy_leaks=main_run.get("privacy_leaks"),
        average_seconds_per_case=main_run.get("average_seconds_per_case"),
        average_cost_usd_per_case=main_run.get("average_cost_usd_per_case"),
    )
