import json
import math
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol, Sequence, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_OUTPUT_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)


MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported LLM message role: {self.role}")
        if not self.content.strip():
            raise ValueError("LLM message content cannot be empty")


@dataclass(frozen=True, slots=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class LLMResult:
    content: str
    provider: str
    model: str
    usage: LLMUsage
    duration_ms: int
    finish_reason: str | None = None


class LLMProviderError(RuntimeError):
    """Raised when a provider cannot generate a valid response."""


@runtime_checkable
class LLMProvider(Protocol):
    provider_name: str
    model: str

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_OUTPUT_TOKENS,
    ) -> LLMResult:
        """Generate one non-streaming response for a normalized message list."""


class FakeLLMProvider:
    """Deterministic local provider used to test orchestration without network calls."""

    provider_name = "fake"

    def __init__(self, model: str = "opsmind-fake") -> None:
        self.model = model

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_OUTPUT_TOKENS,
    ) -> LLMResult:
        _validate_generation_input(messages, temperature, max_tokens)
        started_at = perf_counter()
        user_message = next((message.content for message in reversed(messages) if message.role == "user"), None)
        if user_message is None:
            raise LLMProviderError("At least one user message is required")

        raw_content = f"[fake response] {user_message}"
        content = raw_content[: max_tokens * 4]
        prompt_tokens = sum(_estimate_tokens(message.content) for message in messages)
        completion_tokens = _estimate_tokens(content)
        return LLMResult(
            content=content,
            provider=self.provider_name,
            model=self.model,
            usage=LLMUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
            duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
            finish_reason="length" if len(content) < len(raw_content) else "stop",
        )


class OpenAICompatibleLLMProvider:
    """Non-streaming provider for OpenAI-compatible chat completion APIs."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = LLM_TIMEOUT_SECONDS,
    ) -> None:
        normalized_model = model.strip()
        normalized_base_url = base_url.strip().rstrip("/")
        if not normalized_model:
            raise ValueError("LLM model cannot be empty")
        if not normalized_base_url:
            raise ValueError("LLM base URL cannot be empty")
        parsed_url = urlparse(normalized_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("LLM base URL must be an absolute HTTP or HTTPS URL")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("LLM timeout must be a positive finite number")

        self.model = normalized_model
        self.base_url = normalized_base_url
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_OUTPUT_TOKENS,
    ) -> LLMResult:
        _validate_generation_input(messages, temperature, max_tokens)
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        started_at = perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read()
        except HTTPError as error:
            raise LLMProviderError(
                f"LLM provider returned HTTP status {error.code}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise LLMProviderError("LLM provider request failed") from error

        duration_ms = max(0, round((perf_counter() - started_at) * 1000))
        try:
            response_data = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMProviderError("LLM provider returned invalid JSON") from error
        return _parse_openai_compatible_response(response_data, self.model, duration_ms)


def get_llm_provider(provider_name: str | None = None, model: str | None = None) -> LLMProvider:
    selected_provider = (provider_name or LLM_PROVIDER).strip().lower()
    selected_model = (model or LLM_MODEL).strip()
    if not selected_model:
        raise ValueError("LLM model cannot be empty")
    if selected_provider == "fake":
        return FakeLLMProvider(model=selected_model)
    if selected_provider == "openai_compatible":
        if LLM_BASE_URL is None:
            raise ValueError("LLM_BASE_URL is required for the openai_compatible provider")
        return OpenAICompatibleLLMProvider(
            model=selected_model,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            timeout_seconds=LLM_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unsupported LLM provider: {selected_provider}")


def _validate_generation_input(
    messages: Sequence[LLMMessage],
    temperature: float,
    max_tokens: int,
) -> None:
    if not messages:
        raise ValueError("At least one LLM message is required")
    if not 0 <= temperature <= 2:
        raise ValueError("LLM temperature must be between 0 and 2")
    if max_tokens <= 0:
        raise ValueError("LLM max_tokens must be greater than 0")


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _parse_openai_compatible_response(
    response_data: object,
    fallback_model: str,
    duration_ms: int,
) -> LLMResult:
    if not isinstance(response_data, dict):
        raise LLMProviderError("LLM provider response must be a JSON object")

    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LLMProviderError("LLM provider response does not contain a valid choice")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise LLMProviderError("LLM provider response does not contain a valid message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMProviderError("LLM provider response contains empty message content")

    usage_data = response_data.get("usage", {})
    if not isinstance(usage_data, dict):
        raise LLMProviderError("LLM provider response contains invalid token usage")
    prompt_tokens = _read_token_count(usage_data, "prompt_tokens")
    completion_tokens = _read_token_count(usage_data, "completion_tokens")

    response_model = response_data.get("model")
    model = response_model.strip() if isinstance(response_model, str) and response_model.strip() else fallback_model
    finish_reason = choice.get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        raise LLMProviderError("LLM provider response contains invalid finish reason")

    return LLMResult(
        content=content.strip(),
        provider="openai_compatible",
        model=model,
        usage=LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
        duration_ms=duration_ms,
        finish_reason=finish_reason,
    )


def _read_token_count(usage_data: dict[object, object], field: str) -> int:
    value = usage_data.get(field, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LLMProviderError(f"LLM provider response contains invalid {field}")
    return value
