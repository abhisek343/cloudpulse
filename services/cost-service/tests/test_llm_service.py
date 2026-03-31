"""Tests for LLM service provider integrations."""

from types import SimpleNamespace

import httpx
import pytest

from app.services.llm_service import LLMService


class FakeAsyncResponse:
    """Minimal async HTTP response test double."""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    """Async client test double for OpenRouter requests."""

    def __init__(self, response: FakeAsyncResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, *, headers: dict, json: dict) -> FakeAsyncResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.response


@pytest.mark.asyncio
async def test_openrouter_uses_direct_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenRouter requests should bypass LiteLLM and hit the native API."""
    service = LLMService()
    service.provider = "openrouter"
    service.model = "openrouter/free"
    service.api_key = "test-key"
    service.base_url = "https://openrouter.ai/api/v1"

    fake_client = FakeAsyncClient(
        FakeAsyncResponse(
            {
                "choices": [
                    {"message": {"content": "Synthetic OpenRouter reply"}}
                ]
            }
        )
    )

    def fake_async_client(*args, **kwargs) -> FakeAsyncClient:
        del args, kwargs
        return fake_client

    monkeypatch.setattr("app.services.llm_service.httpx.AsyncClient", fake_async_client)

    response = await service.get_chat_response("What changed in my costs?", {"total_cost": 123.45})

    assert response == "Synthetic OpenRouter reply"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert fake_client.calls[0]["json"]["model"] == "openrouter/free"
    assert fake_client.calls[0]["headers"]["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
async def test_non_openrouter_uses_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Other providers should continue using LiteLLM."""
    service = LLMService()
    service.provider = "openai"
    service.model = "gpt-4o-mini"
    service.api_key = "test-key"
    service.base_url = "https://api.openai.com/v1"

    captured: dict = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="LiteLLM reply"))]
        )

    monkeypatch.setattr("app.services.llm_service.completion", fake_completion)

    response = await service.get_chat_response("Summarize this.", {"total_cost": 88})

    assert response == "LiteLLM reply"
    assert captured["model"] == "gpt-4o-mini"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://api.openai.com/v1"
