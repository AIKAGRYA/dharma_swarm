"""Adversarial tests for the sealed Grok OAuth Responses adapter."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from dharma_swarm.tui.engine.adapters import grok_oauth
from dharma_swarm.tui.engine.adapters.base import CompletionRequest, ProviderConfig
from dharma_swarm.tui.engine.adapters.grok_oauth import GrokOAuthResponsesAdapter
from dharma_swarm.tui.engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
)

REQUESTED_MODEL = "grok-4.6"
SERVED_MODEL = "grok-4.6-build"
OAUTH_TOKEN = "unit-test-oauth-access-token"


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        body: bytes,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = body
        self.headers = headers or {"content-type": "text/event-stream; charset=utf-8"}
        self.close_count = 0

    async def aiter_bytes(self):
        yield self.content

    async def aclose(self) -> None:
        self.close_count += 1


class _FakeClient:
    def __init__(
        self,
        response: _FakeResponse | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.exit_count = 0
        self.posts: list[dict[str, Any]] = []

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1
        return None

    def build_request(
        self, method: str, url: str, headers: dict, json: dict
    ) -> dict[str, Any]:
        assert method == "POST"
        self.posts.append({"url": url, "headers": headers, "json": json})
        return self.posts[-1]

    async def send(self, request: dict[str, Any], *, stream: bool) -> _FakeResponse:
        assert request is self.posts[-1]
        assert stream is True
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class _ClientFactory:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.client


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

    def build_request(
        self, method: str, url: str, headers: dict, json: dict
    ) -> dict[str, Any]:
        return {"method": method, "url": url, "headers": headers, "json": json}

    async def send(self, request: dict[str, Any], *, stream: bool) -> _FakeResponse:
        del request, stream
        self.post_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.post_cancelled.set()
            raise


class _GatedClient(_FakeClient):
    def __init__(self, response: _FakeResponse) -> None:
        super().__init__(response)
        self.post_started = asyncio.Event()
        self.release_response = asyncio.Event()

    async def send(self, request: dict[str, Any], *, stream: bool) -> _FakeResponse:
        assert request is self.posts[-1]
        assert stream is True
        self.post_started.set()
        await self.release_response.wait()
        assert self._response is not None
        return self._response


def _future_expiry() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def _write_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    payload: Any | None = None,
    mode: int = 0o600,
) -> Path:
    path = tmp_path / "grok-auth.json"
    auth = (
        {
            "account": {
                "key": OAUTH_TOKEN,
                "expires_at": _future_expiry(),
                "refresh_token": "must-never-be-used",
            }
        }
        if payload is None
        else payload
    )
    path.write_text(json.dumps(auth), encoding="utf-8")
    path.chmod(mode)
    monkeypatch.setattr(grok_oauth, "_GROK_AUTH_PATH", path)
    return path


def _response_object(content: str = "PONG") -> dict[str, Any]:
    return {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "model": SERVED_MODEL,
        "error": None,
        "incomplete_details": None,
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
        "store": False,
        "output": [
            {
                "id": "reasoning_test",
                "type": "reasoning",
                "status": "completed",
                "summary": [
                    {
                        "type": "summary_text",
                        "text": "The answer should be concise.",
                    }
                ],
            },
            {
                "id": "message_test",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": content,
                        "annotations": [],
                    }
                ],
            },
        ],
        "usage": {
            "input_tokens": 3,
            "input_tokens_details": {"cached_tokens": 1},
            "output_tokens": 2,
            "output_tokens_details": {"reasoning_tokens": 1},
            "total_tokens": 5,
            "num_server_side_tools_used": 0,
        },
    }


def _event(event_type: str, sequence: int, **values: Any) -> dict[str, Any]:
    return {"type": event_type, "sequence_number": sequence, **values}


def _success_events(
    *,
    content: str = "PONG",
    response: dict[str, Any] | None = None,
) -> list[tuple[str | None, Any]]:
    final = response if response is not None else _response_object(content)
    early_response = {
        "id": "resp_test",
        "status": "in_progress",
        "model": SERVED_MODEL,
        "parallel_tool_calls": False,
        "tools": [],
    }
    reasoning = {
        "id": "reasoning_test",
        "type": "reasoning",
        "status": "in_progress",
        "summary": [],
    }
    message = {
        "id": "message_test",
        "type": "message",
        "status": "in_progress",
        "role": "assistant",
        "content": [],
    }
    final_message = final["output"][1]
    output_part = {"type": "output_text", "text": content, "annotations": []}
    return [
        (
            "response.created",
            _event("response.created", 0, response=dict(early_response)),
        ),
        (
            "response.in_progress",
            _event("response.in_progress", 1, response=dict(early_response)),
        ),
        (
            "response.output_item.added",
            _event("response.output_item.added", 2, item=reasoning, output_index=0),
        ),
        (
            "response.reasoning_summary_part.added",
            _event(
                "response.reasoning_summary_part.added",
                3,
                part={"type": "summary_text", "text": ""},
            ),
        ),
        (
            "response.reasoning_summary_text.delta",
            _event(
                "response.reasoning_summary_text.delta",
                4,
                delta="The answer should be concise.",
            ),
        ),
        (
            "response.reasoning_summary_text.done",
            _event(
                "response.reasoning_summary_text.done",
                5,
                text="The answer should be concise.",
            ),
        ),
        (
            "response.reasoning_summary_part.done",
            _event(
                "response.reasoning_summary_part.done",
                6,
                part={
                    "type": "summary_text",
                    "text": "The answer should be concise.",
                },
            ),
        ),
        (
            "response.output_item.done",
            _event(
                "response.output_item.done",
                7,
                item=final["output"][0],
                output_index=0,
            ),
        ),
        (
            "response.output_item.added",
            _event("response.output_item.added", 8, item=message, output_index=1),
        ),
        (
            "response.content_part.added",
            _event(
                "response.content_part.added",
                9,
                part={"type": "output_text", "text": "", "annotations": []},
            ),
        ),
        (
            "response.output_text.delta",
            _event("response.output_text.delta", 10, delta=content),
        ),
        (
            "response.output_text.done",
            _event("response.output_text.done", 11, text=content),
        ),
        (
            "response.content_part.done",
            _event("response.content_part.done", 12, part=output_part),
        ),
        (
            "response.output_item.done",
            _event(
                "response.output_item.done",
                13,
                item=final_message,
                output_index=1,
            ),
        ),
        (
            "response.completed",
            _event("response.completed", 14, response=final),
        ),
        (None, "[DONE]"),
    ]


def _sse(events: list[tuple[str | None, Any]]) -> bytes:
    chunks: list[str] = []
    for event_name, data in events:
        if event_name is not None:
            chunks.append(f"event: {event_name}\n")
        encoded = (
            data if isinstance(data, str) else json.dumps(data, separators=(",", ":"))
        )
        chunks.append(f"data: {encoded}\n\n")
    return "".join(chunks).encode()


def _request(**overrides: Any) -> CompletionRequest:
    values: dict[str, Any] = {
        "messages": [{"role": "user", "content": "PING"}],
        "model": REQUESTED_MODEL,
        "tools": [],
        "tool_choice": "none",
    }
    values.update(overrides)
    return CompletionRequest(**values)


async def _collect(
    adapter: GrokOAuthResponsesAdapter,
    request: CompletionRequest | None = None,
    *,
    session_id: str = "grok-session",
) -> list[object]:
    return [
        event
        async for event in adapter.stream(request or _request(), session_id=session_id)
    ]


def _assert_failed_before_route_evidence(
    events: list[object],
    expected_code: str,
) -> None:
    assert [type(event) for event in events] == [ErrorEvent, SessionEnd]
    error, end = events
    assert isinstance(error, ErrorEvent)
    assert isinstance(end, SessionEnd)
    assert error.code == expected_code
    assert end.success is False
    assert end.error_code == expected_code
    assert not any(isinstance(event, SessionStart) for event in events)
    assert not any(isinstance(event, TextComplete) for event in events)
    assert not any(isinstance(event, UsageReport) for event in events)


def test_grok_oauth_profile_is_sealed_and_keeps_identity_claims_separate() -> None:
    adapter = GrokOAuthResponsesAdapter(
        ProviderConfig(
            provider_id="attacker",
            api_key="caller-key-must-be-ignored",
            base_url="https://attacker.invalid/v1",
            default_model="caller-model-must-be-ignored",
        )
    )

    profile = adapter.get_profile()

    assert adapter.provider_id == "grok_oauth"
    assert profile.provider_id == "grok_oauth"
    assert profile.model_id == REQUESTED_MODEL
    assert profile.max_output_tokens == 4096
    assert profile.extra["accepted_served_model"] == SERVED_MODEL
    assert profile.extra["exact_model_proven"] is False
    assert [item.model_id for item in asyncio.run(adapter.list_models())] == [
        REQUESTED_MODEL
    ]
    with pytest.raises(ValueError, match="sealed model"):
        adapter.get_profile("not-the-sealed-model")


@pytest.mark.asyncio
async def test_grok_oauth_no_tools_payload_is_sealed_and_response_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    client = _FakeClient(_FakeResponse(200, _sse(_success_events())))
    factory = _ClientFactory(client)
    monkeypatch.setattr(grok_oauth.httpx, "AsyncClient", factory)
    adapter = GrokOAuthResponsesAdapter(
        ProviderConfig(
            provider_id="grok_oauth",
            api_key="caller-key-must-be-ignored",
            base_url="https://attacker.invalid/v1",
            default_model="caller-model-must-be-ignored",
        )
    )
    request = _request(
        system_prompt="Answer with one token.",
        max_tokens=99_999,
        temperature=0.9,
        enable_thinking=True,
        provider_options={
            "timeout_sec": 17,
            "base_url": "https://attacker.invalid/v1",
            "oauth_key": "request-key-must-be-ignored",
        },
    )

    events = await _collect(adapter, request)

    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    start, text, usage, end = events
    assert isinstance(start, SessionStart)
    assert isinstance(text, TextComplete)
    assert isinstance(usage, UsageReport)
    assert isinstance(end, SessionEnd)
    assert start.model == SERVED_MODEL
    assert start.provider_id == "grok_oauth"
    assert start.tools_available == []
    assert start.system_info == {
        "base_url": "https://cli-chat-proxy.grok.com/v1",
        "endpoint_path": "/v1/responses",
        "requested_model": REQUESTED_MODEL,
        "served_model": SERVED_MODEL,
        "served_identity_source": "response.model",
        "exact_model_proven": False,
        "tool_authority": "absent",
    }
    assert text.content == "PONG"
    assert usage.input_tokens == 3
    assert usage.output_tokens == 2
    assert usage.thinking_tokens == 1
    assert usage.model_breakdown == {
        "input_tokens": 3,
        "output_tokens": 2,
        "total_tokens": 5,
        "cached_tokens": 1,
        "reasoning_tokens": 1,
        "num_server_side_tools_used": 0,
    }
    assert end.success is True

    assert factory.calls == [
        {"timeout": 17.0, "trust_env": False, "follow_redirects": False}
    ]
    assert len(client.posts) == 1
    post = client.posts[0]
    assert post["url"] == "https://cli-chat-proxy.grok.com/v1/responses"
    assert post["headers"] == {
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {OAUTH_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "xai-grok-shell/1.0.0",
        "X-XAI-Token-Auth": "xai-grok-cli",
        "x-grok-client-version": "1.0.0",
        "x-grok-client-identifier": "grok-shell",
        "x-grok-model-override": REQUESTED_MODEL,
    }
    assert post["json"] == {
        "model": REQUESTED_MODEL,
        "input": [{"role": "user", "content": "PING"}],
        "stream": True,
        "tools": [],
        "parallel_tool_calls": False,
        "store": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 4096,
        "instructions": "Answer with one token.",
    }
    assert "tool_choice" not in post["json"]
    assert "temperature" not in post["json"]
    rendered = repr([asdict(event) for event in events])
    assert OAUTH_TOKEN not in rendered
    assert "must-never-be-used" not in rendered
    assert "attacker.invalid" not in rendered
    assert "caller-key-must-be-ignored" not in repr(client.posts)
    assert "request-key-must-be-ignored" not in repr(client.posts)


@pytest.mark.asyncio
async def test_grok_oauth_config_key_cannot_replace_missing_auth_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(grok_oauth, "_GROK_AUTH_PATH", tmp_path / "missing.json")
    adapter = GrokOAuthResponsesAdapter(
        ProviderConfig(provider_id="grok_oauth", api_key="caller-secret")
    )

    events = await _collect(adapter)

    _assert_failed_before_route_evidence(events, "missing_oauth_auth")
    assert "caller-secret" not in repr([asdict(event) for event in events])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("world_readable", "insecure_oauth_auth"),
        ("malformed_json", "malformed_oauth_auth"),
        ("missing_expiry", "malformed_oauth_auth"),
        ("blank_key", "malformed_oauth_auth"),
        ("naive_expiry", "malformed_oauth_auth"),
        ("expired", "expired_oauth_auth"),
        ("multiple", "ambiguous_oauth_auth"),
    ],
)
async def test_grok_oauth_rejects_unsafe_or_ambiguous_auth_before_http(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
    expected_code: str,
) -> None:
    payload: Any = {"account": {"key": OAUTH_TOKEN, "expires_at": _future_expiry()}}
    mode = 0o600
    if case == "world_readable":
        mode = 0o644
    elif case == "malformed_json":
        path = tmp_path / "grok-auth.json"
        path.write_text("{not-json", encoding="utf-8")
        path.chmod(0o600)
        monkeypatch.setattr(grok_oauth, "_GROK_AUTH_PATH", path)
    elif case == "missing_expiry":
        payload = {"account": {"key": OAUTH_TOKEN}}
    elif case == "blank_key":
        payload = {"account": {"key": "  ", "expires_at": _future_expiry()}}
    elif case == "naive_expiry":
        payload = {"account": {"key": OAUTH_TOKEN, "expires_at": "2099-01-01"}}
    elif case == "expired":
        payload = {
            "account": {
                "key": OAUTH_TOKEN,
                "expires_at": (
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat(),
            }
        }
    elif case == "multiple":
        payload = {
            "one": {"key": OAUTH_TOKEN, "expires_at": _future_expiry()},
            "two": {"key": "second-token", "expires_at": _future_expiry()},
        }
    if case != "malformed_json":
        _write_auth(monkeypatch, tmp_path, payload=payload, mode=mode)

    class _MustNotOpenClient:
        def __init__(self, **kwargs: Any) -> None:
            raise AssertionError(f"HTTP must not start: {kwargs!r}")

    monkeypatch.setattr(grok_oauth.httpx, "AsyncClient", _MustNotOpenClient)

    events = await _collect(GrokOAuthResponsesAdapter())

    _assert_failed_before_route_evidence(events, expected_code)
    rendered = repr([asdict(event) for event in events])
    assert OAUTH_TOKEN not in rendered
    assert "second-token" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("completion", "expected_code"),
    [
        (_request(model="not-the-sealed-model"), "unsupported_model"),
        (_request(tools=[{"type": "function"}]), "tools_not_supported"),
        (_request(tool_choice="auto"), "tools_not_supported"),
        (
            _request(messages=[{"role": "tool", "content": "forbidden"}]),
            "invalid_request",
        ),
        (
            _request(
                messages=[
                    {
                        "role": "assistant",
                        "content": "forbidden",
                        "tool_calls": [{"id": "call-1"}],
                    }
                ]
            ),
            "invalid_request",
        ),
        (_request(messages=[]), "invalid_request"),
        (_request(max_tokens=True), "invalid_request"),
    ],
)
async def test_grok_oauth_rejects_request_authority_before_auth_and_http(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    completion: CompletionRequest,
    expected_code: str,
) -> None:
    monkeypatch.setattr(grok_oauth, "_GROK_AUTH_PATH", tmp_path / "missing.json")

    events = await _collect(GrokOAuthResponsesAdapter(), completion)

    _assert_failed_before_route_evidence(events, expected_code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "headers", "expected_code"),
    [
        (307, {"location": "https://credential-secret.invalid"}, "redirect_rejected"),
        (401, {"content-type": "application/json"}, "http_401"),
        (429, {"content-type": "application/json"}, "rate_limited"),
        (200, {"content-type": "application/json"}, "malformed_response"),
    ],
)
async def test_grok_oauth_http_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: int,
    headers: dict[str, str],
    expected_code: str,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    response = _FakeResponse(
        status,
        b"credential-secret-in-provider-body",
        headers=headers,
    )
    monkeypatch.setattr(
        grok_oauth.httpx,
        "AsyncClient",
        _ClientFactory(_FakeClient(response)),
    )

    events = await _collect(GrokOAuthResponsesAdapter())

    _assert_failed_before_route_evidence(events, expected_code)
    rendered = repr([asdict(event) for event in events])
    assert "credential-secret" not in rendered
    assert OAUTH_TOKEN not in rendered


@pytest.mark.asyncio
async def test_grok_oauth_stream_body_is_capped_while_reading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    response = _FakeResponse(200, b"x" * (4 * 1024 * 1024 + 1))
    monkeypatch.setattr(
        grok_oauth.httpx,
        "AsyncClient",
        _ClientFactory(_FakeClient(response)),
    )

    events = await _collect(GrokOAuthResponsesAdapter())

    _assert_failed_before_route_evidence(events, "response_too_large")
    assert response.close_count == 1


def _adversarial_stream(case: str) -> bytes:
    final = _response_object("hidden-output")
    events = _success_events(content="hidden-output", response=final)
    if case == "malformed_json":
        return b"event: response.created\ndata: {credential-secret\n\n"
    if case == "duplicate_type_key":
        raw = _sse(events)
        return raw.replace(
            b'"type":"response.created"',
            b'"type":"response.function_call_arguments.delta",'
            b'"type":"response.created"',
            1,
        )
    if case == "duplicate_nested_model_key":
        raw = _sse(events)
        model_key = f'"model":"{SERVED_MODEL}"'.encode()
        index = raw.rfind(model_key)
        assert index >= 0
        replacement = (
            b'"model":"credential-secret-model",' + f'"model":"{SERVED_MODEL}"'.encode()
        )
        return raw[:index] + replacement + raw[index + len(model_key) :]
    if case == "event_mismatch":
        events[0] = (
            "response.created",
            _event("response.in_progress", 0, response={}),
        )
    elif case == "provider_error":
        events = [
            (
                "error",
                {
                    "type": "error",
                    "error": {"message": "credential-secret"},
                },
            )
        ]
    elif case == "missing_completed":
        events = events[:-2] + [events[-1]]
    elif case == "duplicate_completed":
        events.insert(-1, events[-2])
    elif case == "tool_event":
        events.insert(
            -2,
            (
                "response.function_call_arguments.delta",
                {
                    "type": "response.function_call_arguments.delta",
                    "delta": "credential-secret",
                },
            ),
        )
    elif case == "tool_output_item":
        final["output"].append(
            {"type": "function_call", "name": "shell", "arguments": "secret"}
        )
    elif case == "nonempty_tools":
        final["tools"] = [{"type": "function", "name": "shell"}]
    elif case == "server_tool_use":
        final["usage"]["num_server_side_tools_used"] = 1
    elif case == "tool_choice_object":
        final["tool_choice"] = {"mode": "auto"}
    elif case == "tool_choice_required":
        final["tool_choice"] = "required"
    elif case in {
        "call",
        "computer_use",
        "computer_call",
        "mcp",
        "code_interpreter",
        "code_interpreter_call",
        "image_generation_call",
        "shell_call",
    }:
        final["provider_details"] = {case: {"payload": "credential-secret"}}
    elif case == "served_identity":
        final["model"] = "credential-secret-model"
    elif case == "spliced_response_id":
        final["id"] = "resp_from_another_stream"
    elif case == "empty_text":
        final["output"][1]["content"][0]["text"] = "   "
        events[10] = (
            "response.output_text.delta",
            _event("response.output_text.delta", 10, delta="   "),
        )
        events[11] = (
            "response.output_text.done",
            _event("response.output_text.done", 11, text="   "),
        )
        events[12] = (
            "response.content_part.done",
            _event(
                "response.content_part.done",
                12,
                part={"type": "output_text", "text": "   ", "annotations": []},
            ),
        )
        events[13] = (
            "response.output_item.done",
            _event(
                "response.output_item.done",
                13,
                item=final["output"][1],
                output_index=1,
            ),
        )
    elif case == "refusal":
        final["output"][1]["content"] = [
            {"type": "refusal", "refusal": "credential-secret"}
        ]
    elif case == "store_true":
        final["store"] = True
    elif case == "bad_usage":
        final["usage"]["input_tokens"] = "credential-secret"
    elif case == "delta_mismatch":
        events[10] = (
            "response.output_text.delta",
            _event("response.output_text.delta", 10, delta="credential-secret"),
        )
    elif case == "unknown_event":
        events.insert(
            -2,
            (
                "response.future_event",
                {"type": "response.future_event", "value": "credential-secret"},
            ),
        )
    elif case == "out_of_order_sequence":
        events[1][1]["sequence_number"] = 0
    else:  # pragma: no cover - protects the test table itself
        raise AssertionError(case)
    return _sse(events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("malformed_json", "malformed_sse"),
        ("duplicate_type_key", "malformed_sse"),
        ("duplicate_nested_model_key", "malformed_sse"),
        ("event_mismatch", "malformed_sse"),
        ("provider_error", "provider_response_error"),
        ("missing_completed", "malformed_sse"),
        ("duplicate_completed", "malformed_sse"),
        ("tool_event", "provider_tool_use_rejected"),
        ("tool_output_item", "provider_tool_use_rejected"),
        ("nonempty_tools", "provider_tool_use_rejected"),
        ("server_tool_use", "provider_tool_use_rejected"),
        ("tool_choice_object", "provider_tool_use_rejected"),
        ("tool_choice_required", "provider_tool_use_rejected"),
        ("call", "provider_tool_use_rejected"),
        ("computer_use", "provider_tool_use_rejected"),
        ("computer_call", "provider_tool_use_rejected"),
        ("mcp", "provider_tool_use_rejected"),
        ("code_interpreter", "provider_tool_use_rejected"),
        ("code_interpreter_call", "provider_tool_use_rejected"),
        ("image_generation_call", "provider_tool_use_rejected"),
        ("shell_call", "provider_tool_use_rejected"),
        ("served_identity", "served_identity_mismatch"),
        ("spliced_response_id", "malformed_sse"),
        ("empty_text", "empty_response"),
        ("refusal", "malformed_response"),
        ("store_true", "malformed_response"),
        ("bad_usage", "malformed_response"),
        ("delta_mismatch", "malformed_sse"),
        ("unknown_event", "malformed_sse"),
        ("out_of_order_sequence", "malformed_sse"),
    ],
)
async def test_grok_oauth_adversarial_sse_fails_before_route_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
    expected_code: str,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    monkeypatch.setattr(
        grok_oauth.httpx,
        "AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, _adversarial_stream(case)))),
    )

    events = await _collect(GrokOAuthResponsesAdapter())

    _assert_failed_before_route_evidence(events, expected_code)
    rendered = repr([asdict(event) for event in events])
    assert "credential-secret" not in rendered
    assert "hidden-output" not in rendered
    assert OAUTH_TOKEN not in rendered


@pytest.mark.asyncio
async def test_grok_oauth_transport_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    request = httpx.Request(
        "POST",
        "https://cli-chat-proxy.grok.com/v1/responses",
    )
    error = httpx.ConnectError("credential-secret-in-exception", request=request)
    monkeypatch.setattr(
        grok_oauth.httpx,
        "AsyncClient",
        _ClientFactory(_FakeClient(error=error)),
    )

    events = await _collect(GrokOAuthResponsesAdapter())

    _assert_failed_before_route_evidence(events, "transport_error")
    rendered = repr([asdict(event) for event in events])
    assert "credential-secret" not in rendered
    assert OAUTH_TOKEN not in rendered


@pytest.mark.asyncio
async def test_grok_oauth_session_start_waits_for_complete_validated_sse(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    client = _GatedClient(_FakeResponse(200, _sse(_success_events())))
    monkeypatch.setattr(grok_oauth.httpx, "AsyncClient", _ClientFactory(client))
    adapter = GrokOAuthResponsesAdapter()
    stream = adapter.stream(_request(), session_id="deferred-start")

    first_event = asyncio.create_task(anext(stream))
    await asyncio.wait_for(client.post_started.wait(), timeout=1)
    assert first_event.done() is False

    client.release_response.set()
    start = await asyncio.wait_for(first_event, timeout=1)
    remaining = [event async for event in stream]

    assert isinstance(start, SessionStart)
    assert start.model == SERVED_MODEL
    assert any(isinstance(event, TextComplete) for event in remaining)
    assert any(isinstance(event, SessionEnd) and event.success for event in remaining)
    assert adapter._active_request_task is None


@pytest.mark.asyncio
async def test_grok_oauth_cancel_interrupts_http_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_auth(monkeypatch, tmp_path)
    client = _BlockingClient()
    monkeypatch.setattr(grok_oauth.httpx, "AsyncClient", _ClientFactory(client))
    adapter = GrokOAuthResponsesAdapter()

    collector = asyncio.create_task(_collect(adapter))
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
    assert client.exit_count == 1
    assert request_task.cancelled()
    assert adapter._active_request_task is None
    assert [type(event) for event in events] == [SessionEnd]
    end = events[0]
    assert isinstance(end, SessionEnd)
    assert end.success is False
    assert end.error_code == "cancelled"
