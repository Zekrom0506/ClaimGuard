"""API tests for uploading and reading cases."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import evaluation_case_path, make_pdf_bytes
from tests.fakes import load_recorded_response, make_fake_pipeline


def upload_pdf(client: TestClient, pdf_bytes: bytes, filename: str = "request.pdf"):
    """POST a file to /cases."""
    return client.post("/cases", files={"file": (filename, pdf_bytes, "application/pdf")})


def test_upload_returns_case_id_and_processes_in_background(client: TestClient) -> None:
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    upload_response = upload_pdf(client, pdf_bytes)
    assert upload_response.status_code == 202
    case_id = upload_response.json()["case_id"]

    # TestClient runs background tasks before returning, so the case is finished here.
    case_response = client.get(f"/cases/{case_id}")
    assert case_response.status_code == 200
    body = case_response.json()
    assert body["status"] in {"done", "needs_human_review"}
    assert "[PATIENT_NAME]" in body["masked_text"]
    assert "original_text" not in body


def test_rejects_non_pdf_file(client: TestClient) -> None:
    response = upload_pdf(client, b"hello", filename="notes.txt")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_rejects_renamed_file_that_is_not_a_pdf(client: TestClient) -> None:
    response = upload_pdf(client, b"MZ fake program", filename="request.pdf")
    assert response.status_code == 415


def test_rejects_file_over_size_limit(client: TestClient) -> None:
    too_large = b"%PDF-" + b"0" * get_settings().max_upload_size_bytes
    response = upload_pdf(client, too_large)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_unreadable_pdf_marks_case_failed(client: TestClient) -> None:
    response = upload_pdf(client, b"%PDF-1.7 broken file")
    case_id = response.json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "failed"
    assert body["error_message"]


def test_pdf_without_text_marks_case_failed(client: TestClient) -> None:
    response = upload_pdf(client, make_pdf_bytes(""))
    body = client.get(f"/cases/{response.json()['case_id']}").json()
    assert body["status"] == "failed"


def test_unknown_case_returns_404_in_standard_error_format(client: TestClient) -> None:
    response = client.get("/cases/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "case_not_found"
    assert error["request_id"]


def test_upload_rate_limit(client: TestClient) -> None:
    pdf_bytes = make_pdf_bytes("CPT Code: 72148")
    limit = get_settings().uploads_per_minute_limit
    for _ in range(limit):
        assert upload_pdf(client, pdf_bytes).status_code == 202
    response = upload_pdf(client, pdf_bytes)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


def test_request_id_header_is_returned(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-123"})
    assert response.headers["X-Request-ID"] == "test-123"


def test_missing_file_gives_validation_error(client: TestClient) -> None:
    response = client.post("/cases")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_extracted_fields_are_returned(client: TestClient) -> None:
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["extracted_fields"]["procedure_code"]["value"] == "72158"
    assert body["llm_cost_usd"] is not None


def test_invalid_extraction_sends_case_to_human_review(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline({"extraction": ["not json"]})
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "needs_human_review"
    assert "extraction_invalid" in body["review_flags"]


def test_unreachable_language_model_marks_case_failed(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline({})
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "failed"


def test_full_pipeline_returns_verdict_with_verified_citations(client: TestClient) -> None:
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "done"
    assert body["verdict"] == "likely_approved"
    assert len(body["citations"]) == 2
    assert body["citations"][0]["section_title"] == "6 Coding Information"
    assert body["citations"][0]["chunk_text"]
    assert len(body["retrieved_chunks"]) == 5
    assert body["review_flags"] == []


def test_verdict_without_valid_citations_goes_to_human_review(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline(
        {
            "extraction": [load_recorded_response("extraction_eval_001.json")],
            "verdict": [load_recorded_response("verdict_hallucinated.json")],
        }
    )
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "needs_human_review"
    assert body["citations"] == []
    assert len(body["failed_citations"]) == 2
    assert "citation_failed" in body["review_flags"]


def test_case_without_any_policy_loaded_goes_to_human_review(client: TestClient) -> None:
    from sqlalchemy import text

    from app.core.database import engine

    with engine.begin() as connection:
        connection.execute(text("TRUNCATE policy_chunks"))
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "needs_human_review"
    assert "no_policy_found" in body["review_flags"]


def test_risk_score_and_reasons_are_returned(client: TestClient) -> None:
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["denial_probability"] < 0.5
    assert len(body["risk_reasons"]) == 3
    assert body["model_disagreement"] is False


def test_disagreement_between_ai_and_risk_model_is_flagged(client: TestClient) -> None:
    # Extraction says no therapy (high risk) but the recorded verdict says approved.
    client.app.state.pipeline = make_fake_pipeline(
        {
            "extraction": [load_recorded_response("extraction_eval_033.json")],
            "verdict": [load_recorded_response("verdict_eval_001_approved.json")],
        }
    )
    pdf_bytes = evaluation_case_path("EVAL-033").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["model_disagreement"] is True
    assert "ai_and_risk_model_disagree" in body["review_flags"]


def test_missing_risk_model_is_flagged_but_case_still_finishes(client: TestClient) -> None:
    client.app.state.pipeline = make_fake_pipeline(
        {
            "extraction": [load_recorded_response("extraction_eval_001.json")],
            "verdict": [load_recorded_response("verdict_eval_001_approved.json")],
        },
        with_risk_model=False,
    )
    pdf_bytes = evaluation_case_path("EVAL-001").read_bytes()
    case_id = upload_pdf(client, pdf_bytes).json()["case_id"]
    body = client.get(f"/cases/{case_id}").json()
    assert body["status"] == "done"
    assert body["denial_probability"] is None
    assert "risk_model_unavailable" in body["review_flags"]
