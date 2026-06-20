import json
from urllib.error import HTTPError

import pytest

from app.services import llm_provider as llm_provider_module
from app.services.llm_provider import (
    FakeLLMProvider,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
    get_llm_provider,
)


class FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_fake_provider_returns_normalized_result() -> None:
    provider = FakeLLMProvider(model="test-model")

    result = provider.generate(
        [
            LLMMessage(role="system", content="只根据 Wiki 回答。"),
            LLMMessage(role="user", content="如何排查数据库延迟？"),
        ],
        temperature=0,
        max_tokens=100,
    )

    assert isinstance(provider, LLMProvider)
    assert result.content == "[fake response] 如何排查数据库延迟？"
    assert result.provider == "fake"
    assert result.model == "test-model"
    assert result.usage.prompt_tokens > 0
    assert result.usage.total_tokens >= result.usage.prompt_tokens
    assert result.finish_reason == "stop"


def test_fake_provider_requires_user_message() -> None:
    provider = FakeLLMProvider()

    with pytest.raises(LLMProviderError, match="user message"):
        provider.generate([LLMMessage(role="system", content="系统提示")])


@pytest.mark.parametrize(
    ("temperature", "max_tokens", "message"),
    [
        (-0.1, 100, "temperature"),
        (2.1, 100, "temperature"),
        (0.2, 0, "max_tokens"),
    ],
)
def test_fake_provider_validates_generation_parameters(
    temperature: float,
    max_tokens: int,
    message: str,
) -> None:
    provider = FakeLLMProvider()

    with pytest.raises(ValueError, match=message):
        provider.generate(
            [LLMMessage(role="user", content="测试问题")],
            temperature=temperature,
            max_tokens=max_tokens,
        )


def test_provider_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider(provider_name="unknown", model="test-model")


def test_message_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        LLMMessage(role="user", content="   ")


def test_message_rejects_unsupported_role() -> None:
    with pytest.raises(ValueError, match="Unsupported LLM message role"):
        LLMMessage(role="tool", content="工具结果")  # type: ignore[arg-type]


def test_fake_provider_honors_max_tokens() -> None:
    result = FakeLLMProvider().generate(
        [LLMMessage(role="user", content="这是一个足够长的测试问题")],
        max_tokens=2,
    )

    assert len(result.content) <= 8
    assert result.usage.completion_tokens <= 2
    assert result.finish_reason == "length"


def test_openai_compatible_provider_sends_request_and_parses_response(monkeypatch) -> None:
    captured = {}
    response_body = json.dumps(
        {
            "model": "served-model-v2",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "  Wiki 回答。[Wiki:1]  "},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 42, "completion_tokens": 9, "total_tokens": 51},
        },
        ensure_ascii=False,
    ).encode("utf-8")

    def fake_urlopen(request, *, timeout):
        captured.update(request=request, timeout=timeout)
        return FakeHTTPResponse(response_body)

    monkeypatch.setattr(llm_provider_module, "urlopen", fake_urlopen)
    provider = OpenAICompatibleLLMProvider(
        model="configured-model",
        base_url="http://127.0.0.1:9000/v1/",
        api_key="test-key",
        timeout_seconds=15,
    )

    result = provider.generate(
        [
            LLMMessage(role="system", content="只根据 Wiki 回答。"),
            LLMMessage(role="user", content="如何排查？"),
        ],
        temperature=0.1,
        max_tokens=300,
    )

    request = captured["request"]
    request_payload = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "http://127.0.0.1:9000/v1/chat/completions"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert captured["timeout"] == 15
    assert request_payload == {
        "model": "configured-model",
        "messages": [
            {"role": "system", "content": "只根据 Wiki 回答。"},
            {"role": "user", "content": "如何排查？"},
        ],
        "temperature": 0.1,
        "max_tokens": 300,
    }
    assert result.content == "Wiki 回答。[Wiki:1]"
    assert result.provider == "openai_compatible"
    assert result.model == "served-model-v2"
    assert result.usage.total_tokens == 51
    assert result.finish_reason == "stop"


def test_openai_compatible_provider_omits_authorization_without_key(monkeypatch) -> None:
    response_body = b'{"choices":[{"message":{"content":"answer"}}]}'

    def fake_urlopen(request, *, timeout):
        assert request.get_header("Authorization") is None
        return FakeHTTPResponse(response_body)

    monkeypatch.setattr(llm_provider_module, "urlopen", fake_urlopen)
    provider = OpenAICompatibleLLMProvider(
        model="local-model",
        base_url="http://127.0.0.1:9000/v1",
    )

    result = provider.generate([LLMMessage(role="user", content="test")])

    assert result.model == "local-model"
    assert result.usage.total_tokens == 0


def test_openai_compatible_provider_converts_http_error_without_body(monkeypatch) -> None:
    def fake_urlopen(request, *, timeout):
        raise HTTPError(request.full_url, 429, "rate limited: secret-body", None, None)

    monkeypatch.setattr(llm_provider_module, "urlopen", fake_urlopen)
    provider = OpenAICompatibleLLMProvider(
        model="test-model",
        base_url="https://llm.example.test/v1",
        api_key="secret-key",
    )

    with pytest.raises(LLMProviderError, match="HTTP status 429") as captured:
        provider.generate([LLMMessage(role="user", content="test")])

    assert "secret-key" not in str(captured.value)
    assert "secret-body" not in str(captured.value)


@pytest.mark.parametrize(
    ("response_body", "message"),
    [
        (b"not-json", "invalid JSON"),
        (b"{}", "valid choice"),
        (b'{"choices":[{"message":{"content":""}}]}', "empty message content"),
        (
            b'{"choices":[{"message":{"content":"answer"}}],"usage":{"prompt_tokens":-1}}',
            "invalid prompt_tokens",
        ),
    ],
)
def test_openai_compatible_provider_rejects_invalid_response(
    monkeypatch,
    response_body: bytes,
    message: str,
) -> None:
    monkeypatch.setattr(
        llm_provider_module,
        "urlopen",
        lambda request, *, timeout: FakeHTTPResponse(response_body),
    )
    provider = OpenAICompatibleLLMProvider(
        model="test-model",
        base_url="https://llm.example.test/v1",
    )

    with pytest.raises(LLMProviderError, match=message):
        provider.generate([LLMMessage(role="user", content="test")])


@pytest.mark.parametrize(
    ("base_url", "timeout", "message"),
    [
        ("", 60, "base URL cannot be empty"),
        ("localhost:9000/v1", 60, "absolute HTTP"),
        ("ftp://localhost/v1", 60, "absolute HTTP"),
        ("http://localhost/v1", 0, "positive finite"),
    ],
)
def test_openai_compatible_provider_validates_configuration(
    base_url: str,
    timeout: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        OpenAICompatibleLLMProvider(
            model="test-model",
            base_url=base_url,
            timeout_seconds=timeout,
        )


def test_provider_factory_builds_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.setattr(llm_provider_module, "LLM_BASE_URL", "http://localhost:9000/v1")
    monkeypatch.setattr(llm_provider_module, "LLM_API_KEY", "factory-key")
    monkeypatch.setattr(llm_provider_module, "LLM_TIMEOUT_SECONDS", 20)

    provider = get_llm_provider(provider_name="openai_compatible", model="factory-model")

    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.model == "factory-model"
    assert provider.api_key == "factory-key"
    assert provider.timeout_seconds == 20
