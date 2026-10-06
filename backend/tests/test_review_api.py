"""API tests for reviewer decisions, the case list and the audit log."""

import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.case import PriorAuthCase
from tests.conftest import evaluation_case_path
from tests.fakes import load_recorded_response, make_fake_pipeline

LABELS = json.loads(
    (get_settings().project_root / "data" / "evaluation" / "labels.json").read_text()
)


def identity_for(case_id: str) -> dict:
    for labelled_case in LABELS["cases"]:
        if labelled_case["case_id"] == case_id:
            return labelled_case["synthetic_identity"]
    raise KeyError(case_id)


def process(client: TestClient, evaluation_case_id: str) -> str:
    pdf_bytes = evaluation_case_path(evaluation_case_id).read_bytes()
    response = client.post(
        "/cases", files={"file": (f"{evaluation_case_id}.pdf", pdf_bytes, "application/pdf")}
    )
    return response.json()["case_id"]


def use_denied_case_responses(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline(
        {
            "extraction": [load_recorded_response("extraction_eval_033.json")],
            "verdict": [load_recorded_response("verdict_eval_033_denied.json")],
            "appeal_letter": [load_recorded_response("appeal_letter_eval_033.txt")],
        }
    )


def test_reviewer_can_accept_the_suggestion(client: TestClient) -> None:
    case_id = process(client, "EVAL-001")
    response = client.post(
        f"/cases/{case_id}/review", json={"decision": "accept", "reviewer_name": "Nurse Test"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["final_verdict"] == "likely_approved"
    assert body["reviewer_decision"] == "accept"
    assert body["verdict"] == "likely_approved"


def test_override_needs_a_reason(client: TestClient) -> None:
    case_id = process(client, "EVAL-001")
    response = client.post(
        f"/cases/{case_id}/review",
        json={
            "decision": "override",
            "reviewer_name": "Nurse Test",
            "final_verdict": "likely_denied",
        },
    )
    assert response.status_code == 422
    assert "reason" in response.json()["error"]["message"]


def test_override_with_reason_keeps_the_ai_suggestion(client: TestClient) -> None:
    case_id = process(client, "EVAL-001")
    response = client.post(
        f"/cases/{case_id}/review",
        json={
            "decision": "override",
            "reviewer_name": "Nurse Test",
            "final_verdict": "missing_information",
            "reason": "Therapy notes are not attached to the request.",
        },
    )
    body = response.json()
    assert body["final_verdict"] == "missing_information"
    assert body["verdict"] == "likely_approved"
    assert body["reviewer_reason"] == "Therapy notes are not attached to the request."


def test_cannot_accept_when_there_is_no_suggestion(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline({"extraction": ["not json"]})
    case_id = process(client, "EVAL-001")
    response = client.post(
        f"/cases/{case_id}/review", json={"decision": "accept", "reviewer_name": "Nurse Test"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "nothing_to_accept"


def test_cannot_review_a_case_still_processing(client: TestClient) -> None:
    with SessionLocal() as database_session:
        queued_case = PriorAuthCase(original_filename="x.pdf", status="processing")
        database_session.add(queued_case)
        database_session.commit()
        case_id = queued_case.id
    response = client.post(
        f"/cases/{case_id}/review", json={"decision": "accept", "reviewer_name": "Nurse Test"}
    )
    assert response.status_code == 409


def test_missing_information_case_gets_a_checklist(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline(
        {
            "extraction": [load_recorded_response("extraction_eval_001.json")],
            "verdict": [load_recorded_response("verdict_missing_information.json")],
        }
    )
    case_id = process(client, "EVAL-001")
    body = client.get(f"/cases/{case_id}").json()
    assert body["verdict"] == "missing_information"
    assert body["missing_info_checklist"][0]["what_to_add"] == (
        "Physical therapy records showing the number of weeks completed"
    )
    assert body["missing_info_checklist"][0]["policy_section"] == "6 Coding Information"
    assert body["appeal_letter"] is None


def test_denied_case_gets_letter_with_details_filled_in_on_screen_only(
    client: TestClient,
) -> None:
    use_denied_case_responses(client)
    case_id = process(client, "EVAL-033")
    body = client.get(f"/cases/{case_id}").json()
    identity = identity_for("EVAL-033")

    assert body["verdict"] == "likely_denied"
    assert identity["patient_name"] in body["appeal_letter"]
    assert identity["member_id"] in body["appeal_letter"]
    assert "[PROVIDER_NAME]" in body["appeal_letter"]

    with SessionLocal() as database_session:
        stored_draft = database_session.get(PriorAuthCase, case_id).appeal_letter_draft
    assert "[PATIENT_NAME]" in stored_draft
    assert identity["patient_name"] not in stored_draft


def test_failed_letter_does_not_stop_the_case(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline(
        {
            "extraction": [load_recorded_response("extraction_eval_033.json")],
            "verdict": [load_recorded_response("verdict_eval_033_denied.json")],
        }
    )
    case_id = process(client, "EVAL-033")
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "done"
    assert "appeal_letter_failed" in body["review_flags"]


def test_case_list_shows_newest_first(client: TestClient) -> None:
    first_case_id = process(client, "EVAL-001")
    second_case_id = process(client, "EVAL-001")
    rows = client.get("/cases").json()
    assert [row["case_id"] for row in rows] == [second_case_id, first_case_id]
    assert rows[0]["verdict"] == "likely_approved"


def test_audit_log_records_each_step(client: TestClient) -> None:
    case_id = process(client, "EVAL-001")
    client.post(
        f"/cases/{case_id}/review", json={"decision": "accept", "reviewer_name": "Nurse Test"}
    )
    entries = client.get(f"/cases/{case_id}/audit-log").json()
    assert [entry["event_type"] for entry in entries] == [
        "uploaded",
        "processing_finished",
        "reviewed",
    ]
    finished_entry = entries[1]
    assert finished_entry["prompt_versions"] == {"extraction": "v1", "verdict": "v1"}
    assert finished_entry["model_name"] == "fake-llm"
    assert len(finished_entry["retrieved_chunk_ids"]) == 5
    assert finished_entry["verdict"] == "likely_approved"
    assert finished_entry["denial_probability"] is not None
    assert entries[2]["final_verdict"] == "likely_approved"


def test_privacy_audit_log_contains_no_patient_details(client: TestClient) -> None:
    use_denied_case_responses(client)
    case_id = process(client, "EVAL-033")
    client.post(
        f"/cases/{case_id}/review",
        json={
            "decision": "override",
            "reviewer_name": "Nurse Test",
            "final_verdict": "likely_approved",
            "reason": "Spoke with the clinic; therapy records are on file for this member.",
        },
    )
    audit_text = json.dumps(client.get(f"/cases/{case_id}/audit-log").json()).lower()
    for private_value in identity_for("EVAL-033").values():
        assert private_value.lower() not in audit_text
    assert "therapy records are on file" not in audit_text


def test_audit_log_for_unknown_case_is_404(client: TestClient) -> None:
    assert client.get("/cases/nope/audit-log").status_code == 404
