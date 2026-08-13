"""Contract tests for the fail-closed local Helm Ollama preview adapter."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from dharma_swarm.tui.engine.adapters.base import CompletionRequest
from dharma_swarm.tui.engine.adapters.ollama import (
    OLLAMA_LOCAL_PREVIEW_BASE_URL,
    OLLAMA_LOCAL_PREVIEW_ENV,
    OllamaAdapter,
)
from dharma_swarm.tui.engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
)

MODEL = "mistral:latest"


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any, *, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.posts: list[dict[str, Any]] = []
        self.exit_count = 0

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1

    async def post(self, url: str, *, json: dict[str, Any]) -> _FakeResponse:
        self.posts.append({"url": url, "json": json})
        return self.response


class _BlockingClient(_FakeClient):
    def __init__(self) -> None:
        super().__init__(_FakeResponse(200, {}))
        self.post_started = asyncio.Event()
        self.post_cancelled = asyncio.Event()
        self.exited = asyncio.Event()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await super().__aexit__(exc_type, exc, tb)
        self.exited.set()

    async def post(self, url: str, *, json: dict[str, Any]) -> _FakeResponse:
        self.posts.append({"url": url, "json": json})
        self.post_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.post_cancelled.set()
            raise


def _request(**overrides: Any) -> CompletionRequest:
    fields: dict[str, Any] = {
        "messages": [{"role": "user", "content": "hello"}],
        "model": MODEL,
        "system_prompt": "Stay local and return text only.",
        "tools": [],
        "tool_choice": "none",
    }
    fields.update(overrides)
    return CompletionRequest(**fields)


def _success_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": MODEL,
        "message": {"role": "assistant", "content": "local reply"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 8,
        "eval_count": 3,
    }
    payload.update(overrides)
    return payload


async def _collect(
    adapter: OllamaAdapter,
    request: CompletionRequest | None = None,
) -> list[object]:
    return [
        event
        async for event in adapter.stream(request or _request(), session_id="sid-local")
    ]


def _enable(monkeypatch: pytest.MonkeyPatch, model: str = MODEL) -> None:
    monkeypatch.setenv(OLLAMA_LOCAL_PREVIEW_ENV, model)


def _assert_failed_before_route_evidence(
    events: list[object],
    expected_code: str,
) -> None:
    assert [type(event) for event in events] == [ErrorEvent, SessionEnd]
    error, end = events
    assert isinstance(error, ErrorEvent)
    assert isinstance(end, SessionEnd)
    assert error.code == end.error_code == expected_code
    assert end.success is False
    assert not any(isinstance(event, SessionStart) for event in events)
    assert not any(isinstance(event, TextComplete) for event in events)
    assert not any(isinstance(event, UsageReport) for event in events)


def test_ollama_adapter_requires_explicit_exact_preview_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(OLLAMA_LOCAL_PREVIEW_ENV, raising=False)
    with pytest.raises(RuntimeError, match=OLLAMA_LOCAL_PREVIEW_ENV):
        OllamaAdapter(model_id=MODEL)

    _enable(monkeypatch)
    with pytest.raises(ValueError, match="exactly match"):
        OllamaAdapter(model_id="llama3.2:latest")
    with pytest.raises(ValueError, match="invalid"):
        OllamaAdapter(model_id="mistral:latest\nhttps://remote.invalid")


@pytest.mark.asyncio
async def test_ollama_adapter_has_one_exact_non_seat_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    adapter = OllamaAdapter(model_id=MODEL)

    profiles = await adapter.list_models()

    assert profiles == [adapter.get_profile()]
    assert profiles[0].model_id == MODEL
    assert profiles[0].extra == {
        "base_url": OLLAMA_LOCAL_PREVIEW_BASE_URL,
        "local_preview": True,
        "seat_evidence": False,
    }
    assert profiles[0].supports(profiles[0].capabilities)
    with pytest.raises(KeyError):
        adapter.get_profile("different:latest")


@pytest.mark.asyncio
async def test_ollama_adapter_seals_loopback_client_payload_and_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    client = _FakeClient(_FakeResponse(200, _success_payload()))
    client_kwargs: list[dict[str, Any]] = []

    def client_factory(**kwargs: Any) -> _FakeClient:
        client_kwargs.append(kwargs)
        return client

    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.ollama.httpx.AsyncClient",
        client_factory,
    )
    adapter = OllamaAdapter(model_id=MODEL)

    events = await _collect(adapter)

    assert client_kwargs == [
        {"timeout": 120.0, "trust_env": False, "follow_redirects": False}
    ]
    assert client.posts == [
        {
            "url": "http://127.0.0.1:11434/api/chat",
            "json": {
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Stay local and return text only.",
                    },
                    {"role": "user", "content": "hello"},
                ],
                "stream": False,
            },
        }
    ]
    payload = client.posts[0]["json"]
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert "api_key" not in payload

    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    start, text, usage, end = events
    assert isinstance(start, SessionStart)
    assert start.model == MODEL
    assert start.tools_available == []
    assert start.system_info == {
        "base_url": OLLAMA_LOCAL_PREVIEW_BASE_URL,
        "local_preview": True,
        "requested_model": MODEL,
        "seat_evidence": False,
        "served_identity_source": "response.model",
        "transport_mode": "local_api",
    }
    assert isinstance(text, TextComplete) and text.content == "local reply"
    assert isinstance(usage, UsageReport)
    assert usage.input_tokens == 8
    assert usage.output_tokens == 3
    assert isinstance(end, SessionEnd) and end.success
    assert client.exit_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("completion", "expected_code"),
    [
        (_request(model="other:latest"), "model_mismatch"),
        (_request(tools=[{"type": "function"}]), "tools_rejected"),
        (_request(tool_choice="auto"), "tools_rejected"),
        (_request(tool_choice={"type": "function"}), "tools_rejected"),
        (_request(enable_thinking=True), "thinking_rejected"),
        (_request(resume_session_id="prior"), "resume_rejected"),
        (_request(provider_options={"base_url": "https://remote.invalid"}), "provider_options_rejected"),
        (_request(provider_options={"api_key": "do-not-use"}), "provider_options_rejected"),
        (_request(provider_options={"require_served_identity": False}), "provider_options_rejected"),
        (_request(provider_options={"require_served_identity": {}}), "provider_options_rejected"),
        (_request(messages=[{"role": "tool", "content": "unsafe"}]), "invalid_messages"),
        (_request(max_tokens=-1), "invalid_generation_options"),
        (_request(temperature=float("nan")), "invalid_generation_options"),
    ],
)
async def test_ollama_adapter_rejects_authority_and_transport_overrides(
    monkeypatch: pytest.MonkeyPatch,
    completion: CompletionRequest,
    expected_code: str,
) -> None:
    _enable(monkeypatch)
    adapter = OllamaAdapter(model_id=MODEL)

    events = await _collect(adapter, completion)

    _assert_failed_before_route_evidence(events, expected_code)


@pytest.mark.asyncio
async def test_ollama_adapter_rechecks_capability_gate_each_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    adapter = OllamaAdapter(model_id=MODEL)
    monkeypatch.delenv(OLLAMA_LOCAL_PREVIEW_ENV)

    events = await _collect(adapter)

    _assert_failed_before_route_evidence(events, "preview_gate_closed")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (None, "malformed_response"),
        ({"model": MODEL, "message": {}, "done": True}, "malformed_response"),
        (_success_payload(model="llama3.2:latest"), "model_mismatch"),
        (_success_payload(done=False), "malformed_response"),
        (_success_payload(error="secret provider detail"), "provider_response_error"),
        (
            _success_payload(
                message={
                    "role": "assistant",
                    "content": "must not escape",
                    "tool_calls": [{"function": {"name": "shell"}}],
                }
            ),
            "provider_tool_use_rejected",
        ),
        (_success_payload(tool_calls=[{"id": "hidden"}]), "provider_tool_use_rejected"),
        (_success_payload(done_reason="tool_calls"), "provider_tool_use_rejected"),
        (
            _success_payload(message={"role": "assistant", "content": "   "}),
            "empty_response",
        ),
        (_success_payload(prompt_eval_count=-1), "malformed_response"),
    ],
)
async def test_ollama_adapter_rejects_unproven_or_unsafe_responses_before_start(
    monkeypatch: pytest.MonkeyPatch,
    payload: Any,
    expected_code: str,
) -> None:
    _enable(monkeypatch)
    client = _FakeClient(_FakeResponse(200, payload))
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.ollama.httpx.AsyncClient",
        lambda **kwargs: client,
    )
    adapter = OllamaAdapter(model_id=MODEL)

    events = await _collect(adapter)

    _assert_failed_before_route_evidence(events, expected_code)


@pytest.mark.asyncio
async def test_ollama_adapter_rejects_redirect_without_following(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    client = _FakeClient(
        _FakeResponse(307, {}, text="https://credential@example.invalid/secret")
    )
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.ollama.httpx.AsyncClient",
        lambda **kwargs: client,
    )
    adapter = OllamaAdapter(model_id=MODEL)

    events = await _collect(adapter)

    _assert_failed_before_route_evidence(events, "redirect_rejected")
    rendered = repr(events)
    assert "example.invalid" not in rendered
    assert "credential" not in rendered


@pytest.mark.asyncio
async def test_ollama_adapter_sanitizes_http_and_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    secret = "super-secret-response-body"
    client = _FakeClient(_FakeResponse(500, {}, text=secret))
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.ollama.httpx.AsyncClient",
        lambda **kwargs: client,
    )
    adapter = OllamaAdapter(model_id=MODEL)

    events = await _collect(adapter)

    _assert_failed_before_route_evidence(events, "http_500")
    assert secret not in repr(events)

    class _FailingClient(_FakeClient):
        async def post(self, url: str, *, json: dict[str, Any]) -> _FakeResponse:
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("credential=also-secret", request=request)

    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.ollama.httpx.AsyncClient",
        lambda **kwargs: _FailingClient(_FakeResponse(200, {})),
    )
    events = await _collect(adapter)
    _assert_failed_before_route_evidence(events, "transport_error")
    assert "also-secret" not in repr(events)


@pytest.mark.asyncio
async def test_ollama_adapter_cancel_interrupts_request_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    client = _BlockingClient()
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.ollama.httpx.AsyncClient",
        lambda **kwargs: client,
    )
    adapter = OllamaAdapter(model_id=MODEL)

    collector = asyncio.create_task(_collect(adapter))
    await asyncio.wait_for(client.post_started.wait(), timeout=1)
    request_task = adapter._active_request_task
    assert request_task is not None

    await adapter.cancel()
    events = await asyncio.wait_for(collector, timeout=1)
    await adapter.cancel()
    await adapter.close()

    assert client.post_cancelled.is_set()
    assert client.exited.is_set()
    assert client.exit_count == 1
    assert request_task.cancelled()
    assert adapter._active_request_task is None
    assert [type(event) for event in events] == [SessionEnd]
    end = events[0]
    assert isinstance(end, SessionEnd)
    assert end.success is False
    assert end.error_code == "cancelled"
