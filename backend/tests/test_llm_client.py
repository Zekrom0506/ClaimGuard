"""Tests for the LLM client wrapper (no real model is ever called)."""

from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.core.llm_client import (
    AnthropicLLMClient,
    FakeLLMClient,
    LLMError,
    OllamaLLMClient,
    OpenAICompatibleLLMClient,
    RecordingLLMClient,
    calculate_cost_usd,
    create_llm_client,
)


def test_fake_client_replays_responses_in_order_and_repeats_the_last() -> None:
    fake_client = FakeLLMClient({"extraction": ["first", "second"]})
    answers = []
    for _ in range(3):
        answers.append(fake_client.complete("extraction", "system", "user").text)
    assert answers == ["first", "second", "second"]


def test_fake_client_records_prompts() -> None:
    fake_client = FakeLLMClient({"verdict": ["{}"]})
    fake_client.complete("verdict", "system text", "user text")
    assert fake_client.sent_prompts[0].user_prompt == "user text"


def test_fake_client_without_response_for_task_raises() -> None:
    with pytest.raises(LLMError):
        FakeLLMClient({}).complete("extraction", "system", "user")


def test_recording_client_passes_calls_through() -> None:
    recording_client = RecordingLLMClient(FakeLLMClient({"letter": ["Dear reviewer"]}))
    response = recording_client.complete("letter", "system", "user")
    assert response.text == "Dear reviewer"
    assert len(recording_client.sent_prompts) == 1


def test_anthropic_client_without_key_raises_clear_error() -> None:
    with pytest.raises(LLMError):
        AnthropicLLMClient(api_key="", model_name="claude-sonnet-5").complete("x", "s", "u")


def test_anthropic_client_joins_text_blocks_and_reads_usage(monkeypatch) -> None:
    text_blocks = [
        SimpleNamespace(type="text", text='{"a": '),
        SimpleNamespace(type="text", text="1}"),
    ]
    fake_message = SimpleNamespace(
        content=text_blocks,
        usage=SimpleNamespace(input_tokens=120, output_tokens=8),
    )
    fake_sdk = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: fake_message))
    llm_client = AnthropicLLMClient(api_key="test-key", model_name="claude-sonnet-5")
    monkeypatch.setattr(llm_client, "_get_sdk_client", lambda: fake_sdk)

    response = llm_client.complete("extraction", "system", "user")
    assert response.text == '{"a": 1}'
    assert response.input_tokens == 120


def test_factory_builds_the_configured_provider() -> None:
    assert isinstance(create_llm_client(Settings(llm_provider="anthropic")), AnthropicLLMClient)
    assert isinstance(create_llm_client(Settings(llm_provider="ollama")), OllamaLLMClient)
    assert isinstance(
        create_llm_client(Settings(llm_provider="openai_compatible")), OpenAICompatibleLLMClient
    )
    with pytest.raises(ValueError):
        create_llm_client(Settings(llm_provider="unknown"))


def test_cost_uses_prices_from_settings() -> None:
    settings = Settings(
        llm_input_price_per_million_tokens=2.0, llm_output_price_per_million_tokens=10.0
    )
    assert calculate_cost_usd(1_000_000, 100_000, settings) == pytest.approx(3.0)


def make_chat_response(status_code: int, body: dict | None = None, headers=None) -> httpx.Response:
    """A fake reply from an OpenAI-style chat API."""
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return httpx.Response(status_code, json=body or {}, headers=headers, request=request)


CHAT_BODY = {
    "choices": [{"message": {"content": '<think>hmm</think>\n{"a": 1}'}}],
    "usage": {"prompt_tokens": 90, "completion_tokens": 7},
}


def test_openai_compatible_client_sends_chat_request_and_reads_usage(monkeypatch) -> None:
    sent_requests = []

    def fake_post(url, json, headers, timeout):
        sent_requests.append((url, json, headers))
        return make_chat_response(200, CHAT_BODY)

    monkeypatch.setattr(httpx, "post", fake_post)
    llm_client = OpenAICompatibleLLMClient(
        "https://api.example.com/v1/", "key-1", "qwen/qwen3-32b", reasoning_effort="none"
    )
    response = llm_client.complete("verdict", "system text", "user text", max_output_tokens=500)

    url, body, headers = sent_requests[0]
    assert url == "https://api.example.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer key-1"
    assert body["messages"][0] == {"role": "system", "content": "system text"}
    assert body["max_tokens"] == 500
    assert body["reasoning_effort"] == "none"
    # Thinking text is removed so only the answer is parsed.
    assert response.text == '{"a": 1}'
    assert response.input_tokens == 90
    assert response.output_tokens == 7


def test_openai_compatible_client_leaves_out_reasoning_effort_when_not_set(monkeypatch) -> None:
    sent_bodies = []

    def fake_post(url, json, headers, timeout):
        sent_bodies.append(json)
        return make_chat_response(200, CHAT_BODY)

    monkeypatch.setattr(httpx, "post", fake_post)
    OpenAICompatibleLLMClient("https://x/v1", "key", "model").complete("x", "s", "u")
    assert "reasoning_effort" not in sent_bodies[0]


def test_openai_compatible_client_waits_and_retries_after_rate_limit(monkeypatch) -> None:
    replies = [
        make_chat_response(429, headers={"retry-after": "4"}),
        make_chat_response(200, CHAT_BODY),
    ]
    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: replies.pop(0))
    waits = []
    llm_client = OpenAICompatibleLLMClient("https://x/v1", "key", "model", sleep=waits.append)

    response = llm_client.complete("x", "s", "u")
    assert response.text == '{"a": 1}'
    assert waits == [5.0]


def test_openai_compatible_client_gives_up_when_daily_limit_is_used_up(monkeypatch) -> None:
    reply = make_chat_response(429, headers={"retry-after": "3600"})
    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: reply)
    llm_client = OpenAICompatibleLLMClient("https://x/v1", "key", "model", sleep=lambda s: None)
    with pytest.raises(LLMError, match="daily free limit"):
        llm_client.complete("x", "s", "u")


def test_openai_compatible_client_reports_http_errors(monkeypatch) -> None:
    reply = make_chat_response(401, {"error": {"message": "Invalid API Key"}})
    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: reply)
    with pytest.raises(LLMError, match="HTTP 401"):
        OpenAICompatibleLLMClient("https://x/v1", "bad", "model").complete("x", "s", "u")


def test_openai_compatible_client_without_key_raises_clear_error() -> None:
    with pytest.raises(LLMError, match="OPENAI_COMPATIBLE_API_KEY"):
        OpenAICompatibleLLMClient("https://x/v1", "", "model").complete("x", "s", "u")
