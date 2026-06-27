"""Regression coverage for the Bun terminal stdio bridge."""

from __future__ import annotations

import asyncio
import json

from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.terminal_bridge import TerminalBridge, system_commands_module
from dharma_swarm.tui.engine.events import SessionEnd, ToolCallComplete, ToolResult


def test_terminal_bridge_loads_tui_command_surface() -> None:
    assert system_commands_module is not None
    assert "status" in system_commands_module._ALL_COMMANDS


def test_terminal_bridge_bootstraps_commands_and_adapters() -> None:
    bridge = TerminalBridge()

    try:
        graph = bridge._build_command_graph_summary()
        assert bridge._adapter_boot_error is None
        assert bridge._commands is not None
        assert {"claude", "codex", "openrouter"}.issubset(bridge._available_provider_ids())
        assert "status" in graph["commands"]
    finally:
        # The constructors do not start provider streams, but keep the close path
        # explicit so future adapter resources do not leak in this test.
        import asyncio

        asyncio.run(bridge.close())


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
                content="/Users/dhyana/dharma_swarm",
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
