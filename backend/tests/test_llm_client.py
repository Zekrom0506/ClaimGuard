"""Tests for the LLM client wrapper (no real model is ever called)."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.llm_client import (
    AnthropicLLMClient,
    FakeLLMClient,
    LLMError,
    OllamaLLMClient,
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
    with pytest.raises(ValueError):
        create_llm_client(Settings(llm_provider="unknown"))


def test_cost_uses_prices_from_settings() -> None:
    settings = Settings(
        llm_input_price_per_million_tokens=2.0, llm_output_price_per_million_tokens=10.0
    )
    assert calculate_cost_usd(1_000_000, 100_000, settings) == pytest.approx(3.0)
