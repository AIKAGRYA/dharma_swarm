"""Tests for autonomous_agent.py — ReAct loop agents, tool execution, orchestrator."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dharma_swarm.autonomous_agent import (
    PRESET_AGENTS,
    TOOL_DEFINITIONS,
    AgentIdentity,
    AgentOrchestrator,
    AgentResult,
    AutonomousAgent,
    _DANGEROUS_PATTERNS,
    _identity_from_registered_holon,
    cli_wake,
)
from dharma_swarm.model_hierarchy import default_model as canonical_default_model
from dharma_swarm.models import ProviderType

# Cross-lane drift guard: the TUI-alias model resolver ships on the
# holon/spine-v1 lane and is absent here. Skip its tests instead of breaking
# collection for the whole module.
try:
    from dharma_swarm.autonomous_agent import _resolve_agent_model_override
except ImportError:
    _resolve_agent_model_override = None


# ---------------------------------------------------------------------------
# AgentResult dataclass
# ---------------------------------------------------------------------------


class TestAgentResult:
    def test_defaults(self):
        r = AgentResult(summary="done")
        assert r.summary == "done"
        assert r.turns == 0
        assert r.tokens_in == 0
        assert r.tokens_out == 0
        assert r.tool_calls_made == 0
        assert r.duration_s == 0.0
        assert r.errors == []

    def test_total_tokens(self):
        r = AgentResult(summary="x", tokens_in=100, tokens_out=50)
        assert r.total_tokens == 150

    def test_errors_independent(self):
        r1 = AgentResult(summary="a")
        r2 = AgentResult(summary="b")
        r1.errors.append("err")
        assert r2.errors == []


# ---------------------------------------------------------------------------
# AgentIdentity dataclass
# ---------------------------------------------------------------------------


class TestAgentIdentity:
    def test_defaults(self):
        ident = AgentIdentity(name="test", role="general", system_prompt="hi")
        assert ident.name == "test"
        assert ident.model == canonical_default_model(ProviderType.ANTHROPIC)
        assert ident.provider == "anthropic"
        assert ident.max_turns == 25
        assert len(ident.allowed_tools) > 0

    def test_allowed_tools_independent(self):
        a = AgentIdentity(name="a", role="x", system_prompt="y")
        b = AgentIdentity(name="b", role="x", system_prompt="y")
        a.allowed_tools.append("custom")
        assert "custom" not in b.allowed_tools

    def test_registered_holon_identity_uses_active_prompt(self, tmp_path):
        agent_dir = tmp_path / "registered_agent"
        (agent_dir / "prompt_variants").mkdir(parents=True)
        (agent_dir / "identity.json").write_text(
            json.dumps(
                {
                    "model": "gpt-5.5",
                    "provider": "codex",
                    "role": "lead_orchestrator",
                    "storage_root": str(agent_dir),
                    "system_prompt": "fallback prompt",
                }
            ),
            encoding="utf-8",
        )
        (agent_dir / "prompt_variants" / "active.txt").write_text(
            "REAL REGISTERED SOUL",
            encoding="utf-8",
        )

        ident = _identity_from_registered_holon(
            "registered_agent",
            agents_root=tmp_path,
        )

        assert ident is not None
        assert ident.name == "registered_agent"
        assert ident.role == "lead_orchestrator"
        assert ident.model == "gpt-5.5"
        assert ident.provider == "codex"
        assert ident.system_prompt == "REAL REGISTERED SOUL"
        # No declared tool contract -> the AgentIdentity default toolset.
        # (A hardcoded allowed_tools=[] used to wake every registered holon
        # permanently toolless.)
        default_tools = AgentIdentity(name="d", role="r", system_prompt="s").allowed_tools
        assert ident.allowed_tools == default_tools
        assert ident.working_directory == str(agent_dir)

    def test_registered_holon_identity_honors_declared_tools(self, tmp_path):
        agent_dir = tmp_path / "tooled_agent"
        (agent_dir / "prompt_variants").mkdir(parents=True)
        (agent_dir / "identity.json").write_text(
            json.dumps(
                {
                    "model": "gpt-5.5",
                    "provider": "codex",
                    "role": "lead_orchestrator",
                    "storage_root": str(agent_dir),
                    "system_prompt": "soul",
                    "allowed_tools": ["read_file", "bash"],
                }
            ),
            encoding="utf-8",
        )
        (agent_dir / "prompt_variants" / "active.txt").write_text(
            "soul", encoding="utf-8"
        )
        ident = _identity_from_registered_holon("tooled_agent", agents_root=tmp_path)
        assert ident is not None
        assert ident.allowed_tools == ["read_file", "bash"]

    def test_unregistered_holon_identity_returns_none(self, tmp_path):
        assert _identity_from_registered_holon("missing", agents_root=tmp_path) is None

    def test_generic_stub_still_available_for_unregistered_name(self):
        agent_name = "not_registered_anywhere"
        ident = _identity_from_registered_holon(
            agent_name,
            agents_root=Path("/tmp/nope"),
        )
        assert ident is None
        stub = AgentIdentity(
            name=agent_name,
            role="general",
            system_prompt=f"You are {agent_name}, an autonomous agent in dharma_swarm.",
        )
        prompt = AutonomousAgent(stub)._build_system_prompt("", [])
        assert f"You are {agent_name}, an autonomous agent in dharma_swarm." in prompt

    def test_real_registered_composer_souls_compose_into_prompt(self):
        cases = [
            ("fable_composer", "This file is not documentation about a seat"),
            ("codex_composer", "TaskClaim versus ExecutionLease boundary"),
        ]
        for name, fragment in cases:
            identity_path = Path.home() / ".dharma" / "agents" / name / "identity.json"
            if not identity_path.exists():
                pytest.skip(f"{name} not registered on this machine")
            ident = _identity_from_registered_holon(name)
            assert ident is not None
            prompt = AutonomousAgent(ident)._build_system_prompt("", [])
            assert fragment in prompt


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_all_have_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_expected_tools_present(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "read_file", "write_file", "bash", "search_files",
            "search_content", "message_agent", "remember", "recall",
            "stigmergy_mark", "stigmergy_read",
        }
        assert expected <= names


# ---------------------------------------------------------------------------
# Dangerous patterns
# ---------------------------------------------------------------------------


class TestDangerousPatterns:
    def test_has_entries(self):
        assert len(_DANGEROUS_PATTERNS) > 5

    def test_rm_rf_blocked(self):
        assert "rm -rf" in _DANGEROUS_PATTERNS

    def test_sudo_blocked(self):
        assert "sudo" in _DANGEROUS_PATTERNS


# ---------------------------------------------------------------------------
# AutonomousAgent — construction and system prompt
# ---------------------------------------------------------------------------


class TestAutonomousAgentConstruction:
    def test_init(self):
        ident = AgentIdentity(name="test", role="coder", system_prompt="You code.")
        agent = AutonomousAgent(ident)
        assert agent.identity.name == "test"
        assert agent.memory is not None

    def test_build_system_prompt_basic(self):
        ident = AgentIdentity(name="test", role="coder", system_prompt="Base prompt.")
        agent = AutonomousAgent(ident)
        prompt = agent._build_system_prompt("", [])
        assert "Base prompt." in prompt
        assert "test" in prompt
        assert "coder" in prompt

    def test_build_system_prompt_with_memory(self):
        ident = AgentIdentity(name="test", role="coder", system_prompt="Base.")
        agent = AutonomousAgent(ident)
        prompt = agent._build_system_prompt("I remember X happened.", [])
        assert "I remember X happened." in prompt
        assert "Memory" in prompt

    def test_build_system_prompt_with_inbox(self):
        ident = AgentIdentity(name="test", role="coder", system_prompt="Base.")
        agent = AutonomousAgent(ident)
        prompt = agent._build_system_prompt("", ["From alice: check this"])
        assert "From alice: check this" in prompt
        assert "Inbox" in prompt

    def test_get_tool_definitions_filters(self):
        ident = AgentIdentity(
            name="test", role="reader", system_prompt="Read only.",
            allowed_tools=["read_file", "recall"],
        )
        agent = AutonomousAgent(ident)
        defs = agent._get_tool_definitions()
        names = {d["name"] for d in defs}
        assert names == {"read_file", "recall"}


# ---------------------------------------------------------------------------
# Tool execution — file tools
# ---------------------------------------------------------------------------


class TestToolFileOperations:
    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_read_file({"path": str(f)})
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_read_file_missing(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_read_file({"path": "/nonexistent/file.txt"})
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_read_file_truncates_large(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * 60000)
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_read_file({"path": str(f)})
        assert "truncated" in result
        assert len(result) < 55000

    @pytest.mark.asyncio
    async def test_write_file(self, tmp_path):
        target = tmp_path / "sub" / "out.txt"
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_write_file({"path": str(target), "content": "data"})
        assert "Wrote" in result
        assert target.read_text() == "data"

    @pytest.mark.asyncio
    async def test_search_files(self, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        (tmp_path / "c.txt").touch()
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_search_files(
            {"pattern": "*.py", "directory": str(tmp_path)},
        )
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    @pytest.mark.asyncio
    async def test_search_files_no_match(self, tmp_path):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_search_files(
            {"pattern": "*.xyz", "directory": str(tmp_path)},
        )
        assert "No files" in result


# ---------------------------------------------------------------------------
# Tool execution — bash
# ---------------------------------------------------------------------------


class TestToolBash:
    @pytest.mark.asyncio
    async def test_bash_simple(self, tmp_path):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s",
            working_directory=str(tmp_path),
        )
        agent = AutonomousAgent(ident)
        result = await agent._tool_bash({"command": "echo hello"})
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_bash_blocked_rm_rf(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_bash({"command": "rm -rf /"})
        assert "BLOCKED" in result

    @pytest.mark.asyncio
    async def test_bash_blocked_sudo(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = await agent._tool_bash({"command": "sudo rm file"})
        assert "BLOCKED" in result

    @pytest.mark.asyncio
    async def test_bash_timeout(self, tmp_path):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s",
            working_directory=str(tmp_path),
        )
        agent = AutonomousAgent(ident)
        result = await agent._tool_bash({"command": "sleep 10", "timeout": 1})
        assert "Timed out" in result


# ---------------------------------------------------------------------------
# Tool execution — dispatch and allowed_tools
# ---------------------------------------------------------------------------


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_disallowed_tool_blocked(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s",
            allowed_tools=["read_file"],
        )
        agent = AutonomousAgent(ident)
        result = await agent._execute_tool("bash", {"command": "echo hi"})
        assert "not allowed" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s",
            allowed_tools=["nonexistent_tool"],
        )
        agent = AutonomousAgent(ident)
        result = await agent._execute_tool("nonexistent_tool", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_gate_crash_fails_closed(self, monkeypatch, tmp_path):
        # A crashed telos gate must refuse the side-effect tool, not wave it
        # through (the pre-2026-07-07 behavior was `except Exception: pass`).
        def boom(**kwargs):
            raise RuntimeError("gate down")

        monkeypatch.setattr("dharma_swarm.telos_gates.check_action", boom)
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s",
            allowed_tools=["bash", "read_file"],
            working_directory=str(tmp_path),
        )
        agent = AutonomousAgent(ident)
        result = await agent._execute_tool("bash", {"command": "echo hi"})
        assert "GATE UNAVAILABLE" in result
        assert "hi" not in result.splitlines()[-1]  # command did not run

        # Non-side-effect tools are unaffected by a downed gate.
        probe = tmp_path / "probe.txt"
        probe.write_text("ok")
        result2 = await agent._execute_tool("read_file", {"path": str(probe)})
        assert "GATE UNAVAILABLE" not in result2


# ---------------------------------------------------------------------------
# Message format conversion
# ---------------------------------------------------------------------------


class TestOpenAIMessageConversion:
    def test_string_content(self):
        msg = {"role": "user", "content": "hello"}
        result = AutonomousAgent._to_openai_message(msg)
        assert result == {"role": "user", "content": "hello"}

    def test_tool_result_content(self):
        msg = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "result text"},
            ],
        }
        result = AutonomousAgent._to_openai_message(msg)
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "t1"
        assert result["content"] == "result text"

    def test_assistant_with_text_blocks(self):
        msg = {
            "role": "assistant",
            "content": [
                SimpleNamespace(type="text", text="Hello "),
                SimpleNamespace(type="text", text="world"),
            ],
        }
        result = AutonomousAgent._to_openai_message(msg)
        assert result["role"] == "assistant"
        assert result["content"] == "Hello world"

    def test_assistant_with_dict_blocks(self):
        msg = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "analysis"},
                {
                    "type": "tool_use", "id": "tu1",
                    "name": "read_file", "input": {"path": "/tmp/x"},
                },
            ],
        }
        result = AutonomousAgent._to_openai_message(msg)
        assert result["role"] == "assistant"
        assert "analysis" in (result.get("content") or "")
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "tu1"

    def test_fallback_stringifies(self):
        msg = {"role": "user", "content": [42, 43]}
        result = AutonomousAgent._to_openai_message(msg)
        assert result["role"] == "user"
        assert isinstance(result["content"], str)


# ---------------------------------------------------------------------------
# ReAct loop (mocked LLM)
# ---------------------------------------------------------------------------


class TestReActLoop:
    @pytest.mark.asyncio
    async def test_single_turn_no_tools(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)

        mock_resp = {
            "text": ["I analyzed the task."],
            "tool_uses": [],
            "raw_content": "I analyzed the task.",
            "stop_reason": "end_turn",
            "tokens_in": 50,
            "tokens_out": 20,
        }
        agent._call_llm = AsyncMock(return_value=mock_resp)

        result = await agent._reason_and_act("system prompt", "do something")
        assert result.summary == "I analyzed the task."
        assert result.turns == 1
        assert result.tokens_in == 50
        assert result.tokens_out == 20
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_tool_use_then_finish(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("important content")

        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)

        # Turn 1: LLM wants to read a file
        turn1 = {
            "text": [],
            "tool_uses": [{"id": "tu1", "name": "read_file", "input": {"path": str(f)}}],
            "raw_content": [{"type": "tool_use", "id": "tu1", "name": "read_file", "input": {"path": str(f)}}],
            "stop_reason": "tool_use",
            "tokens_in": 50,
            "tokens_out": 30,
        }
        # Turn 2: LLM done
        turn2 = {
            "text": ["Found the content."],
            "tool_uses": [],
            "raw_content": "Found the content.",
            "stop_reason": "end_turn",
            "tokens_in": 80,
            "tokens_out": 15,
        }
        agent._call_llm = AsyncMock(side_effect=[turn1, turn2])

        result = await agent._reason_and_act("system", "read the file")
        assert result.turns == 2
        assert result.tool_calls_made == 1
        assert result.tokens_in == 130  # 50 + 80
        assert "Found the content" in result.summary

    @pytest.mark.asyncio
    async def test_max_turns_reached(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s", max_turns=2)
        agent = AutonomousAgent(ident)

        # Both turns want tools, never finishes
        resp = {
            "text": ["working..."],
            "tool_uses": [{"id": "tu1", "name": "recall", "input": {"query": "x"}}],
            "raw_content": [{"type": "tool_use", "id": "tu1", "name": "recall", "input": {"query": "x"}}],
            "stop_reason": "tool_use",
            "tokens_in": 10,
            "tokens_out": 10,
        }
        agent._call_llm = AsyncMock(return_value=resp)
        # Mock recall to return something
        agent._tool_recall = AsyncMock(return_value="No memories")

        result = await agent._reason_and_act("system", "loop forever")
        assert result.turns == 2
        assert any("max turns" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_llm_error_breaks_loop(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        agent._call_llm = AsyncMock(side_effect=RuntimeError("API down"))

        result = await agent._reason_and_act("system", "task")
        # Error breaks the loop, but falls through to max_turns return
        assert any("API down" in e for e in result.errors)
        # Only 1 LLM call attempted (broke on first error)
        assert agent._call_llm.await_count == 1


# ---------------------------------------------------------------------------
# Wake lifecycle (mocked internals)
# ---------------------------------------------------------------------------


class TestWakeLifecycle:
    @pytest.mark.asyncio
    async def test_wake_full_lifecycle(self, tmp_path):
        ident = AgentIdentity(name="lifecycle_test", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)

        # Mock all subsystems
        agent.memory = MagicMock()
        agent.memory.load = AsyncMock()
        agent.memory.get_working_context = AsyncMock(return_value="")
        agent.memory.remember = AsyncMock()
        agent.memory.save = AsyncMock()
        agent._check_inbox = AsyncMock(return_value=[])
        agent._save_run_report = AsyncMock()

        mock_resp = {
            "text": ["Done."],
            "tool_uses": [],
            "raw_content": "Done.",
            "stop_reason": "end_turn",
            "tokens_in": 10,
            "tokens_out": 5,
        }
        agent._call_llm = AsyncMock(return_value=mock_resp)

        result = await agent.wake("test task")
        assert result.summary == "Done."
        agent.memory.load.assert_awaited_once()
        agent.memory.save.assert_awaited_once()
        agent.memory.remember.assert_awaited_once()
        agent._save_run_report.assert_awaited_once()


# ---------------------------------------------------------------------------
# AgentOrchestrator
# ---------------------------------------------------------------------------


class TestAgentOrchestrator:
    def test_register(self):
        orch = AgentOrchestrator()
        ident = AgentIdentity(name="a1", role="r", system_prompt="s")
        agent = orch.register(ident)
        assert "a1" in orch.agents
        assert isinstance(agent, AutonomousAgent)

    @pytest.mark.asyncio
    async def test_dispatch_unknown_raises(self):
        orch = AgentOrchestrator()
        with pytest.raises(ValueError, match="Unknown agent"):
            await orch.dispatch("nonexistent", "task")

    @pytest.mark.asyncio
    async def test_dispatch(self):
        orch = AgentOrchestrator()
        ident = AgentIdentity(name="a1", role="r", system_prompt="s")
        agent = orch.register(ident)

        mock_result = AgentResult(summary="done", turns=1, tokens_in=10, tokens_out=5)
        agent.wake = AsyncMock(return_value=mock_result)

        result = await orch.dispatch("a1", "do work")
        assert result.summary == "done"
        assert len(orch._run_log) == 1
        assert orch._run_log[0]["agent"] == "a1"

    @pytest.mark.asyncio
    async def test_broadcast(self):
        orch = AgentOrchestrator()
        for name in ("a1", "a2"):
            ident = AgentIdentity(name=name, role="r", system_prompt="s")
            agent = orch.register(ident)
            agent.wake = AsyncMock(
                return_value=AgentResult(summary=f"{name} done"),
            )

        results = await orch.broadcast("shared task")
        assert "a1" in results
        assert "a2" in results
        assert results["a1"].summary == "a1 done"

    @pytest.mark.asyncio
    async def test_broadcast_handles_errors(self):
        orch = AgentOrchestrator()
        ident = AgentIdentity(name="a1", role="r", system_prompt="s")
        agent = orch.register(ident)
        agent.wake = AsyncMock(side_effect=RuntimeError("boom"))

        results = await orch.broadcast("task")
        assert "a1" in results
        assert len(results["a1"].errors) > 0


# ---------------------------------------------------------------------------
# PRESET_AGENTS
# ---------------------------------------------------------------------------


class TestPresetAgents:
    def test_has_expected_agents(self):
        expected = {"researcher", "coder", "scout", "reviewer", "witness"}
        assert expected <= set(PRESET_AGENTS.keys())

    def test_all_have_required_fields(self):
        for name, ident in PRESET_AGENTS.items():
            assert ident.name == name
            assert ident.role
            assert ident.system_prompt
            assert ident.model
            assert len(ident.allowed_tools) > 0

    def test_witness_has_no_write(self):
        """Witness agent should not have write_file tool."""
        witness = PRESET_AGENTS["witness"]
        assert "write_file" not in witness.allowed_tools

    @pytest.mark.skipif(
        _resolve_agent_model_override is None,
        reason="claude_code preset lane not on this branch (holon/spine-v1 lane drift)",
    )
    def test_preset_agents_use_subscription_claude_code_lane(self):
        for ident in PRESET_AGENTS.values():
            assert ident.provider == "claude_code"
            assert ident.model == "claude-sonnet-4-6"


@pytest.mark.skipif(
    _resolve_agent_model_override is None,
    reason="_resolve_agent_model_override not on this branch (holon/spine-v1 lane drift)",
)
class TestCliWakeModelRouting:
    def test_resolves_tui_model_aliases(self):
        assert _resolve_agent_model_override("gemini") == (
            "openrouter_direct",
            "google/gemini-2.5-pro",
        )
        assert _resolve_agent_model_override("glm-5") == ("ollama", "glm-5:cloud")
        assert _resolve_agent_model_override("codex") == ("codex", "gpt-5.4")

    def test_resolves_explicit_provider_model_route(self):
        assert _resolve_agent_model_override("openrouter:anthropic/claude-opus-4-6") == (
            "openrouter_direct",
            "anthropic/claude-opus-4-6",
        )
        assert _resolve_agent_model_override("google_ai:gemini-2.5-flash") == (
            "google_ai",
            "gemini-2.5-flash",
        )

    @pytest.mark.asyncio
    async def test_cli_wake_model_override_does_not_mutate_preset(self, monkeypatch, capsys):
        original = PRESET_AGENTS["reviewer"]
        captured: list[AgentIdentity] = []

        async def fake_wake(self, task):
            captured.append(self.identity)
            assert task == "check routing"
            return AgentResult(summary="done")

        monkeypatch.setattr(AutonomousAgent, "wake", fake_wake)

        await cli_wake("reviewer", "check routing", model="gemini")

        assert captured
        assert captured[0].provider == "openrouter_direct"
        assert captured[0].model == "google/gemini-2.5-pro"
        assert PRESET_AGENTS["reviewer"] is original
        assert PRESET_AGENTS["reviewer"].provider == "claude_code"
        assert PRESET_AGENTS["reviewer"].model == "claude-sonnet-4-6"
        assert "Waking reviewer on openrouter:google/gemini-2.5-pro" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# LLM provider dispatch
# ---------------------------------------------------------------------------


class TestCallLLM:
    @pytest.mark.asyncio
    async def test_unsupported_provider_raises(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s", provider="unknown",
        )
        agent = AutonomousAgent(ident)
        with pytest.raises(ValueError, match="Unsupported provider"):
            await agent._call_llm("sys", [], [])

    @pytest.mark.asyncio
    async def test_anthropic_dispatch(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s", provider="anthropic",
        )
        agent = AutonomousAgent(ident)
        agent._call_anthropic = AsyncMock(return_value={"text": [], "tool_uses": []})
        await agent._call_llm("sys", [], [])
        agent._call_anthropic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_openrouter_dispatch(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s", provider="openrouter",
        )
        agent = AutonomousAgent(ident)
        agent._call_openrouter = AsyncMock(return_value={"text": [], "tool_uses": []})
        await agent._call_llm("sys", [], [])
        agent._call_openrouter.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_codex_dispatch(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s", provider="codex",
        )
        agent = AutonomousAgent(ident)
        agent._call_codex = AsyncMock(return_value={"text": [], "tool_uses": []})
        await agent._call_llm("sys", [], [])
        agent._call_codex.assert_awaited_once()

    @pytest.mark.skipif(
        _resolve_agent_model_override is None,
        reason="claude_code dispatch lane not on this branch (holon/spine-v1 lane drift)",
    )
    @pytest.mark.asyncio
    async def test_claude_code_dispatch(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s", provider="claude_code",
        )
        agent = AutonomousAgent(ident)
        agent._call_claude_code = AsyncMock(return_value={"text": [], "tool_uses": []})
        await agent._call_llm("sys", [], [])
        agent._call_claude_code.assert_awaited_once()

    @pytest.mark.skipif(
        _resolve_agent_model_override is None,
        reason="openrouter_direct dispatch lane not on this branch (holon/spine-v1 lane drift)",
    )
    @pytest.mark.asyncio
    async def test_openrouter_direct_dispatch(self):
        ident = AgentIdentity(
            name="t", role="r", system_prompt="s", provider="openrouter_direct",
        )
        agent = AutonomousAgent(ident)
        agent._call_direct_runtime_provider = AsyncMock(return_value={"text": [], "tool_uses": []})
        await agent._call_llm("sys", [], [])
        agent._call_direct_runtime_provider.assert_awaited_once_with(
            ProviderType.OPENROUTER, "sys", [], []
        )


# ---------------------------------------------------------------------------
# Memory and stigmergy tools (mocked backends)
# ---------------------------------------------------------------------------


class TestMemoryTools:
    @pytest.mark.asyncio
    async def test_remember(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        agent.memory = MagicMock()
        agent.memory.remember = AsyncMock()

        result = await agent._tool_remember({"key": "fact", "value": "earth is round"})
        assert "Remembered" in result
        agent.memory.remember.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_recall_no_results(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        agent.memory = MagicMock()
        agent.memory.search = AsyncMock(return_value=[])

        result = await agent._tool_recall({"query": "anything"})
        assert "No memories" in result

    @pytest.mark.asyncio
    async def test_recall_with_results(self):
        ident = AgentIdentity(name="t", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)

        entry = SimpleNamespace(importance=0.8, key="fact", value="earth is round")
        agent.memory = MagicMock()
        agent.memory.search = AsyncMock(return_value=[entry])

        result = await agent._tool_recall({"query": "earth"})
        assert "earth is round" in result
        assert "0.8" in result


# ---------------------------------------------------------------------------
# Save run report
# ---------------------------------------------------------------------------


class TestSaveRunReport:
    @pytest.mark.asyncio
    async def test_saves_report_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ident = AgentIdentity(name="reporter", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        result = AgentResult(
            summary="task done", turns=3, tokens_in=100, tokens_out=50,
            tool_calls_made=2, duration_s=5.5,
        )
        await agent._save_run_report("test task", result)

        report_file = tmp_path / ".dharma" / "agent_runs" / "reporter_latest.json"
        assert report_file.exists()
        data = json.loads(report_file.read_text())
        assert data["agent"] == "reporter"
        assert data["turns"] == 3
        assert data["tokens_in"] == 100


class TestCheckInboxMarksRead:
    """Regression: fetched inbox messages must eventually be marked read so the
    same message is not re-injected into the system prompt every cycle, BUT the
    acknowledgement is deferred to wake success so a failed wake does not
    permanently hide messages (mirrors the consumer pattern in
    contracts/runtime_adapters.py)."""

    @staticmethod
    async def _make_agent_with_message(tmp_path):
        from dharma_swarm.message_bus import MessageBus
        from dharma_swarm.models import Message

        bus = MessageBus(tmp_path / "messages.db")
        await bus.init_db()
        await bus.send(Message(
            from_agent="peer", to_agent="listener",
            subject="ping", body="please look at this",
        ))
        ident = AgentIdentity(name="listener", role="r", system_prompt="s")
        agent = AutonomousAgent(ident)
        agent._message_bus = bus
        return agent, bus

    @pytest.mark.asyncio
    async def test_check_inbox_defers_ack(self, tmp_path):
        agent, bus = await self._make_agent_with_message(tmp_path)

        first = await agent._check_inbox()
        assert len(first) == 1
        assert "ping" in first[0]

        # Deferred: NOT marked read yet, but queued for acknowledgement.
        assert len(await bus.receive("listener", status="unread")) == 1
        assert len(agent._inbox_pending_ack) == 1

    @pytest.mark.asyncio
    async def test_handled_message_not_refetched_after_ack(self, tmp_path):
        agent, bus = await self._make_agent_with_message(tmp_path)

        first = await agent._check_inbox()
        assert len(first) == 1

        # Wake succeeded -> acknowledge the delivered messages.
        await agent._ack_inbox()

        # Second cycle: the handled message must NOT come back.
        second = await agent._check_inbox()
        assert second == []

        # Store confirms the message was marked read, not deleted.
        assert await bus.receive("listener", status="unread") == []
        assert len(await bus.receive("listener", status="read")) == 1
        assert agent._inbox_pending_ack == []

    @pytest.mark.asyncio
    async def test_wake_failure_leaves_messages_unread(self, tmp_path):
        agent, bus = await self._make_agent_with_message(tmp_path)

        # Isolate the wake from real memory/report subsystems.
        agent.memory = MagicMock()
        agent.memory.load = AsyncMock()
        agent.memory.get_working_context = AsyncMock(return_value="")
        agent.memory.remember = AsyncMock()
        agent.memory.save = AsyncMock()
        agent._save_run_report = AsyncMock()

        # The reason+act loop blows up (e.g. provider failure) mid-wake.
        agent._reason_and_act = AsyncMock(side_effect=RuntimeError("provider down"))

        with pytest.raises(RuntimeError, match="provider down"):
            await agent.wake("task")

        # Ack never ran: the message stays unread for the next cycle to retry.
        assert len(await bus.receive("listener", status="unread")) == 1
        assert await bus.receive("listener", status="read") == []
        assert len(agent._inbox_pending_ack) == 1

        # A later successful re-check + ack still delivers and clears it.
        second = await agent._check_inbox()
        assert len(second) == 1
        await agent._ack_inbox()
        assert await bus.receive("listener", status="unread") == []
