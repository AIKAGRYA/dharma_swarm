"""Tests for the Bun terminal bridge."""

from __future__ import annotations

import asyncio
import io
import json
import os
from pathlib import Path
import sys

from dharma_swarm.model_status import LIVE_CALL_MATRIX_DIR_ENV
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.operator_core import build_session_catalog, build_session_detail
from dharma_swarm.terminal_bridge import TerminalBridge, system_commands_module
from dharma_swarm.terminal_bridge_text import render_model_policy_text
from dharma_swarm.tui import model_routing
from dharma_swarm.tui.engine.events import (
    SessionEnd,
    SessionStart,
    TextComplete,
    ToolCallComplete,
    ToolResult,
    UsageReport,
)


class _FakeProfile:
    model_id = "test-model"


class _FakeCompletionRequest:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _BlockingAdapter:
    def __init__(self, provider_id: str = "primary") -> None:
        self.provider_id = provider_id
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancel_called = asyncio.Event()
        self.stream_calls = 0
        self.cancel_calls = 0
        self.close_calls = 0

    def get_profile(self, model):
        return _FakeProfile()

    async def stream(self, completion, *, session_id):
        self.stream_calls += 1
        self.started.set()
        await self.release.wait()
        yield SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=False,
            error_code="adapter_cancelled",
            error_message="adapter stopped",
        )

    async def cancel(self):
        self.cancel_calls += 1
        self.cancel_called.set()
        self.release.set()

    async def close(self):
        self.close_calls += 1
        self.release.set()


class _ImmediateAdapter:
    def __init__(self, provider_id: str = "primary", *, fail: bool = False) -> None:
        self.provider_id = provider_id
        self.fail = fail
        self.stream_calls = 0
        self.cancel_calls = 0
        self.close_calls = 0

    def get_profile(self, model):
        return _FakeProfile()

    async def stream(self, completion, *, session_id):
        self.stream_calls += 1
        if self.fail:
            raise RuntimeError("provider exploded")
        yield SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=True,
        )

    async def cancel(self):
        self.cancel_calls += 1

    async def close(self):
        self.close_calls += 1


class _RouteCaptureAdapter(_ImmediateAdapter):
    def __init__(self, provider_id: str = "codex") -> None:
        super().__init__(provider_id)
        self.completion_models: list[str] = []

    async def stream(self, completion, *, session_id):
        self.stream_calls += 1
        self.completion_models.append(str(completion.kwargs.get("model", "")))
        yield SessionEnd(
            provider_id=self.provider_id,
            session_id=session_id,
            success=True,
        )


def _install_chat_adapters(
    bridge: TerminalBridge,
    primary,
    fallback=None,
) -> None:
    adapters = {"primary": primary}
    lanes = [("primary", "test-model", {}, "test primary")]
    if fallback is not None:
        adapters["fallback"] = fallback
        lanes.append(("fallback", "test-model", {}, "test fallback"))
    bridge._adapters = adapters
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda requested_provider, requested_model: list(lanes)


def _chat_start(request_id: str, *, prompt: str = "keep working") -> dict[str, object]:
    return {
        "id": request_id,
        "type": "session.start",
        "provider": "primary",
        "model": "test-model",
        "prompt": prompt,
        "bootstrap": {"intent": {"kind": "chat"}},
    }


def test_terminal_bridge_loads_tui_command_surface() -> None:
    assert system_commands_module is not None
    assert "status" in system_commands_module._ALL_COMMANDS


def test_terminal_bridge_bootstraps_commands_and_adapters() -> None:
    bridge = TerminalBridge()
    try:
        assert bridge._commands is not None
        assert {"claude", "codex", "openrouter"} <= set(bridge._adapters)
        assert bridge._completion_request_cls is not None
    finally:
        asyncio.run(bridge.close())


def test_model_policy_summary_uses_canonical_status_projection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "dharma_swarm.key_oracle.live_providers",
        lambda: {"claude_code", "codex", "ollama"},
    )
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(tmp_path / "no-live-matrix"))
    bridge = TerminalBridge()

    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="claude",
            selected_model="claude-opus-4.8",
            strategy="responsive",
        )
        targets = {target["alias"]: target for target in policy["targets"]}

        assert policy["schema_version"] == "dharma.model_status.v1"
        assert targets["opus-4.8"]["selectable"] is True
        assert targets["gpt-5.5"]["selectable"] is True
        assert targets["kimi-k2.6"]["available"] is True
        assert targets["kimi-k2.6"]["selectable"] is False
        assert targets["kimi-k2.6"]["availability_reason"] == "terminal_adapter_missing"

        rendered = render_model_policy_text(policy)
        assert "## Targets" in rendered
        assert "opus-4.8 -> Claude Opus 4.8" in rendered
        assert "kimi-k2.6" in rendered
        assert "terminal_adapter_missing" in rendered
    finally:
        asyncio.run(bridge.close())


def test_unknown_oracle_allows_only_authorized_local_cli_attempts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("dharma_swarm.key_oracle.live_providers", lambda: None)
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(tmp_path / "no-live-matrix"))
    bridge = TerminalBridge()
    monkeypatch.setattr(
        bridge,
        "_local_cli_attempt_authorized",
        lambda provider_id: provider_id == "codex",
    )

    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="claude",
            selected_model="claude-opus-4.8",
            strategy="responsive",
        )
        codex_targets = [target for target in policy["targets"] if target["provider"] == "codex"]
        claude_targets = [target for target in policy["targets"] if target["provider"] == "claude"]
        openrouter_targets = [target for target in policy["targets"] if target["provider"] == "openrouter"]

        assert codex_targets
        assert all(target["selectable"] is True for target in codex_targets)
        assert all(target["available"] is False for target in codex_targets)
        assert {target["route_state"] for target in codex_targets} == {"unverified"}
        assert {target["availability_reason"] for target in codex_targets} == {
            "local_cli_auth_unverified"
        }
        assert all(target["selectable"] is False for target in claude_targets)
        assert all(target["selectable"] is False for target in openrouter_targets)
        assert policy["selected_provider"] == "codex"
        assert policy["available_providers"] == []
        assert {entry["id"] for entry in policy["attemptable_providers"]} == {"codex"}
        assert {lane[0] for lane in bridge._chat_lanes("claude", "claude-opus-4.8")} == {
            "codex"
        }
    finally:
        asyncio.run(bridge.close())


def test_unknown_or_explicit_dead_oracle_never_admits_unproven_routes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(tmp_path / "no-live-matrix"))
    bridge = TerminalBridge()
    monkeypatch.setattr(bridge, "_local_cli_attempt_authorized", lambda provider_id: False)

    try:
        monkeypatch.setattr("dharma_swarm.key_oracle.live_providers", lambda: None)
        assert bridge._chat_lanes("claude", "claude-opus-4.8") == []

        monkeypatch.setattr("dharma_swarm.key_oracle.live_providers", lambda: set())
        monkeypatch.setattr(bridge, "_local_cli_attempt_authorized", lambda provider_id: True)
        assert bridge._chat_lanes("claude", "claude-opus-4.8") == []
    finally:
        asyncio.run(bridge.close())


def test_handshake_default_matches_canonical_selected_route(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "dharma_swarm.key_oracle.live_providers",
        lambda: {"claude_code", "codex"},
    )
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    monkeypatch.setenv(LIVE_CALL_MATRIX_DIR_ENV, str(tmp_path / "no-live-matrix"))
    bridge = TerminalBridge()

    try:
        default_target = model_routing.default_target()
        policy = bridge._build_model_policy_summary(
            selected_provider=default_target.provider_id,
            selected_model=default_target.model_id,
            strategy="responsive",
        )
        asyncio.run(bridge._handle_handshake("handshake-1"))
        event = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

        assert event["default_provider"] == policy["selected_provider"]
        assert event["default_model"] == policy["selected_model"]
        selected = next(
            provider
            for provider in event["providers"]
            if provider["provider_id"] == event["default_provider"]
        )
        assert selected["default_model"] == event["default_model"]
        assert event["payload"]["domain"] == "routing_decision"
        assert event["payload"]["decision"]["route_id"] == policy["selected_route"]
        assert event["policy"]["selected_route"] == policy["selected_route"]
    finally:
        asyncio.run(bridge.close())


def test_chat_route_identity_matches_ack_invocation_and_durable_metadata(tmp_path, capsys) -> None:
    bridge = TerminalBridge()
    adapter = _RouteCaptureAdapter()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"codex": adapter}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda requested_provider, requested_model: [
        ("codex", "gpt-5.5", {}, "canonical test route")
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "route-1",
                {
                    "provider": "codex",
                    "model": "gpt-5.4",
                    "prompt": "verify route ownership",
                    "bootstrap": {"intent": {"kind": "chat"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ack = next(event for event in emitted if event["type"] == "session.ack")
    receipt = next(event for event in emitted if event["type"] == "route.receipt")
    meta = bridge._session_store.load_meta(ack["session_id"])

    assert ack["provider"] == "codex"
    assert ack["model"] == "gpt-5.5"
    assert receipt == {
        "type": "route.receipt",
        "request_id": "route-1",
        "session_id": ack["session_id"],
        "provider_id": "codex",
        "model_id": "gpt-5.5",
        "route_id": "codex:gpt-5.5",
        "evidence_kind": "provider_completion",
        "success": True,
    }
    assert adapter.completion_models == ["gpt-5.5"]
    assert meta["provider_id"] == "codex"
    assert meta["model_id"] == "gpt-5.5"


def test_terminal_bridge_routes_tool_work_to_agent_lane() -> None:
    bridge = TerminalBridge()
    try:
        intent = bridge._resolve_prompt_intent(
            "read terminal/src/app.tsx and tell me where session.start is sent"
        )
        assert intent["kind"] == "agent"
        assert intent["reason"] == "tool-capable repo work request"

        test_intent = bridge._resolve_prompt_intent("run tests for the terminal tui")
        assert test_intent["kind"] == "agent"

        chat_intent = bridge._resolve_prompt_intent("what do you think about the helm UI?")
        assert chat_intent["kind"] == "chat"
    finally:
        asyncio.run(bridge.close())


def test_local_success_session_end_never_emits_provider_route_receipt(
    tmp_path, capsys
) -> None:
    adapter = _ImmediateAdapter("codex")
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"codex": adapter}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None

    try:
        asyncio.run(
            bridge._handle_session_start(
                "identity-local",
                {
                    "provider": "codex",
                    "model": "gpt-5.5",
                    "prompt": "who are you?",
                    "bootstrap": {"intent": {"kind": "identity"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert adapter.stream_calls == 0
    assert any(
        event.get("type") == "session_end" and event.get("success") is True
        for event in emitted
    )
    assert all(event.get("type") != "route.receipt" for event in emitted)


def test_session_start_creates_store_entry_before_tool_permissions(tmp_path, capsys) -> None:
    class FakeProfile:
        model_id = "gpt-5.4"

    class FakeCompletionRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAdapter:
        def get_profile(self, model):
            return FakeProfile()

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield ToolCallComplete(
                provider_id="codex",
                session_id=session_id,
                tool_call_id="tool-1",
                tool_name="shell",
                arguments="pwd",
                provider_options={"requires_confirmation": True},
            )
            yield ToolResult(
                provider_id="codex",
                session_id=session_id,
                tool_call_id="tool-1",
                tool_name="shell",
                content="/Users/dhyana/dharma_helm_build",
            )
            yield SessionEnd(provider_id="codex", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"codex": FakeAdapter()}
    bridge._completion_request_cls = FakeCompletionRequest

    try:
        asyncio.run(
            bridge._handle_session_start(
                "req-1",
                {
                    "provider": "codex",
                    "model": "gpt-5.4",
                    "prompt": "run pwd with the shell tool",
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ack = next(event for event in emitted if event["type"] == "session.ack")
    session_id = ack["session_id"]

    assert (tmp_path / session_id / "transcript.jsonl").exists()
    assert any(event["type"] == "permission.decision" for event in emitted)
    assert any(event["type"] == "tool_call_complete" for event in emitted)
    assert any(event["type"] == "tool_result" for event in emitted)
    assert any(event.type == "permission_decision" for event in bridge._session_store.load_transcript(session_id))


def test_claude_agent_turn_scrubs_metered_keys_by_default(tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeProfile:
        model_id = "claude-opus-4-8"

    class FakeCompletionRequest:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

    class FakeAdapter:
        def get_profile(self, model):
            return FakeProfile()

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": FakeAdapter()}
    bridge._completion_request_cls = FakeCompletionRequest

    try:
        asyncio.run(
            bridge._handle_session_start(
                "req-claude",
                {
                    "provider": "claude",
                    "model": "claude-opus-4-8",
                    "prompt": "read terminal/src/bridge.ts",
                    "bootstrap": {"intent": {"kind": "agent"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["provider_options"]["scrub_metered_keys"] is True
    assert kwargs["provider_options"]["permission_mode"] == "default"


def test_successful_agent_turn_persists_completed_replayable_session(tmp_path, capsys) -> None:
    class FakeAdapter:
        def get_profile(self, model):
            return _FakeProfile()

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionStart(
                provider_id="codex",
                session_id=session_id,
                model="gpt-5.4",
                provider_session_id="provider-agent-1",
            )
            yield TextComplete(
                provider_id="codex",
                session_id=session_id,
                role="assistant",
                content="AGENT_DURABLE_OK",
            )
            yield UsageReport(
                provider_id="codex",
                session_id=session_id,
                input_tokens=11,
                output_tokens=7,
                total_cost_usd=0.25,
            )
            yield SessionEnd(provider_id="codex", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"codex": FakeAdapter()}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None

    try:
        asyncio.run(
            bridge._handle_session_start(
                "agent-start",
                {
                    "provider": "codex",
                    "model": "gpt-5.4",
                    "prompt": "prove the agent session is durable",
                    "bootstrap": {"intent": {"kind": "agent"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ack = next(event for event in emitted if event["type"] == "session.ack")
    receipt = next(event for event in emitted if event["type"] == "route.receipt")
    session_id = ack["session_id"]
    reopened = SessionStore(root=tmp_path)
    meta = reopened.load_meta(session_id)
    assert meta["status"] == "completed"
    assert meta["total_turns"] == 1
    assert meta["total_input_tokens"] == 11
    assert meta["total_output_tokens"] == 7
    assert meta["provider_session_id"] == "provider-agent-1"
    assert meta["parent_session_id"] is None
    assert [event.type for event in reopened.load_transcript(session_id)] == [
        "user_prompt",
        "session_start",
        "text_complete",
        "usage",
        "session_end",
    ]
    assert reopened.verify_session_replay(session_id) == (True, [])
    assert receipt["request_id"] == "agent-start"
    assert receipt["session_id"] == session_id
    assert receipt["provider_id"] == "codex"
    assert receipt["model_id"] == "gpt-5.4"
    assert receipt["route_id"] == "codex:gpt-5.4"
    assert receipt["evidence_kind"] == "provider_completion"
    assert build_session_catalog(reopened, cwd=str(bridge._repo_root))["sessions"][0]["total_turns"] == 1
    assert build_session_detail(reopened, session_id)["compaction_preview"]["event_count"] == 5


def test_session_catalog_defaults_to_the_bridge_workspace(tmp_path, capsys) -> None:
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._session_store.create_session(
        session_id="current-workspace",
        provider_id="claude",
        model_id="claude-test",
        cwd=str(bridge._repo_root),
    )
    bridge._session_store.create_session(
        session_id="different-workspace",
        provider_id="claude",
        model_id="claude-test",
        cwd="/different/repository",
    )

    asyncio.run(bridge._handle_session_catalog("catalog-default", {"limit": 12}))

    [event] = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert event["type"] == "session.catalog.result"
    assert event["payload"]["count"] == 1
    assert [entry["session"]["session_id"] for entry in event["payload"]["sessions"]] == [
        "current-workspace"
    ]


def test_chat_persists_only_winning_fallback_and_honors_requested_resume(tmp_path, capsys) -> None:
    class FailingClaude:
        def __init__(self) -> None:
            self.resume_ids: list[str | None] = []

        def get_profile(self, model):
            return _FakeProfile()

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            self.resume_ids.append(completion.kwargs.get("resume_session_id"))
            yield SessionStart(
                provider_id="claude",
                session_id=session_id,
                model="claude-test",
                provider_session_id="discarded-native",
            )
            yield TextComplete(
                provider_id="claude",
                session_id=session_id,
                role="assistant",
                content="DISCARDED_LANE_TEXT",
            )
            yield SessionEnd(
                provider_id="claude",
                session_id=session_id,
                success=False,
                error_code="stale_resume",
                error_message="resume failed",
            )

    class WinningFallback:
        def get_profile(self, model):
            return _FakeProfile()

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionStart(
                provider_id="fallback",
                session_id=session_id,
                model="winner-model",
                provider_session_id="winner-native",
            )
            yield TextComplete(
                provider_id="fallback",
                session_id=session_id,
                role="assistant",
                content="WINNER_ONLY",
            )
            yield UsageReport(
                provider_id="fallback",
                session_id=session_id,
                input_tokens=5,
                output_tokens=2,
            )
            yield SessionEnd(provider_id="fallback", session_id=session_id, success=True)

    primary = FailingClaude()
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": primary, "fallback": WinningFallback()}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-test", {}, "requested"),
        ("fallback", "winner-model", {}, "fallback"),
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "chat-start",
                {
                    "provider": "claude",
                    "model": "claude-test",
                    "prompt": "persist only what I actually saw",
                    "resume_session_id": "requested-native-resume",
                    "bootstrap": {"intent": {"kind": "chat"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    assert primary.resume_ids == ["requested-native-resume", None]
    session_entry = bridge._session_store.list_sessions()[0]
    session_id = session_entry["session_id"]
    meta = bridge._session_store.load_meta(session_id)
    assert (meta["provider_id"], meta["model_id"]) == ("fallback", "winner-model")
    assert meta["provider_session_id"] == "winner-native"
    assert meta["parent_session_id"] is None
    assert meta["status"] == "completed"
    assert meta["total_turns"] == 1
    transcript = bridge._session_store.load_transcript(session_id)
    contents = [getattr(event, "content", "") for event in transcript]
    assert "WINNER_ONLY" in contents
    assert "DISCARDED_LANE_TEXT" not in contents
    assert [event.type for event in transcript] == [
        "user_prompt",
        "session_start",
        "text_complete",
        "usage",
        "session_end",
    ]
    assert bridge._session_store.verify_session_replay(session_id) == (True, [])
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any(event.get("content") == "WINNER_ONLY" for event in emitted)
    assert all(event.get("content") != "DISCARDED_LANE_TEXT" for event in emitted)


def test_fresh_claude_turn_never_implicitly_resumes_the_previous_native_session(
    tmp_path, capsys
) -> None:
    class RecordingClaude:
        def __init__(self) -> None:
            self.resume_ids: list[str | None] = []

        def get_profile(self, model):
            return _FakeProfile()

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            self.resume_ids.append(completion.kwargs.get("resume_session_id"))
            turn = len(self.resume_ids)
            yield SessionStart(
                provider_id="claude",
                session_id=session_id,
                model="claude-test",
                provider_session_id=f"native-{turn}",
            )
            yield TextComplete(
                provider_id="claude",
                session_id=session_id,
                role="assistant",
                content=f"turn-{turn}",
            )
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    adapter = RecordingClaude()
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": adapter}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-test", {}, "requested"),
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "fresh-one",
                {
                    "provider": "claude",
                    "model": "claude-test",
                    "prompt": "first fresh turn",
                    "bootstrap": {"intent": {"kind": "chat"}},
                },
            )
        )
        asyncio.run(
            bridge._handle_session_start(
                "fresh-two",
                {
                    "provider": "claude",
                    "model": "claude-test",
                    "prompt": "second fresh turn",
                    "bootstrap": {"intent": {"kind": "chat"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    assert adapter.resume_ids == [None, None]
    capsys.readouterr()


def test_stdio_reads_correlated_cancel_while_provider_is_blocked_and_skips_fallback(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    primary = _BlockingAdapter("primary")
    fallback = _ImmediateAdapter("fallback")
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    _install_chat_adapters(bridge, primary, fallback)
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "r", encoding="utf-8")
    writer = os.fdopen(write_fd, "w", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", reader)

    async def scenario() -> None:
        run_task = asyncio.create_task(bridge.run_stdio())
        writer.write(json.dumps(_chat_start("start-1")) + "\n")
        writer.flush()
        await asyncio.wait_for(primary.started.wait(), timeout=0.5)

        writer.write(
            json.dumps(
                {
                    "id": "cancel-1",
                    "type": "session.cancel",
                    "target_request_id": "start-1",
                }
            )
            + "\n"
        )
        writer.flush()
        await asyncio.wait_for(primary.cancel_called.wait(), timeout=0.5)
        writer.close()
        assert await asyncio.wait_for(run_task, timeout=0.5) == 0
        await bridge.close()

    try:
        asyncio.run(scenario())
    finally:
        if not writer.closed:
            writer.close()
        reader.close()

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    terminal = [
        event
        for event in emitted
        if event.get("type") == "session_end" and event.get("request_id") == "start-1"
    ]
    assert len(terminal) == 1
    assert terminal == [
        {
            "type": "session_end",
            "request_id": "start-1",
            "session_id": terminal[0]["session_id"],
            "provider_id": "primary",
            "success": False,
            "cancelled": True,
            "error_code": "cancelled",
            "error_message": "cancelled by operator",
        }
    ]
    cancel_ack = next(event for event in emitted if event.get("request_id") == "cancel-1")
    assert cancel_ack["type"] == "session.cancelled"
    assert cancel_ack["target_request_id"] == "start-1"
    assert cancel_ack["cancelled"] is True
    assert cancel_ack["reason"] == "cancel_requested"
    assert cancel_ack["provider"] == "primary"
    assert cancel_ack["target_phase"] == "streaming"
    assert fallback.stream_calls == 0
    assert bridge._active_run is None
    assert bridge._active_session_id is None
    assert bridge._active_provider_id is None
    assert bridge._active_model_id is None
    [session_entry] = bridge._session_store.list_sessions()
    cancelled_session_id = session_entry["session_id"]
    assert bridge._session_store.load_meta(cancelled_session_id)["status"] == "cancelled"
    cancelled_transcript = bridge._session_store.load_transcript(cancelled_session_id)
    assert [event.type for event in cancelled_transcript] == ["user_prompt", "session_end"]
    assert sum(isinstance(event, SessionEnd) for event in cancelled_transcript) == 1
    replay_ok, replay_issues = bridge._session_store.verify_session_replay(cancelled_session_id)
    assert replay_ok is False
    assert "session_start_count:0" in replay_issues


def test_stdio_startup_recovers_stale_ownerless_workspace_session(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    store = SessionStore(root=tmp_path / "sessions")
    session_id = store.create_session(
        session_id="legacy-empty-running",
        provider_id="claude",
        model_id="claude-test",
        cwd=str(tmp_path),
    )
    meta = store.load_meta(session_id)
    meta["updated_at"] = "2000-01-01T00:00:00+00:00"
    (store.root / session_id / "meta.json").write_text(json.dumps(meta, indent=2))

    bridge = TerminalBridge()
    bridge._repo_root = tmp_path
    bridge._session_store = store
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    async def scenario() -> int:
        result = await bridge.run_stdio()
        await bridge.close()
        return result

    assert asyncio.run(scenario()) == 0
    assert store.load_meta(session_id)["status"] == "failed"
    [terminal] = store.load_transcript(session_id)
    assert isinstance(terminal, SessionEnd)
    assert terminal.error_code == "bridge_interrupted"
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert emitted == [
        {
            "type": "bridge.ready",
            "schema_version": 1,
            "protocol": "dharma-terminal-bridge",
        }
    ]


def test_busy_start_and_mismatched_cancel_cannot_touch_active_provider(capsys, tmp_path) -> None:
    async def scenario() -> tuple[TerminalBridge, _BlockingAdapter]:
        primary = _BlockingAdapter("primary")
        bridge = TerminalBridge()
        bridge._session_store = SessionStore(root=tmp_path)
        _install_chat_adapters(bridge, primary)
        await bridge._handle_request(_chat_start("start-active"))
        await asyncio.wait_for(primary.started.wait(), timeout=0.5)

        await bridge._handle_request(_chat_start("start-second"))
        await bridge._handle_request(
            {
                "id": "cancel-wrong",
                "type": "session.cancel",
                "target_request_id": "some-other-request",
            }
        )
        assert primary.cancel_calls == 0
        assert bridge._active_run is not None
        assert bridge._active_run.request_id == "start-active"

        await bridge._handle_request(
            {
                "id": "cancel-right",
                "type": "session.cancel",
                "target_request_id": "start-active",
            }
        )
        await bridge.close()
        return bridge, primary

    bridge, primary = asyncio.run(scenario())
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    busy = next(event for event in emitted if event.get("request_id") == "start-second")
    assert busy["type"] == "bridge.error"
    assert busy["code"] == "session_busy"
    assert busy["active_request_id"] == "start-active"
    mismatch = next(event for event in emitted if event.get("request_id") == "cancel-wrong")
    assert mismatch["type"] == "session.cancelled"
    assert mismatch["cancelled"] is False
    assert mismatch["reason"] == "target_mismatch"
    assert mismatch["active_request_id"] == "start-active"
    assert primary.cancel_calls == 1
    assert bridge._active_run is None


def test_cancel_rejects_missing_idle_and_stale_targets_honestly(capsys, tmp_path) -> None:
    async def scenario() -> TerminalBridge:
        primary = _ImmediateAdapter("primary")
        bridge = TerminalBridge()
        bridge._session_store = SessionStore(root=tmp_path)
        _install_chat_adapters(bridge, primary)
        await bridge._handle_request({"id": "cancel-missing", "type": "session.cancel"})
        await bridge._handle_request(
            {
                "id": "cancel-idle",
                "type": "session.cancel",
                "target_request_id": "never-ran",
            }
        )
        await bridge._handle_session_start("start-done", _chat_start("start-done"))
        await bridge._handle_request(
            {
                "id": "cancel-stale",
                "type": "session.cancel",
                "target_request_id": "start-done",
            }
        )
        await bridge.close()
        return bridge

    bridge = asyncio.run(scenario())
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    reasons = {
        event["request_id"]: event["reason"]
        for event in emitted
        if event.get("type") == "session.cancelled"
    }
    assert reasons == {
        "cancel-missing": "missing_target_request_id",
        "cancel-idle": "idle",
        "cancel-stale": "stale",
    }
    assert all(
        event["cancelled"] is False
        for event in emitted
        if event.get("type") == "session.cancelled"
    )
    assert bridge._active_run is None


def test_close_cancels_and_drains_active_run(capsys, tmp_path) -> None:
    async def scenario() -> tuple[TerminalBridge, _BlockingAdapter]:
        primary = _BlockingAdapter("primary")
        bridge = TerminalBridge()
        bridge._session_store = SessionStore(root=tmp_path)
        _install_chat_adapters(bridge, primary)
        await bridge._handle_request(_chat_start("start-close"))
        await asyncio.wait_for(primary.started.wait(), timeout=0.5)
        await asyncio.wait_for(bridge.close(), timeout=0.5)
        return bridge, primary

    bridge, primary = asyncio.run(scenario())
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    terminal = [
        event
        for event in emitted
        if event.get("type") == "session_end" and event.get("request_id") == "start-close"
    ]
    assert len(terminal) == 1
    assert terminal[0]["cancelled"] is True
    assert terminal[0]["error_code"] == "cancelled"
    assert terminal[0]["error_message"] == "bridge closed"
    assert primary.cancel_calls == 1
    assert primary.close_calls == 1
    assert bridge._active_run is None
    assert bridge._active_session_id is None
    assert bridge._active_provider_id is None
    assert bridge._active_model_id is None
    [session_entry] = bridge._session_store.list_sessions()
    closed_session_id = session_entry["session_id"]
    assert bridge._session_store.load_meta(closed_session_id)["status"] == "cancelled"
    closed_transcript = bridge._session_store.load_transcript(closed_session_id)
    assert [event.type for event in closed_transcript] == ["user_prompt", "session_end"]
    assert sum(isinstance(event, SessionEnd) for event in closed_transcript) == 1


def test_active_state_clears_after_provider_exception(capsys, tmp_path) -> None:
    async def scenario() -> TerminalBridge:
        primary = _ImmediateAdapter("primary", fail=True)
        bridge = TerminalBridge()
        bridge._session_store = SessionStore(root=tmp_path)
        _install_chat_adapters(bridge, primary)
        await bridge._handle_session_start("start-error", _chat_start("start-error"))
        await bridge.close()
        return bridge

    bridge = asyncio.run(scenario())
    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any(
        event.get("type") == "session_end"
        and event.get("request_id") == "start-error"
        and event.get("success") is False
        for event in emitted
    )
    assert bridge._active_run is None
    assert bridge._active_session_id is None
    assert bridge._active_provider_id is None
    assert bridge._active_model_id is None
    [session_entry] = bridge._session_store.list_sessions()
    failed_session_id = session_entry["session_id"]
    assert bridge._session_store.load_meta(failed_session_id)["status"] == "failed"
    failed_transcript = bridge._session_store.load_transcript(failed_session_id)
    assert [event.type for event in failed_transcript] == [
        "user_prompt",
        "error",
        "session_end",
    ]
    assert sum(isinstance(event, SessionEnd) for event in failed_transcript) == 1
