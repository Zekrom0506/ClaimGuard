"""Tests for health checks, the rate limiter when Redis fails, and the Ollama client."""

import httpx
import pytest
import redis
from fastapi.testclient import TestClient

from app.core.llm_client import LLMError, OllamaLLMClient
from app.core.rate_limiter import get_redis_client
from app.main import app
from app.services import health_checks
from tests.conftest import make_pdf_bytes


def test_database_check_succeeds_against_test_database() -> None:
    assert health_checks.is_database_reachable() is True


def test_redis_check_fails_cleanly_when_redis_is_unreachable(monkeypatch) -> None:
    class BrokenRedis:
        def ping(self):
            raise redis.ConnectionError("down")

    monkeypatch.setattr(
        health_checks.redis.Redis, "from_url", lambda *args, **kwargs: BrokenRedis()
    )
    assert health_checks.is_redis_reachable() is False


def test_uploads_still_work_when_redis_is_down(client: TestClient) -> None:
    class BrokenRedis:
        def incr(self, key):
            raise redis.ConnectionError("down")

    app.dependency_overrides[get_redis_client] = lambda: BrokenRedis()
    pdf_bytes = make_pdf_bytes("CPT Code: 72148")
    response = client.post("/cases", files={"file": ("a.pdf", pdf_bytes, "application/pdf")})
    assert response.status_code == 202


def test_ollama_client_reads_message_and_token_counts(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        assert url == "http://ollama:11434/api/chat"
        assert json["messages"][0]["role"] == "system"
        request = httpx.Request("POST", url)
        body = {"message": {"content": "{}"}, "prompt_eval_count": 50, "eval_count": 5}
        return httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    response = OllamaLLMClient("http://ollama:11434/", "llama3.1").complete("x", "sys", "user")
    assert response.text == "{}"
    assert response.input_tokens == 50


def test_ollama_client_wraps_connection_errors(monkeypatch) -> None:
    def failing_post(url, json, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", failing_post)
    with pytest.raises(LLMError):
        OllamaLLMClient("http://ollama:11434", "llama3.1").complete("x", "sys", "user")
