"""Tests for OpenRouter adapter canonical event flow."""

from __future__ import annotations

import asyncio

import pytest

from dharma_swarm import model_pool
from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType
from dharma_swarm.tui.engine.adapters.base import CompletionRequest, ProviderConfig
from dharma_swarm.tui.engine.adapters.openrouter import OpenRouterAdapter
from dharma_swarm.tui.engine.events import ErrorEvent, SessionEnd, TextComplete, UsageReport


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.exit_count = 0

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1
        return None

    async def post(self, url: str, headers: dict, json: dict) -> _FakeResponse:
        return self._response


class _BlockingClient:
    def __init__(self) -> None:
        self.post_started = asyncio.Event()
        self.post_cancelled = asyncio.Event()
        self.exited = asyncio.Event()
        self.exit_count = 0

    async def __aenter__(self) -> "_BlockingClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1
        self.exited.set()
        return None

    async def post(self, url: str, headers: dict, json: dict) -> _FakeResponse:
        self.post_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.post_cancelled.set()
            raise


async def _collect_events(adapter: OpenRouterAdapter) -> list[object]:
    request = CompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="openai/gpt-5-codex",
    )
    events: list[object] = []
    async for ev in adapter.stream(request, session_id="sid-1"):
        events.append(ev)
    return events


def test_openrouter_adapter_defaults_to_canonical_runtime_model() -> None:
    adapter = OpenRouterAdapter()
    profile = adapter.get_profile()

    assert profile.model_id == DEFAULT_MODELS[ProviderType.OPENROUTER]


def test_openrouter_profiles_project_the_pool_gemini_3_route() -> None:
    entry = model_pool.get_entry("gemini-3-pro")
    assert entry is not None
    expected = next(
        route.model_id
        for route in entry.routes
        if route.provider is ProviderType.OPENROUTER
    )

    adapter = OpenRouterAdapter()

    assert adapter.get_profile(expected).model_id == expected
    assert expected in {profile.model_id for profile in asyncio.run(adapter.list_models())}


@pytest.mark.asyncio
async def test_openrouter_missing_api_key_emits_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    adapter = OpenRouterAdapter(
        ProviderConfig(provider_id="openrouter", api_key=None)
    )

    events = await _collect_events(adapter)

    assert any(
        isinstance(ev, ErrorEvent) and ev.code == "missing_api_key" for ev in events
    )
    assert any(
        isinstance(ev, SessionEnd) and (not ev.success) for ev in events
    )


@pytest.mark.asyncio
async def test_openrouter_success_emits_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _FakeResponse(
        200,
        {
            "choices": [{"message": {"content": "hi from model"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_cost": 0.02},
        },
    )
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.openrouter.httpx.AsyncClient",
        lambda timeout: _FakeClient(response),
    )
    adapter = OpenRouterAdapter(
        ProviderConfig(provider_id="openrouter", api_key="test-key")
    )

    events = await _collect_events(adapter)

    assert any(
        isinstance(ev, TextComplete) and ev.content == "hi from model"
        for ev in events
    )
    assert any(
        isinstance(ev, UsageReport) and ev.total_cost_usd == 0.02 for ev in events
    )
    assert any(isinstance(ev, SessionEnd) and ev.success for ev in events)


@pytest.mark.asyncio
async def test_openrouter_success_emits_reasoning_when_content_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(
        200,
        {
            "choices": [{
                "message": {
                    "content": None,
                    "reasoning": "hi from reasoning",
                }
            }],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_cost": 0.02},
        },
    )
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.openrouter.httpx.AsyncClient",
        lambda timeout: _FakeClient(response),
    )
    adapter = OpenRouterAdapter(
        ProviderConfig(provider_id="openrouter", api_key="test-key")
    )

    events = await _collect_events(adapter)

    assert any(
        isinstance(ev, TextComplete) and ev.content == "hi from reasoning"
        for ev in events
    )
    assert any(isinstance(ev, SessionEnd) and ev.success for ev in events)


@pytest.mark.asyncio
async def test_openrouter_http_429_marks_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _FakeResponse(
        429,
        {},
        text="rate limit",
    )
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.openrouter.httpx.AsyncClient",
        lambda timeout: _FakeClient(response),
    )
    adapter = OpenRouterAdapter(
        ProviderConfig(provider_id="openrouter", api_key="test-key")
    )

    events = await _collect_events(adapter)

    err = next((ev for ev in events if isinstance(ev, ErrorEvent)), None)
    assert isinstance(err, ErrorEvent)
    assert err.code == "rate_limited"
    assert err.retryable is True
    assert any(
        isinstance(ev, SessionEnd) and (not ev.success) and ev.error_code == "rate_limited"
        for ev in events
    )


@pytest.mark.asyncio
async def test_openrouter_cancel_interrupts_http_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _BlockingClient()
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.openrouter.httpx.AsyncClient",
        lambda timeout: client,
    )
    adapter = OpenRouterAdapter(
        ProviderConfig(provider_id="openrouter", api_key="test-key")
    )

    collector = asyncio.create_task(_collect_events(adapter))
    await asyncio.wait_for(client.post_started.wait(), timeout=1)
    request_task = adapter._active_request_task
    assert request_task is not None

    await adapter.cancel()
    assert adapter._active_request_task is None
    assert client.exited.is_set()
    await adapter.cancel()
    await adapter.close()
    events = await asyncio.wait_for(collector, timeout=1)

    assert client.post_cancelled.is_set()
    assert client.exited.is_set()
    assert client.exit_count == 1
    assert request_task.cancelled()
    assert adapter._active_request_task is None
    assert not any(isinstance(ev, TextComplete) for ev in events)
    ends = [ev for ev in events if isinstance(ev, SessionEnd)]
    assert len(ends) == 1
    assert ends[0].success is False
    assert ends[0].error_code == "cancelled"


@pytest.mark.asyncio
async def test_openrouter_cancel_before_http_start_skips_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_created = False

    def make_client(timeout: float) -> _BlockingClient:
        nonlocal client_created
        client_created = True
        return _BlockingClient()

    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.openrouter.httpx.AsyncClient",
        make_client,
    )
    adapter = OpenRouterAdapter(
        ProviderConfig(provider_id="openrouter", api_key="test-key")
    )
    request = CompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="openai/gpt-5-codex",
    )
    stream = adapter.stream(request, session_id="sid-before-http")

    await anext(stream)
    await adapter.cancel()
    remaining = [event async for event in stream]

    assert client_created is False
    assert len(remaining) == 1
    assert isinstance(remaining[0], SessionEnd)
    assert remaining[0].error_code == "cancelled"
    assert adapter._active_request_task is None
