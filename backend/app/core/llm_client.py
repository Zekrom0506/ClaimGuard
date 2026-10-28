"""A small wrapper around language model providers.

Every part of ClaimGuard talks to `LLMClient`, never to a provider's SDK
directly. Switching from the Claude API to a local model (Ollama) is then a
one-line settings change, and tests can plug in `FakeLLMClient`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import anthropic
import httpx

from app.core.config import Settings

OLLAMA_CONTEXT_TOKENS = 8192


class LLMError(Exception):
    """The language model could not be reached or returned nothing usable."""


@dataclass
class LLMResponse:
    """The text the model returned plus token counts for cost tracking."""

    text: str
    model_name: str
    input_tokens: int
    output_tokens: int


@dataclass
class SentPrompt:
    """A record of one call, kept by test and evaluation clients."""

    task_name: str
    system_prompt: str
    user_prompt: str


class LLMClient(ABC):
    """Common interface for every provider."""

    model_name: str

    @abstractmethod
    def complete(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        """Send one prompt and return the model's answer.

        `task_name` ("extraction", "verdict", ...) is used for logging and by the
        fake client to pick the right recorded response.
        """


class AnthropicLLMClient(LLMClient):
    """Calls the Claude API."""

    def __init__(self, api_key: str, model_name: str) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._sdk_client: anthropic.Anthropic | None = None

    def _get_sdk_client(self) -> anthropic.Anthropic:
        """Create the SDK client on first use, so the API can start without a key."""
        if self._api_key == "":
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        if self._sdk_client is None:
            self._sdk_client = anthropic.Anthropic(api_key=self._api_key, max_retries=2)
        return self._sdk_client

    def complete(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        """Send the prompt to Claude. Sampling settings are left at their defaults."""
        try:
            message = self._get_sdk_client().messages.create(
                model=self.model_name,
                max_tokens=max_output_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except anthropic.APIError as error:
            raise LLMError(f"Claude API call failed: {type(error).__name__}") from error

        answer_parts = []
        for content_block in message.content:
            if content_block.type == "text":
                answer_parts.append(content_block.text)
        return LLMResponse(
            text="".join(answer_parts),
            model_name=self.model_name,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


class OllamaLLMClient(LLMClient):
    """Calls a local model through Ollama, so no text leaves the machine."""

    def __init__(self, base_url: str, model_name: str) -> None:
        self.model_name = model_name
        self._base_url = base_url.rstrip("/")

    def complete(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        """Send the prompt to Ollama's chat endpoint."""
        request_body = {
            "model": self.model_name,
            "stream": False,
            # Ollama's default context window can be as small as 2048 tokens and it
            # silently drops anything beyond it; the verdict prompt alone is ~1,800.
            "options": {"num_predict": max_output_tokens, "num_ctx": OLLAMA_CONTEXT_TOKENS},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = httpx.post(f"{self._base_url}/api/chat", json=request_body, timeout=300)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise LLMError(f"Ollama call failed: {type(error).__name__}") from error

        body = response.json()
        return LLMResponse(
            text=body["message"]["content"],
            model_name=self.model_name,
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
        )


class FakeLLMClient(LLMClient):
    """Returns recorded responses instead of calling a real model.

    Used in tests and CI: free, fast, and gives the same answer every time.
    It also remembers every prompt it received, which the privacy test checks.
    """

    def __init__(self, recorded_responses: dict[str, list[str]]) -> None:
        self.model_name = "fake-llm"
        self.recorded_responses = recorded_responses
        self.sent_prompts: list[SentPrompt] = []
        self._next_index_by_task: dict[str, int] = {}

    def complete(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        """Return the next recorded response for this task (the last one repeats)."""
        self.sent_prompts.append(SentPrompt(task_name, system_prompt, user_prompt))
        responses_for_task = self.recorded_responses.get(task_name)
        if not responses_for_task:
            raise LLMError(f"No recorded response for task '{task_name}'.")

        next_index = self._next_index_by_task.get(task_name, 0)
        self._next_index_by_task[task_name] = next_index + 1
        if next_index >= len(responses_for_task):
            next_index = len(responses_for_task) - 1
        return LLMResponse(
            text=responses_for_task[next_index],
            model_name=self.model_name,
            input_tokens=len(user_prompt) // 4,
            output_tokens=len(responses_for_task[next_index]) // 4,
        )


class RecordingLLMClient(LLMClient):
    """Wraps a real client and keeps a copy of every prompt sent through it.

    The evaluation uses this to prove no private details reached the model.
    """

    def __init__(self, inner_client: LLMClient) -> None:
        self.inner_client = inner_client
        self.model_name = inner_client.model_name
        self.sent_prompts: list[SentPrompt] = []

    def complete(
        self,
        task_name: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        """Record the prompt, then pass the call on."""
        self.sent_prompts.append(SentPrompt(task_name, system_prompt, user_prompt))
        return self.inner_client.complete(task_name, system_prompt, user_prompt, max_output_tokens)


def create_llm_client(settings: Settings) -> LLMClient:
    """Build the client chosen by the LLM_PROVIDER setting."""
    if settings.llm_provider == "anthropic":
        return AnthropicLLMClient(settings.anthropic_api_key, settings.llm_model_name)
    if settings.llm_provider == "ollama":
        return OllamaLLMClient(settings.ollama_base_url, settings.llm_model_name)
    raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'.")


def calculate_cost_usd(input_tokens: int, output_tokens: int, settings: Settings) -> float:
    """Estimated cost of the tokens used, from the per-million prices in settings."""
    input_cost = input_tokens / 1_000_000 * settings.llm_input_price_per_million_tokens
    output_cost = output_tokens / 1_000_000 * settings.llm_output_price_per_million_tokens
    return round(input_cost + output_cost, 6)
