"""API tests for the dashboard and the latest evaluation endpoint."""

import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import evaluation_case_path


def write_report(directory, run_at: str, accuracy: float) -> None:
    report = {
        "run_at": run_at,
        "mode": "full",
        "case_count": 40,
        "runs": [
            {
                "search_mode": "hybrid",
                "model_name": "fake",
                "verdict_accuracy": accuracy,
                "citation_section_accuracy": 0.8,
                "hallucination_rate": 0.0,
                "privacy_leaks": 0,
                "average_seconds_per_case": 5.0,
                "average_cost_usd_per_case": 0.01,
            }
        ],
    }
    file_name = f"eval_full_{run_at.replace(':', '').replace('-', '')}.json"
    (directory / file_name).write_text(json.dumps(report))


def use_reports_directory(monkeypatch, directory) -> None:
    settings = get_settings()
    monkeypatch.setattr(
        type(settings), "evaluation_reports_directory", property(lambda s: directory)
    )


def test_empty_dashboard(client: TestClient, monkeypatch, tmp_path) -> None:
    use_reports_directory(monkeypatch, tmp_path)
    body = client.get("/dashboard/summary").json()
    assert body["data_label"] == "SYNTHETIC DATA"
    assert body["total_cases"] == 0
    assert body["latest_verdict_accuracy"] is None
    assert body["override_rate"] is None
    assert body["verdict_counts"] == {
        "likely_approved": 0,
        "missing_information": 0,
        "likely_denied": 0,
    }


def test_dashboard_counts_cases_reviews_and_latest_accuracy(
    client: TestClient, monkeypatch, tmp_path
) -> None:
    use_reports_directory(monkeypatch, tmp_path)
    write_report(tmp_path, "2026-10-01T10:00:00", 0.7)
    write_report(tmp_path, "2026-10-09T10:00:00", 0.85)

    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_ids = []
    for _ in range(2):
        upload = client.post("/cases", files={"file": ("a.pdf", pdf_bytes, "application/pdf")})
        case_ids.append(upload.json()["case_id"])
    client.post(f"/cases/{case_ids[0]}/review", json={"decision": "accept", "reviewer_name": "N T"})
    client.post(
        f"/cases/{case_ids[1]}/review",
        json={
            "decision": "override",
            "reviewer_name": "N T",
            "final_verdict": "likely_denied",
            "reason": "Reviewer disagrees after reading notes.",
        },
    )

    body = client.get("/dashboard/summary").json()
    assert body["total_cases"] == 2
    assert body["verdict_counts"]["likely_approved"] == 2
    assert body["override_rate"] == 0.5
    assert body["latest_verdict_accuracy"] == 0.85
    assert body["average_processing_seconds"] is not None


def test_latest_evaluation_404_when_none(client: TestClient, monkeypatch, tmp_path) -> None:
    use_reports_directory(monkeypatch, tmp_path)
    response = client.get("/evaluation/latest")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_evaluation"


def test_latest_evaluation_returns_newest_report(client: TestClient, monkeypatch, tmp_path) -> None:
    use_reports_directory(monkeypatch, tmp_path)
    write_report(tmp_path, "2026-10-01T10:00:00", 0.7)
    write_report(tmp_path, "2026-10-09T10:00:00", 0.85)
    body = client.get("/evaluation/latest").json()
    assert body["run_at"] == "2026-10-09T10:00:00"
    assert body["verdict_accuracy"] == 0.85
