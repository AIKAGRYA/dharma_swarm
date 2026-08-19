"""Tests for the sealed first-party Kimi Code terminal adapter."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

import httpx
import pytest

from dharma_swarm.api_keys import KIMI_API_KEY_ENV
from dharma_swarm.tui.engine.adapters import kimi_code
from dharma_swarm.tui.engine.adapters.base import CompletionRequest, ProviderConfig
from dharma_swarm.tui.engine.adapters.kimi_code import KimiCodeAdapter
from dharma_swarm.tui.engine.events import (
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
)
from tests.tui.kimi_code_test_support import (
    ENV_TOKEN,
    MODEL_ID,
    BlockingClient as _BlockingClient,
    ClientFactory as _ClientFactory,
    FakeClient as _FakeClient,
    FakeResponse as _FakeResponse,
    GatedClient as _GatedClient,
    assert_failed_before_route_evidence as _assert_failed_before_route_evidence,
    collect_events as _collect,
    completion_request as _request,
    success_payload as _success_payload,
)


@pytest.mark.parametrize(
    "raw",
    [
        {"parallel_tool_calls": False},
        {"num_server_side_tools_used": 0},
        {"tool_choice": "none"},
        {"tools": []},
    ],
)
def test_kimi_explicit_no_tool_evidence_is_accepted(raw: dict) -> None:
    assert kimi_code._has_tool_signal(raw) is False


def test_kimi_code_profile_is_the_canonical_sealed_model() -> None:
    adapter = KimiCodeAdapter(
        ProviderConfig(
            provider_id="attacker",
            api_key="caller-key-must-be-ignored",
            base_url="https://attacker.invalid/v1",
            default_model="caller-model-must-be-ignored",
        )
    )

    profile = adapter.get_profile()

    assert adapter.provider_id == "kimi_code"
    assert profile.provider_id == "kimi_code"
    assert profile.model_id == MODEL_ID
    assert [item.model_id for item in asyncio.run(adapter.list_models())] == [MODEL_ID]
    with pytest.raises(ValueError, match="sealed model"):
        adapter.get_profile("not-the-sealed-model")


@pytest.mark.asyncio
async def test_kimi_code_no_tools_payload_is_sealed_and_event_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload()
    payload["usage"]["untrusted_provider_detail"] = "must-not-project"
    client = _FakeClient(_FakeResponse(200, payload))
    factory = _ClientFactory(client)
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        factory,
    )
    adapter = KimiCodeAdapter(
        ProviderConfig(
            provider_id="kimi_code",
            api_key="caller-key-must-be-ignored",
            base_url="https://attacker.invalid/v1",
            default_model="caller-model-must-be-ignored",
        )
    )
    request = _request(
        system_prompt="Answer with one token.",
        max_tokens=8,
        temperature=0.25,
        provider_options={
            "timeout_sec": 17,
            "base_url": "https://attacker.invalid/v1",
            "kimi_api_key": "request-key-must-be-ignored",
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
    assert start.model == MODEL_ID
    assert start.provider_id == "kimi_code"
    assert start.tools_available == []
    assert start.system_info == {
        "base_url": "https://api.kimi.com/coding/v1",
        "requested_model": MODEL_ID,
        "served_model": MODEL_ID,
        "served_identity_source": "response.model",
        "exact_model_proven": True,
    }
    assert text.content == "PONG"
    assert usage.input_tokens == 3
    assert usage.output_tokens == 1
    assert usage.model_breakdown == {
        "prompt_tokens": 3,
        "completion_tokens": 1,
        "total_tokens": 4,
    }
    assert end.success is True

    assert factory.calls == [
        {"timeout": 17.0, "trust_env": False, "follow_redirects": False}
    ]
    assert client.posts == [
        {
            "url": "https://api.kimi.com/coding/v1/chat/completions",
            "headers": {
                "Accept": "application/json",
                "Authorization": f"Bearer {ENV_TOKEN}",
                "Content-Type": "application/json",
            },
            "json": {
                "model": MODEL_ID,
                "messages": [
                    {"role": "system", "content": "Answer with one token."},
                    {"role": "user", "content": "PING"},
                ],
                "stream": False,
                "tool_choice": "none",
                "max_tokens": 8,
            },
        }
    ]
    assert "temperature" not in client.posts[0]["json"]
    assert "tools" not in client.posts[0]["json"]
    assert "attacker.invalid" not in repr([asdict(event) for event in events])
    assert ENV_TOKEN not in repr([asdict(event) for event in events])
    assert "caller-key-must-be-ignored" not in repr(client.posts)
    assert "request-key-must-be-ignored" not in repr(client.posts)


@pytest.mark.asyncio
async def test_kimi_code_config_key_cannot_replace_missing_canonical_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(KIMI_API_KEY_ENV, raising=False)
    adapter = KimiCodeAdapter(
        ProviderConfig(provider_id="kimi_code", api_key="caller-key-must-be-ignored")
    )

    events = await _collect(adapter)

    _assert_failed_before_route_evidence(events, "missing_api_key")
    assert "caller-key-must-be-ignored" not in repr([asdict(event) for event in events])


@pytest.mark.asyncio
async def test_kimi_code_rejects_request_model_override_before_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    adapter = KimiCodeAdapter()

    events = await _collect(adapter, _request(model="not-the-sealed-model"))

    _assert_failed_before_route_evidence(events, "unsupported_model")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "completion",
    [
        _request(tools=[{"type": "function"}]),
        _request(tool_choice="auto"),
        _request(messages=[{"role": "tool", "content": "forbidden"}]),
        _request(
            messages=[
                {
                    "role": "assistant",
                    "content": "forbidden",
                    "tool_calls": [{"id": "call-1"}],
                }
            ]
        ),
    ],
)
async def test_kimi_code_rejects_request_side_tool_authority_before_http(
    monkeypatch: pytest.MonkeyPatch,
    completion: CompletionRequest,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    adapter = KimiCodeAdapter()

    events = await _collect(adapter, completion)

    _assert_failed_before_route_evidence(
        events,
        "tools_not_supported"
        if completion.tools or completion.tool_choice == "auto"
        else "invalid_request",
    )


@pytest.mark.asyncio
async def test_kimi_code_rejects_served_identity_mismatch_without_leaking_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload("must not escape")
    payload["model"] = "untrusted-model-identity"
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "served_identity_mismatch")
    rendered = repr([asdict(event) for event in events])
    assert "untrusted-model-identity" not in rendered
    assert "must not escape" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (["not", "an", "object"], "malformed_response"),
        (
            {
                **_success_payload("must not escape"),
                "error": {"message": "embedded-secret"},
            },
            "provider_response_error",
        ),
        ({"model": MODEL_ID, "choices": []}, "malformed_response"),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {"message": {"role": "assistant", "content": "one"}},
                    {"message": {"role": "assistant", "content": "two"}},
                ],
            },
            "malformed_response",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "error": {"message": "choice-secret"},
                        "message": {"role": "assistant", "content": "hidden"},
                    }
                ],
            },
            "provider_response_error",
        ),
        (
            {"model": MODEL_ID, "choices": [{"message": "not-an-object"}]},
            "malformed_response",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "hidden",
                            "error": {"message": "message-secret"},
                        }
                    }
                ],
            },
            "provider_response_error",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "hidden",
                            "tool_calls": [{"id": "call-1"}],
                        }
                    }
                ],
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "hidden",
                            "function_call": {"name": "shell"},
                        }
                    }
                ],
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {"role": "assistant", "content": "hidden"},
                    }
                ],
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "native_finish_reason": "tool_use",
                        "message": {"role": "assistant", "content": "hidden"},
                    }
                ],
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                **_success_payload("hidden"),
                "server_tool_use": {"web_search": 1},
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                **_success_payload("hidden"),
                "usage": {"server_tool_use_details": {"web_search": 1}},
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [{"message": {"role": "assistant", "content": "   "}}],
            },
            "empty_response",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "hidden"}],
                        }
                    }
                ],
            },
            "malformed_response",
        ),
        (
            {
                "model": MODEL_ID,
                "choices": [{"message": {"role": "tool", "content": "hidden"}}],
            },
            "malformed_response",
        ),
        (
            {
                **_success_payload("hidden"),
                "usage": {"prompt_tokens": "three", "completion_tokens": 1},
            },
            "malformed_response",
        ),
        (
            {
                **_success_payload("hidden"),
                "metadata": {"server_tool_use": {"web_search": 1}},
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                **_success_payload("hidden"),
                "metadata": {"nested": {"type": "tool_call"}},
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                **_success_payload("hidden"),
                "metadata": {"nested": {"object": "function_call"}},
            },
            "provider_tool_use_rejected",
        ),
        (
            {
                **_success_payload("hidden"),
                "metadata": {"nested": {"finish_reason": "tool_calls"}},
            },
            "provider_tool_use_rejected",
        ),
        *[
            (
                {
                    **_success_payload("hidden"),
                    "metadata": {"nested": {"type": tool_type}},
                },
                "provider_tool_use_rejected",
            )
            for tool_type in (
                "web_search_call",
                "web-search-calls",
                "computer",
                "computer_call",
                "shell",
                "shell_call",
                "mcp",
                "mcp.call",
                "code_interpreter",
                "code-interpreter-call",
                "image_generation",
                "image_generation_call",
                "server_tool_use",
            )
        ],
    ],
)
async def test_kimi_code_adversarial_response_fails_before_route_evidence(
    monkeypatch: pytest.MonkeyPatch,
    payload: Any,
    expected_code: str,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, expected_code)
    rendered = repr([asdict(event) for event in events])
    for forbidden in ("embedded-secret", "choice-secret", "message-secret", "hidden"):
        assert forbidden not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "inventory"),
    [
        ("tool", {"name": "shell"}),
        ("tools", [{"type": "computer"}]),
        ("tool_uses", [{"id": "tool-1"}]),
        ("tool-uses", [{"id": "tool-1"}]),
        ("computer_use", {"id": "computer-1"}),
        ("computer_uses", [{"id": "computer-1"}]),
        ("computer.uses", [{"id": "computer-1"}]),
        ("mcp", {"server": "provider-owned"}),
        ("code_interpreter", {"input": "provider-owned"}),
        ("file_search_call", {"query": "provider-owned"}),
        ("web_search", {"query": "provider-owned"}),
    ],
)
async def test_kimi_code_rejects_nested_nonempty_tool_inventories(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    inventory: Any,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload("must not escape")
    payload["metadata"] = {"nested": {field: inventory}}
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "provider_tool_use_rejected")
    assert "must not escape" not in repr([asdict(event) for event in events])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "signal",
    [
        {"toolCalls": [{"id": "tool-1"}]},
        {"functionCall": {"name": "provider-owned"}},
        {"computerUse": {"id": "computer-1"}},
        {"type": "toolCall"},
        {"finishReason": "tool_calls"},
    ],
)
async def test_kimi_code_rejects_camel_case_structural_tool_signals(
    monkeypatch: pytest.MonkeyPatch,
    signal: dict[str, Any],
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload("must not escape")
    payload["metadata"] = {"nested": signal}
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "provider_tool_use_rejected")
    assert "must not escape" not in repr([asdict(event) for event in events])


@pytest.mark.asyncio
async def test_kimi_code_allows_nested_empty_no_tools_inventories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload()
    payload["metadata"] = {
        "nested": {
            "tool": None,
            "tools": [],
            "more": {"tool": {}, "tools": ""},
        }
    }
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    assert isinstance(events[-1], SessionEnd)
    assert events[-1].success is True


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_choice", [None, "none"])
async def test_kimi_code_allows_only_explicit_no_tool_choice(
    monkeypatch: pytest.MonkeyPatch,
    tool_choice: Any,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload()
    payload["metadata"] = {"nested": {"tool_choice": tool_choice}}
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    assert isinstance(events[-1], SessionEnd)
    assert events[-1].success is True


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_choice", ["", "auto", "NONE", [], {}, False])
async def test_kimi_code_rejects_every_other_tool_choice(
    monkeypatch: pytest.MonkeyPatch,
    tool_choice: Any,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    payload = _success_payload("must not escape")
    payload["metadata"] = {"nested": {"tool_choice": tool_choice}}
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "provider_tool_use_rejected")
    assert "must not escape" not in repr([asdict(event) for event in events])


@pytest.mark.asyncio
async def test_kimi_code_does_not_treat_narration_as_tool_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    narration = (
        "No tool_uses, computer_use, mcp, code_interpreter, file_search_call, "
        "web_search, toolCalls, functionCall, computerUse, toolCall, or "
        "finishReason capability was available."
    )
    payload = _success_payload(narration)
    payload["metadata"] = {"narration": narration, "notes": [narration]}
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, payload))),
    )

    events = await _collect(KimiCodeAdapter())

    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    text = events[1]
    assert isinstance(text, TextComplete)
    assert text.content == narration


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate_field", ["model", "type"])
async def test_kimi_code_rejects_duplicate_json_keys_at_any_depth(
    monkeypatch: pytest.MonkeyPatch,
    duplicate_field: str,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    raw = json.dumps(_success_payload(), separators=(",", ":"))
    if duplicate_field == "model":
        model_member = f'"model":{json.dumps(MODEL_ID)}'
        raw = raw.replace(model_member, f"{model_member},{model_member}", 1)
    else:
        raw = (
            raw[:-1]
            + ',"metadata":{"nested":{"type":"text","type":"text"}}}'
        )
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(_FakeResponse(200, raw))),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "malformed_response")


@pytest.mark.asyncio
async def test_kimi_code_streaming_response_body_has_hard_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    monkeypatch.setattr(kimi_code, "_MAX_RESPONSE_BYTES", 64)
    response = _FakeResponse(
        200,
        _success_payload("must not escape" * 20),
        chunk_size=11,
    )
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(response)),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "response_too_large")
    assert response.close_count == 1
    assert "must not escape" not in repr([asdict(event) for event in events])


@pytest.mark.asyncio
async def test_kimi_code_response_requires_strict_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    response = _FakeResponse(200, b'{"model":"\xff"}')
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(response)),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "malformed_response")
    assert response.close_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (
            _FakeResponse(401, {}, text="credential-secret-in-body"),
            "http_401",
        ),
        (
            _FakeResponse(
                200,
                {},
                json_error=ValueError("credential-secret-in-json-error"),
            ),
            "malformed_response",
        ),
    ],
)
async def test_kimi_code_http_and_json_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    response: _FakeResponse,
    expected_code: str,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(response)),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, expected_code)
    rendered = repr([asdict(event) for event in events])
    assert "credential-secret" not in rendered
    assert ENV_TOKEN not in rendered


@pytest.mark.asyncio
async def test_kimi_code_transport_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    request = httpx.Request("POST", "https://api.kimi.com/coding/v1/chat/completions")
    error = httpx.ConnectError("credential-secret-in-exception", request=request)
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(_FakeClient(error=error)),
    )

    events = await _collect(KimiCodeAdapter())

    _assert_failed_before_route_evidence(events, "transport_error")
    rendered = repr([asdict(event) for event in events])
    assert "credential-secret" not in rendered
    assert ENV_TOKEN not in rendered


@pytest.mark.asyncio
async def test_kimi_code_session_start_waits_for_validated_http_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    client = _GatedClient(_FakeResponse(200, _success_payload()))
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(client),
    )
    adapter = KimiCodeAdapter()
    stream = adapter.stream(_request(), session_id="deferred-start")

    first_event = asyncio.create_task(anext(stream))
    await asyncio.wait_for(client.post_started.wait(), timeout=1)
    assert first_event.done() is False

    client.release_response.set()
    start = await asyncio.wait_for(first_event, timeout=1)
    remaining = [event async for event in stream]

    assert isinstance(start, SessionStart)
    assert start.model == MODEL_ID
    assert any(isinstance(event, TextComplete) for event in remaining)
    assert any(isinstance(event, SessionEnd) and event.success for event in remaining)
    assert adapter._active_request_task is None


@pytest.mark.asyncio
async def test_kimi_code_cancel_interrupts_http_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(KIMI_API_KEY_ENV, ENV_TOKEN)
    client = _BlockingClient()
    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.kimi_code.httpx.AsyncClient",
        _ClientFactory(client),
    )
    adapter = KimiCodeAdapter()

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
