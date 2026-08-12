"""Tests for the Bun terminal bridge."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import pytest

from dharma_swarm.model_status import LIVE_CALL_MATRIX_DIR_ENV
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.operator_core import build_session_catalog, build_session_detail
from dharma_swarm.terminal_bridge import TerminalBridge, system_commands_module
from dharma_swarm.terminal_bridge_text import render_model_policy_text
from dharma_swarm.tui import model_routing
from dharma_swarm.tui.engine.events import (
    CanonicalEvent,
    SessionEnd,
    SessionStart,
    TaskStarted,
    TextComplete,
    ToolCallComplete,
    UsageReport,
)


HELM_SLICE1_COMPOUND_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "terminal_bridge"
    / "helm_slice1_compound_adversarial.json"
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


def test_terminal_bridge_materializes_memory_common(monkeypatch) -> None:
    bridge = TerminalBridge()
    monkeypatch.setattr(
        "dharma_swarm.memory_common.render_memory_common_command",
        lambda arg, **kwargs: f"memory common rendered: {arg}",
        raising=True,
    )

    try:
        output = bridge._materialize_async_command("memory common agent task", "async:memory:common agent task")
    finally:
        asyncio.run(bridge.close())

    assert output == "memory common rendered: common agent task"


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
        # Codex advertises the shell tool and is therefore excluded from the
        # Slice-1 primary-chat membrane even when a local CLI attempt is
        # otherwise authorized.
        assert bridge._chat_lanes("claude", "claude-opus-4.8") == []
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
    adapter = _RouteCaptureAdapter("claude")
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": adapter}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda requested_provider, requested_model: [
        ("claude", "claude-opus-4.8", {}, "canonical test route")
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "route-1",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
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

    assert ack["provider"] == "claude"
    assert ack["model"] == "claude-opus-4.8"
    assert receipt == {
        "type": "route.receipt",
        "request_id": "route-1",
        "session_id": ack["session_id"],
        "provider_id": "claude",
        "model_id": "claude-opus-4.8",
        "route_id": "claude:claude-opus-4.8",
        "evidence_kind": "provider_completion",
        "success": True,
    }
    assert adapter.completion_models == ["claude-opus-4.8"]
    assert meta["provider_id"] == "claude"
    assert meta["model_id"] == "claude-opus-4.8"


def test_terminal_bridge_only_classifies_whole_registered_commands() -> None:
    bridge = TerminalBridge()
    try:
        assert bridge._resolve_prompt_intent("/status verbose") == {
            "kind": "command",
            "auto_execute": True,
            "confidence": "high",
            "command": "status verbose",
            "reason": "explicit registered slash command",
        }
        assert bridge._resolve_prompt_intent("status")["kind"] == "command"
        for conversational in (
            "read terminal/src/app.tsx and tell me where session.start is sent",
            "run tests for the terminal tui",
            "show status",
            "status now",
            "/status\nthen run swarm",
            "/status\rthen run swarm",
            "/status\vthen run swarm",
            "/status\fthen run swarm",
            "/status\x1cthen run swarm",
            "/status\x1dthen run swarm",
            "/status\x1ethen run swarm",
            "/status\x1fthen run swarm",
            "/status\x85then run swarm",
            "/status\u2028then run swarm",
            "/status\u2029then run swarm",
            "/status\u2003then run swarm",
            "/status ",
            "/status\t",
            "/status verbose ",
            "/status verbose\t",
            "/not-registered",
            " status ",
        ):
            intent = bridge._resolve_prompt_intent(conversational)
            assert intent["kind"] == "chat"
            assert intent["auto_execute"] is False
    finally:
        asyncio.run(bridge.close())


@pytest.mark.parametrize("prompt", ["/status ", "/status\t"])
def test_padded_slash_prompt_reaches_provider_byte_exact_without_command_dispatch(
    prompt: str,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    captured_prompts: list[str] = []

    class PromptCaptureAdapter(_ImmediateAdapter):
        async def stream(self, completion, *, session_id):
            self.stream_calls += 1
            captured_prompts.append(str(completion.kwargs["messages"][-1]["content"]))
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=True,
            )

    adapter = PromptCaptureAdapter("claude")
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": adapter}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-opus-4.8", {}, "sealed no-tools route")
    ]

    async def forbidden_command(request_id, request):
        raise AssertionError(f"padded chat reached command handling: {request}")

    monkeypatch.setattr(bridge, "_handle_command", forbidden_command)

    try:
        asyncio.run(
            bridge._handle_session_start(
                "padded-slash-chat",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
                    "prompt": prompt,
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert adapter.stream_calls == 1
    assert len(captured_prompts) == 1
    assert captured_prompts[0].encode("utf-8") == prompt.encode("utf-8")
    assert all(event["type"] not in {"command.result", "action.result"} for event in emitted)


def test_compound_fixture_is_exact_and_bootstrap_does_not_write_working_memory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fixture = json.loads(HELM_SLICE1_COMPOUND_FIXTURE.read_text(encoding="utf-8"))
    prompt = fixture["prompt"]
    encoded = prompt.encode("utf-8")

    assert len(encoded) == 239
    assert hashlib.sha256(encoded).hexdigest() == fixture["utf8_sha256"]

    bridge = TerminalBridge()
    bridge._state_dir = tmp_path / "terminal-state"
    monkeypatch.setattr(bridge, "_build_workspace_snapshot", lambda: "workspace")
    monkeypatch.setattr(bridge, "_build_ontology_snapshot", lambda: "ontology")
    monkeypatch.setattr(bridge, "_build_runtime_snapshot", lambda: "runtime")
    monkeypatch.setattr(bridge, "_load_repo_guidance", lambda: "guidance")
    monkeypatch.setattr(bridge, "_load_session_context_hint", lambda: "context")
    monkeypatch.setattr(bridge, "_load_working_memory", lambda: {"turns": []})
    monkeypatch.setattr(bridge, "_build_workspace_preview", lambda content: {})
    monkeypatch.setattr(bridge, "_build_runtime_preview", lambda content: {})
    monkeypatch.setattr(bridge, "_build_command_graph_summary", lambda: {})
    monkeypatch.setattr(
        bridge,
        "_build_model_policy_summary",
        lambda **kwargs: {
            "selected_provider": "claude",
            "selected_model": "claude-opus-4.8",
        },
    )
    monkeypatch.setattr(bridge, "_render_working_memory", lambda memory: "memory")
    monkeypatch.setattr(bridge, "_render_system_prompt", lambda **kwargs: "system")
    strategy_inputs: list[str] = []

    def forbidden_prompt_route_inference(prompt_text: str):
        raise AssertionError(f"bootstrap inferred a route from prompt: {prompt_text}")

    def record_explicit_strategy(strategy_text: str):
        strategy_inputs.append(strategy_text)
        return None

    monkeypatch.setattr(model_routing, "resolve_model_target", forbidden_prompt_route_inference)
    monkeypatch.setattr(model_routing, "resolve_strategy", record_explicit_strategy)

    def forbidden_working_memory_write(*args, **kwargs):
        raise AssertionError("chat classification attempted a working-memory write")

    monkeypatch.setattr(bridge, "_apply_turn_to_memory", forbidden_working_memory_write)
    monkeypatch.setattr(bridge, "_save_working_memory", forbidden_working_memory_write)

    try:
        bootstrap = bridge._build_session_bootstrap(
            {
                "provider": "claude",
                "model": "claude-opus-4.8",
                "prompt": prompt,
            }
        )
    finally:
        asyncio.run(bridge.close())

    assert bootstrap["prompt"].encode("utf-8") == encoded
    assert bootstrap["intent"]["kind"] == fixture["expected_intent_kind"]
    assert bootstrap["intent"]["auto_execute"] is fixture["expected_auto_execute"]
    assert bootstrap["selected_provider"] == "claude"
    assert bootstrap["selected_model"] == "claude-opus-4.8"
    assert strategy_inputs == [""]
    assert not (bridge._state_dir / "working_memory.json").exists()


def test_compound_fixture_ignores_forged_intent_and_has_zero_effects(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    fixture = json.loads(HELM_SLICE1_COMPOUND_FIXTURE.read_text(encoding="utf-8"))
    prompt = fixture["prompt"]
    captured: dict[str, object] = {}
    effects = dict(fixture["expected_effect_counters"])

    class SealedClaude:
        def get_profile(self, model):
            return _FakeProfile()

        async def cancel(self):
            return None

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            captured["kwargs"] = completion.kwargs
            yield SessionStart(
                provider_id="claude",
                session_id=session_id,
                model="claude-opus-4.8",
                provider_session_id="compound-native",
                tools_available=[],
            )
            yield TextComplete(
                provider_id="claude",
                session_id=session_id,
                role="assistant",
                content="I completed the requested swarm, seeds, and evolution runs.",
            )
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._repo_root = tmp_path
    bridge._state_dir = tmp_path / "terminal-state"
    bridge._session_store = SessionStore(root=tmp_path / "sessions")
    bridge._adapters = {"claude": SealedClaude()}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-opus-4.8", {"tools": "*"}, "sealed")
    ]

    async def forbidden_command(request_id, request):
        effects["agent"] += 1
        raise AssertionError("compound chat reached command handling")

    def deny_effect(counter: str):
        def denied(*args, **kwargs):
            effects[counter] += 1
            raise AssertionError(f"compound chat attempted {counter} state/effect access")

        return denied

    monkeypatch.setattr(bridge, "_handle_command", forbidden_command)
    monkeypatch.setattr(bridge, "_build_session_bootstrap", deny_effect("runtime"))
    monkeypatch.setattr(bridge, "_apply_turn_to_memory", deny_effect("runtime"))
    monkeypatch.setattr(bridge, "_save_working_memory", deny_effect("runtime"))
    monkeypatch.setattr(bridge, "_remember_action", deny_effect("runtime"))
    monkeypatch.setattr(bridge, "_build_agent_routes", deny_effect("agent"))
    monkeypatch.setattr(bridge, "_build_workspace_snapshot", deny_effect("workspace"))
    monkeypatch.setattr(bridge, "_build_runtime_snapshot", deny_effect("runtime"))
    monkeypatch.setattr(bridge, "_run_action", deny_effect("external_effect"))

    try:
        asyncio.run(
            bridge._handle_session_start(
                "compound-start",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
                    "prompt": prompt,
                    "bootstrap": {
                        "intent": {
                            "kind": "command",
                            "auto_execute": True,
                            "command": "swarm",
                        }
                    },
                    "provider_options": {
                        "permission_mode": "bypassPermissions",
                        "tools": "*",
                        "strict_mcp_config": False,
                        "max_turns": 99,
                    },
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["messages"][-1]["content"].encode("utf-8") == prompt.encode("utf-8")
    assert kwargs["tools"] == []
    assert kwargs["tool_choice"] == "none"
    assert kwargs["provider_options"]["permission_mode"] == "plan"
    assert kwargs["provider_options"]["tools"] == ""
    assert kwargs["provider_options"]["strict_mcp_config"] is True
    assert kwargs["provider_options"]["max_turns"] == 1

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert all(event["type"] not in {"command.result", "action.result"} for event in emitted)
    forbidden_prefixes = ("tool_", "task_")
    for event in emitted:
        if event["type"].startswith("tool_"):
            effects["tool"] += 1
        if event["type"].startswith("task_"):
            effects["task"] += 1
        assert not event["type"].startswith(forbidden_prefixes)
    narration = next(event for event in emitted if event["type"] == "text_complete")
    assert narration["authority"] == fixture["expected_authority"]
    assert narration["narration_verified"] is fixture["expected_narration_verified"]
    assert narration["state_promotion_allowed"] is False
    assert effects == fixture["expected_effect_counters"]
    assert not (bridge._state_dir / "working_memory.json").exists()
    assert any(event["type"] == "route.receipt" for event in emitted)


def test_session_start_rejects_empty_and_nul_before_persistence_or_provider(
    tmp_path: Path,
    capsys,
) -> None:
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    adapter = _ImmediateAdapter()
    _install_chat_adapters(bridge, adapter)

    try:
        asyncio.run(bridge._handle_session_start("empty", _chat_start("empty", prompt=" \n")))
        asyncio.run(bridge._handle_session_start("nul", _chat_start("nul", prompt="safe\x00unsafe")))
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert {(event["request_id"], event["code"]) for event in emitted} == {
        ("empty", "missing_prompt"),
        ("nul", "invalid_prompt_nul"),
    }
    assert adapter.stream_calls == 0
    assert bridge._session_store.list_sessions() == []


def test_session_start_ignores_caller_session_path_and_receipts_stay_under_root(
    tmp_path: Path,
    capsys,
) -> None:
    store_root = tmp_path / "sessions"
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=store_root)
    _install_chat_adapters(bridge, _ImmediateAdapter())
    request = _chat_start("server-owned-session")
    request["session_id"] = "../../forged-evidence-root"
    request["parent_session_id"] = "forged-parent-authority"

    try:
        asyncio.run(bridge._handle_session_start("server-owned-session", request))
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ack = next(event for event in emitted if event["type"] == "session.ack")
    session_id = ack["session_id"]
    assert session_id.startswith("dgc-")
    assert "/" not in session_id
    assert (store_root / session_id / "transcript.jsonl").is_file()
    assert bridge._session_store.load_meta(session_id)["parent_session_id"] is None
    assert not (tmp_path / "forged-evidence-root").exists()


def test_stub_command_outcomes_fail_closed_and_fail_the_session(tmp_path, capsys) -> None:
    adapter = _ImmediateAdapter("claude")
    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": adapter}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None

    try:
        asyncio.run(bridge._handle_command("missing-command", {"command": ""}))
        asyncio.run(bridge._handle_command("stub-command", {"command": "/swarm status"}))
        asyncio.run(
            bridge._handle_action_run(
                "stub-action",
                {"action_type": "command.run", "command": "/evolve status"},
            )
        )
        asyncio.run(
            bridge._handle_session_start(
                "stub-session",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
                    "prompt": "/swarm status",
                    "bootstrap": {"intent": {"kind": "chat"}},
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    missing = next(event for event in emitted if event.get("request_id") == "missing-command")
    assert (missing["outcome"], missing["ok"], missing["completed"]) == (
        "failed",
        False,
        False,
    )
    stub = next(event for event in emitted if event.get("request_id") == "stub-command")
    assert (stub["outcome"], stub["ok"], stub["supported"]) == (
        "unsupported",
        False,
        False,
    )
    action = next(event for event in emitted if event.get("request_id") == "stub-action")
    assert action["type"] == "action.result"
    assert (action["outcome"], action["ok"], action["completed"]) == (
        "unsupported",
        False,
        False,
    )
    terminal = next(
        event
        for event in emitted
        if event.get("request_id") == "stub-session" and event["type"] == "session_end"
    )
    assert terminal["success"] is False
    assert terminal["error_code"] == "command_unsupported"
    assert adapter.stream_calls == 0


@pytest.mark.parametrize(
    ("command", "expected_action"),
    [
        ("btw investigate", "btw:open"),
        ("cancel", "cancel"),
        ("chat", "chat:new"),
        ("chat continue", "chat:continue"),
        ("clear", "clear"),
        ("copy", "copy"),
        ("copylast", "copylast"),
        ("dashboard", "dashboard:open"),
        ("paste", "paste"),
        ("plan on", "mode:set:P"),
        ("plan off", "mode:set:N"),
        ("model auto on", "model:auto on"),
        ("model auto status", "model:auto status"),
        ("model strategy cost", "model:auto cost"),
        ("model set definitely-not-a-route", "model:set definitely-not-a-route"),
        ("model reset", "model:cooldown clear"),
    ],
)
def test_unconsumed_command_actions_are_explicitly_unsupported(
    command: str,
    expected_action: str,
    capsys,
) -> None:
    bridge = TerminalBridge()

    try:
        result = asyncio.run(
            bridge._handle_command(f"unsupported-{expected_action}", {"command": command})
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert emitted == [result]
    assert result["action"] == expected_action
    assert result["outcome"] == "unsupported"
    assert result["ok"] is False
    assert result["supported"] is False
    assert result["completed"] is False
    assert "Unsupported in Helm Slice 1" in result["output"]


@pytest.mark.parametrize(
    "command",
    ["model status", "model list", "model metrics", "model cooldown status"],
)
def test_read_only_model_commands_remain_completed(command: str, capsys) -> None:
    bridge = TerminalBridge()

    try:
        result = asyncio.run(
            bridge._handle_command(f"read-only-{command}", {"command": command})
        )
    finally:
        asyncio.run(bridge.close())

    capsys.readouterr()
    assert result["outcome"] == "completed"
    assert result["ok"] is True
    assert result["supported"] is True
    assert result["completed"] is True
    assert str(result["output"]).strip()


@pytest.mark.parametrize("command", ["net on", "net off", "reset"])
def test_unbound_net_mutations_and_reset_are_unsupported(command: str, capsys) -> None:
    bridge = TerminalBridge()

    try:
        result = asyncio.run(
            bridge._handle_command(f"unbound-{command}", {"command": command})
        )
    finally:
        asyncio.run(bridge.close())

    capsys.readouterr()
    assert result["outcome"] == "unsupported"
    assert result["ok"] is False
    assert result["supported"] is False
    assert result["completed"] is False
    assert "Unsupported in Helm Slice 1" in result["output"]


@pytest.mark.parametrize(("command", "expected_supported"), [("help", True), ("hlep", False)])
def test_handler_exception_emits_one_correlated_failed_direct_result(
    command: str,
    expected_supported: bool,
    capsys,
) -> None:
    class RaisingCommands:
        def handle(self, raw_command):
            raise RuntimeError("do-not-leak-handler-detail")

    bridge = TerminalBridge()
    bridge._commands = RaisingCommands()

    try:
        result = asyncio.run(
            bridge._handle_command("direct-handler-failure", {"command": command})
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert emitted == [result]
    assert result["type"] == "command.result"
    assert result["request_id"] == "direct-handler-failure"
    assert result["command"] == command
    assert result["outcome"] == "failed"
    assert result["ok"] is False
    assert result["supported"] is expected_supported
    assert result["completed"] is False
    assert result["error_type"] == "RuntimeError"
    assert "do-not-leak-handler-detail" not in result["output"]


@pytest.mark.parametrize(
    "raw_command",
    ["  /thread attacker-chosen  ", "/thread attacker\nsecond-command", "\t/thread attacker"],
)
def test_command_run_rejects_non_exact_envelopes_without_calling_handler(
    raw_command: str,
    capsys,
) -> None:
    class ForbiddenCommands:
        def handle(self, command):
            raise AssertionError(f"non-exact command reached handler: {command}")

    bridge = TerminalBridge()
    bridge._commands = ForbiddenCommands()

    try:
        direct = asyncio.run(
            bridge._handle_command("non-exact-direct", {"command": raw_command})
        )
        asyncio.run(
            bridge._handle_action_run(
                "non-exact-action",
                {"action_type": "command.run", "command": raw_command},
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert [event["request_id"] for event in emitted] == [
        "non-exact-direct",
        "non-exact-action",
    ]
    assert [event["type"] for event in emitted] == [
        "command.result",
        "action.result",
    ]
    for result in (direct, *emitted):
        assert result["outcome"] == "failed"
        assert result["ok"] is False
        assert result["supported"] is False
        assert result["completed"] is False


@pytest.mark.parametrize(("command", "expected_supported"), [("help", True), ("hlep", False)])
def test_handler_exception_emits_one_correlated_failed_action_result(
    command: str,
    expected_supported: bool,
    capsys,
) -> None:
    class RaisingCommands:
        def handle(self, raw_command):
            raise RuntimeError("do-not-leak-handler-detail")

    bridge = TerminalBridge()
    bridge._commands = RaisingCommands()

    try:
        asyncio.run(
            bridge._handle_action_run(
                "action-handler-failure",
                {"action_type": "command.run", "command": command},
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert len(emitted) == 1
    result = emitted[0]
    assert result["type"] == "action.result"
    assert result["request_id"] == "action-handler-failure"
    assert result["action_type"] == "command.run"
    assert result["command"] == command
    assert result["outcome"] == "failed"
    assert result["ok"] is False
    assert result["supported"] is expected_supported
    assert result["completed"] is False
    assert result["error_type"] == "RuntimeError"
    assert "do-not-leak-handler-detail" not in result["output"]


@pytest.mark.parametrize("path", ["direct", "action"])
def test_materializer_exception_returns_one_correlated_failed_result(
    path: str,
    monkeypatch,
    capsys,
) -> None:
    bridge = TerminalBridge()

    def raising_materializer(raw_command, action):
        raise ValueError("do-not-leak-materializer-detail")

    monkeypatch.setattr(bridge, "_materialize_model_command", raising_materializer)
    try:
        if path == "direct":
            result = asyncio.run(
                bridge._handle_command(
                    "direct-materializer-failure",
                    {"command": "model status"},
                )
            )
        else:
            asyncio.run(
                bridge._handle_action_run(
                    "action-materializer-failure",
                    {"action_type": "command.run", "command": "model status"},
                )
            )
            result = None
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert len(emitted) == 1
    event = emitted[0]
    if result is not None:
        assert event == result
        assert event["type"] == "command.result"
        assert event["request_id"] == "direct-materializer-failure"
    else:
        assert event["type"] == "action.result"
        assert event["request_id"] == "action-materializer-failure"
        assert event["action_type"] == "command.run"
    assert event["outcome"] == "failed"
    assert event["ok"] is False
    assert event["supported"] is True
    assert event["completed"] is False
    assert event["error_type"] == "ValueError"
    assert "do-not-leak-materializer-detail" not in event["output"]


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
                    "prompt": "/help",
                    "bootstrap": {
                        "intent": {
                            "kind": "chat",
                            "auto_execute": False,
                        }
                    },
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    assert adapter.stream_calls == 0
    command = next(event for event in emitted if event.get("type") == "command.result")
    assert command["outcome"] == "completed"
    assert command["ok"] is True
    assert any(
        event.get("type") == "session_end" and event.get("success") is True
        for event in emitted
    )
    assert all(event.get("type") != "route.receipt" for event in emitted)


@pytest.mark.parametrize(
    "forbidden_event",
    [
        "tool_call_complete",
        "task_started",
        "command.result",
        "workspace.snapshot.result",
    ],
)
@pytest.mark.parametrize("cancel_fails", [False, True])
def test_chat_rejects_and_never_buffers_tool_task_command_or_effect_events(
    forbidden_event: str,
    cancel_fails: bool,
    tmp_path,
    capsys,
) -> None:
    class FakeProfile:
        model_id = "claude-opus-4.8"

    class FakeCompletionRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAdapter:
        def __init__(self) -> None:
            self.cancel_calls = 0

        def get_profile(self, model):
            return FakeProfile()

        async def cancel(self):
            self.cancel_calls += 1
            if cancel_fails:
                raise RuntimeError("sensitive cancel detail")

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionStart(
                provider_id="claude",
                session_id=session_id,
                model="claude-opus-4.8",
                tools_available=[],
            )
            if forbidden_event == "tool_call_complete":
                yield ToolCallComplete(
                    provider_id="claude",
                    session_id=session_id,
                    tool_call_id="tool-1",
                    tool_name="shell",
                    arguments="pwd",
                    provider_options={"requires_confirmation": True},
                )
            elif forbidden_event == "task_started":
                yield TaskStarted(
                    provider_id="claude",
                    session_id=session_id,
                    task_id="task-1",
                    description="forbidden task",
                )
            else:
                yield CanonicalEvent(
                    type=forbidden_event,
                    provider_id="claude",
                    session_id=session_id,
                )
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    adapter = FakeAdapter()
    bridge._adapters = {"claude": adapter}
    bridge._completion_request_cls = FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-opus-4.8", {}, "sealed test route"),
        ("openrouter", "moonshotai/kimi-k3", {}, "must not run"),
    ]
    fallback = _ImmediateAdapter("openrouter")
    bridge._adapters["openrouter"] = fallback

    try:
        asyncio.run(
            bridge._handle_session_start(
                "req-1",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
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
    assert adapter.cancel_calls == 1
    assert fallback.stream_calls == 0
    assert all(event["type"] != forbidden_event for event in emitted)
    assert all(event["type"] != "permission.decision" for event in emitted)
    assert all(event["type"] != "route.receipt" for event in emitted)
    assert all(event["type"] != "helm.on_call_projection" for event in emitted)
    transcript_types = [
        event.type for event in bridge._session_store.load_transcript(session_id)
    ]
    assert forbidden_event not in transcript_types
    assert "permission_decision" not in transcript_types
    membrane_error = next(
        event
        for event in emitted
        if event.get("type") == "error"
        and event.get("code") == "chat_membrane_violation"
    )
    assert ("provider cancellation failed" in membrane_error["message"]) is cancel_fails
    assert "sensitive cancel detail" not in json.dumps(emitted)
    terminal = next(event for event in emitted if event["type"] == "session_end")
    assert terminal["success"] is False
    assert terminal["error_code"] == "chat_membrane_violation"


def test_claude_chat_turn_is_sealed_no_tools_and_preserves_raw_prompt(tmp_path) -> None:
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

        async def cancel(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": FakeAdapter()}
    bridge._completion_request_cls = FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-opus-4.8", {"permission_mode": "bypassPermissions"}, "sealed")
    ]
    raw_prompt = "  read café/端末.md exactly  \n"

    try:
        asyncio.run(
            bridge._handle_session_start(
                "req-claude",
                {
                    "provider": "claude",
                    "model": "claude-opus-4-8",
                    "prompt": raw_prompt,
                    "bootstrap": {
                        "intent": {
                            "kind": "command",
                            "auto_execute": True,
                            "command": "swarm",
                        }
                    },
                    "provider_options": {
                        "permission_mode": "bypassPermissions",
                        "tools": "*",
                        "strict_mcp_config": False,
                        "max_turns": 99,
                    },
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["messages"][-1]["content"].encode("utf-8") == raw_prompt.encode("utf-8")
    assert kwargs["tools"] == []
    assert kwargs["tool_choice"] == "none"
    assert kwargs["provider_options"]["scrub_metered_keys"] is True
    assert kwargs["provider_options"]["permission_mode"] == "plan"
    assert kwargs["provider_options"]["tools"] == ""
    assert kwargs["provider_options"]["strict_mcp_config"] is True
    assert kwargs["provider_options"]["setting_sources"] == ""
    assert kwargs["provider_options"]["max_turns"] == 1
    assert kwargs["provider_options"]["raw_single_user_prompt"] is True
    assert "authority NONE" in kwargs["system_prompt"]
    assert "⟦helm:" not in kwargs["system_prompt"]
    assert "narration only" in kwargs["system_prompt"]


def test_openrouter_sealed_options_require_served_identity_and_preserve_timeout() -> None:
    bridge = TerminalBridge()
    try:
        assert bridge._sealed_chat_options(
            "openrouter",
            {
                "require_served_identity": False,
                "timeout_sec": 17,
                "tools": [{"name": "shell"}],
            },
        ) == {
            "require_served_identity": True,
            "timeout_sec": 17,
        }
    finally:
        asyncio.run(bridge.close())


def test_helm_on_call_request_ignores_caller_truth_and_evaluates_empty_census(
    capsys,
) -> None:
    bridge = TerminalBridge()
    initial_epoch = bridge._runtime_owner_id
    assert bridge._helm_on_call_projection.state.value == "UNKNOWN"
    assert bridge._helm_on_call_projection.on_call_count is None

    try:
        asyncio.run(
            bridge._handle_request(
                {
                    "id": "helm-census",
                    "type": "helm.on_call.request",
                    "projection": {
                        "state": "ON_CALL",
                        "on_call_count": 7,
                    },
                }
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    event = next(item for item in emitted if item["type"] == "helm.on_call_projection")
    assert set(event) == {"type", "request_id", "projection"}
    assert event["request_id"] == "helm-census"
    projection = event["projection"]
    assert projection["state"] == "LIVE_DEGRADED"
    assert projection["on_call_count"] == 0
    assert projection["total"] == 7
    assert projection["runtime_epoch"] == initial_epoch
    assert [seat["seat_id"] for seat in projection["seats"]] == [
        "fable-5",
        "gpt-5.6",
        "grok-4.5-4.6-lineage",
        "fugu-ultra",
        "kimi-k3",
        "opus-5.0",
        "opus-4.8",
    ]
    assert all(seat["verdict"] == "UNKNOWN" for seat in projection["seats"])


def test_verified_claude_transcript_promotes_only_python_projection(
    tmp_path,
    capsys,
) -> None:
    prompt = "  route truth for Opus 4.8  \n"

    class VerifiedClaude:
        def get_profile(self, model):
            return _FakeProfile()

        async def cancel(self):
            return None

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionStart(
                provider_id="claude",
                session_id=session_id,
                model="claude-opus-4.8",
                provider_session_id="provider-verified-opus",
                tools_available=[],
                system_info={"permission_mode": "plan", "mcp_servers": []},
            )
            yield TextComplete(
                provider_id="claude",
                session_id=session_id,
                role="assistant",
                content="Verified no-tools reply.",
            )
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": VerifiedClaude()}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-opus-4.8", {}, "verified route")
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "verified-opus",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
                    "prompt": prompt,
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ack = next(item for item in emitted if item["type"] == "session.ack")
    event = next(item for item in emitted if item["type"] == "helm.on_call_projection")
    projection = event["projection"]
    assert projection["state"] == "LIVE_DEGRADED"
    assert projection["on_call_count"] == 1
    seat = projection["seats"][6]
    assert seat["seat_id"] == "opus-4.8"
    assert seat["verdict"] == "ON_CALL"
    assert seat["reason"] == "verified"
    assert seat["runtime_epoch"] == bridge._runtime_owner_id
    transcript = tmp_path / ack["session_id"] / "transcript.jsonl"
    assert seat["evidence"]["receipt_ref"] == str(transcript.resolve())
    assert seat["evidence"]["receipt_sha256"] == hashlib.sha256(transcript.read_bytes()).hexdigest()
    assert seat["evidence"]["served_provider"] == "claude_code"
    assert seat["evidence"]["served_model"] == "claude-opus-4.8"
    assert seat["evidence"]["age_seconds"] >= 0
    assert set(event) == {"type", "request_id", "projection"}


def test_openrouter_request_echo_cannot_promote_served_identity(
    tmp_path,
    capsys,
) -> None:
    class EchoOnlyOpenRouter:
        def get_profile(self, model):
            return _FakeProfile()

        async def cancel(self):
            return None

        async def close(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionStart(
                provider_id="openrouter",
                session_id=session_id,
                model="moonshotai/kimi-k3",
                tools_available=[],
                system_info={"base_url": "https://openrouter.ai/api/v1"},
            )
            yield TextComplete(
                provider_id="openrouter",
                session_id=session_id,
                role="assistant",
                content="A response whose served model was not proven.",
            )
            yield SessionEnd(provider_id="openrouter", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"openrouter": EchoOnlyOpenRouter()}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("openrouter", "moonshotai/kimi-k3", {}, "echo-only route")
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "echo-only-kimi",
                {
                    "provider": "openrouter",
                    "model": "moonshotai/kimi-k3",
                    "prompt": "prove the served Kimi identity",
                },
            )
        )
    finally:
        asyncio.run(bridge.close())

    emitted = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    projection = next(
        item["projection"] for item in emitted if item["type"] == "helm.on_call_projection"
    )
    kimi = projection["seats"][4]
    assert projection["on_call_count"] == 0
    assert kimi["seat_id"] == "kimi-k3"
    assert kimi["verdict"] == "REJECTED"
    assert kimi["reason"] == "verifier_decision_rejected"


def test_successful_chat_turn_persists_completed_replayable_session(tmp_path, capsys) -> None:
    class FakeAdapter:
        def get_profile(self, model):
            return _FakeProfile()

        async def close(self):
            return None

        async def cancel(self):
            return None

        async def stream(self, completion, *, session_id):
            yield SessionStart(
                provider_id="claude",
                session_id=session_id,
                model="claude-opus-4.8",
                provider_session_id="provider-chat-1",
                tools_available=[],
            )
            yield TextComplete(
                provider_id="claude",
                session_id=session_id,
                role="assistant",
                content="CHAT_DURABLE_OK",
            )
            yield UsageReport(
                provider_id="claude",
                session_id=session_id,
                input_tokens=11,
                output_tokens=7,
                total_cost_usd=0.25,
            )
            yield SessionEnd(provider_id="claude", session_id=session_id, success=True)

    bridge = TerminalBridge()
    bridge._session_store = SessionStore(root=tmp_path)
    bridge._adapters = {"claude": FakeAdapter()}
    bridge._completion_request_cls = _FakeCompletionRequest
    bridge._adapter_boot_error = None
    bridge._chat_lanes = lambda provider, model: [
        ("claude", "claude-opus-4.8", {}, "sealed")
    ]

    try:
        asyncio.run(
            bridge._handle_session_start(
                "chat-durable-start",
                {
                    "provider": "claude",
                    "model": "claude-opus-4.8",
                    "prompt": "prove the chat session is durable",
                    "bootstrap": {"intent": {"kind": "chat"}},
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
    assert meta["provider_session_id"] == "provider-chat-1"
    assert meta["parent_session_id"] is None
    assert [event.type for event in reopened.load_transcript(session_id)] == [
        "user_prompt",
        "session_start",
        "text_complete",
        "usage",
        "session_end",
    ]
    assert reopened.verify_session_replay(session_id) == (True, [])
    assert receipt["request_id"] == "chat-durable-start"
    assert receipt["session_id"] == session_id
    assert receipt["provider_id"] == "claude"
    assert receipt["model_id"] == "claude-opus-4.8"
    assert receipt["route_id"] == "claude:claude-opus-4.8"
    assert receipt["evidence_kind"] == "provider_completion"
    narration = next(event for event in emitted if event["type"] == "text_complete")
    assert narration["authority"] == "NONE"
    assert narration["narration_verified"] is False
    assert narration["state_promotion_allowed"] is False
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
