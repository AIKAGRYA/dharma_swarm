"""Integration tests for tool loop helpers in agent_runner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from dharma_swarm.agent_runner import (
    _parse_tool_calls_from_text,
    _requires_tooling,
    _resolve_local_tool_path,
)
from dharma_swarm.models import AgentConfig, AgentRole, ProviderType, Task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def researcher_config():
    return AgentConfig(name="r", role=AgentRole.RESEARCHER, provider=ProviderType.OLLAMA, model="m")


@pytest.fixture
def simple_task():
    return Task(id="t1", title="summarize findings")


# ---------------------------------------------------------------------------
# _requires_tooling
# ---------------------------------------------------------------------------

class TestRequiresTooling:
    def test_coder_role_always_requires_tooling(self):
        config = AgentConfig(name="c", role=AgentRole.CODER, provider=ProviderType.OLLAMA, model="m")
        task = Task(id="t", title="do something")
        assert _requires_tooling(task, config) is True

    def test_surgeon_role_always_requires_tooling(self):
        config = AgentConfig(name="s", role=AgentRole.SURGEON, provider=ProviderType.OLLAMA, model="m")
        task = Task(id="t", title="do something")
        assert _requires_tooling(task, config) is True

    def test_tooling_hint_in_title_triggers(self, researcher_config):
        task = Task(id="t", title="research the topic and write a report")
        assert _requires_tooling(task, researcher_config) is True

    def test_no_tooling_hint_returns_false(self, researcher_config):
        task = Task(id="t", title="summarize findings")
        assert _requires_tooling(task, researcher_config) is False

    def test_metadata_override_true(self, researcher_config):
        task = Task(id="t", title="plain title", metadata={"requires_tooling": True})
        assert _requires_tooling(task, researcher_config) is True

    def test_metadata_override_false_beats_hint(self):
        config = AgentConfig(name="c", role=AgentRole.CODER, provider=ProviderType.OLLAMA, model="m")
        task = Task(id="t", title="code fix", metadata={"requires_tooling": False})
        # metadata override False takes precedence even over CODER role via _metadata_bool
        # but CODER role check comes after _metadata_bool override check
        result = _requires_tooling(task, config)
        # metadata False → returns False (override is before role check)
        assert result is False


# ---------------------------------------------------------------------------
# _resolve_local_tool_path
# ---------------------------------------------------------------------------

class TestResolveLocalToolPath:
    def test_tilde_slash_path(self, tmp_path):
        home = Path.home()
        result = _resolve_local_tool_path("~/Documents", workdir=tmp_path)
        assert result == (home / "Documents").resolve(strict=False)

    def test_tilde_only_path(self, tmp_path):
        home = Path.home()
        result = _resolve_local_tool_path("~/.dharma/state", workdir=tmp_path)
        assert result == (home / ".dharma/state").resolve(strict=False)

    def test_home_user_hallucination(self, tmp_path):
        home = Path.home()
        result = _resolve_local_tool_path("/home/user/Documents", workdir=tmp_path)
        assert result == (home / "Documents").resolve(strict=False)

    def test_home_dhyana_path(self, tmp_path):
        home = Path.home()
        result = _resolve_local_tool_path("/home/dhyana/dharma_swarm", workdir=tmp_path)
        assert result == (home / "dharma_swarm").resolve(strict=False)

    def test_relative_path_resolved_against_workdir(self, tmp_path):
        result = _resolve_local_tool_path("subdir/file.txt", workdir=tmp_path)
        assert result == (tmp_path / "subdir/file.txt").resolve(strict=False)

    def test_absolute_path_unchanged(self, tmp_path):
        result = _resolve_local_tool_path("/tmp/some_file.txt", workdir=tmp_path)
        assert result == Path("/tmp/some_file.txt").resolve(strict=False)


# ---------------------------------------------------------------------------
# _parse_tool_calls_from_text
# ---------------------------------------------------------------------------

class TestParseToolCallsFromText:
    KNOWN = {"web_search", "read_file", "shell_exec"}

    def test_xml_pattern(self):
        text = '<tool_call>{"name": "web_search", "arguments": {"query": "AI news"}}</tool_call>'
        calls = _parse_tool_calls_from_text(text, known_tools=self.KNOWN)
        assert len(calls) == 1
        assert calls[0]["name"] == "web_search"
        args = json.loads(calls[0]["arguments"])
        assert args["query"] == "AI news"

    def test_react_pattern(self):
        text = "Action: read_file\nAction Input: {\"path\": \"/tmp/foo.txt\"}"
        calls = _parse_tool_calls_from_text(text, known_tools=self.KNOWN)
        assert len(calls) == 1
        assert calls[0]["name"] == "read_file"
        args = json.loads(calls[0]["arguments"])
        assert args["path"] == "/tmp/foo.txt"

    def test_bare_json_pattern(self):
        text = '{"name": "shell_exec", "arguments": {"command": "ls"}}'
        calls = _parse_tool_calls_from_text(text, known_tools=self.KNOWN)
        assert len(calls) == 1
        assert calls[0]["name"] == "shell_exec"

    def test_unknown_tool_filtered_out(self):
        text = '<tool_call>{"name": "unknown_tool", "arguments": {}}</tool_call>'
        calls = _parse_tool_calls_from_text(text, known_tools=self.KNOWN)
        assert calls == []

    def test_no_known_tools_filter_passes_all(self):
        text = '<tool_call>{"name": "anything", "arguments": {}}</tool_call>'
        calls = _parse_tool_calls_from_text(text, known_tools=None)
        assert len(calls) == 1
        assert calls[0]["name"] == "anything"

    def test_empty_text_returns_empty(self):
        assert _parse_tool_calls_from_text("", known_tools=self.KNOWN) == []
        assert _parse_tool_calls_from_text("   ", known_tools=self.KNOWN) == []

    def test_call_id_generated(self):
        text = '<tool_call>{"name": "web_search", "arguments": {"query": "x"}}</tool_call>'
        calls = _parse_tool_calls_from_text(text, known_tools=self.KNOWN)
        assert calls[0]["id"].startswith("text_")

    def test_xml_priority_over_react(self):
        # When XML match exists, ReAct should not add duplicate
        text = (
            '<tool_call>{"name": "web_search", "arguments": {"query": "x"}}</tool_call>\n'
            "Action: web_search\nAction Input: {\"query\": \"y\"}"
        )
        calls = _parse_tool_calls_from_text(text, known_tools=self.KNOWN)
        # XML pattern wins and returns early
        assert len(calls) == 1
        args = json.loads(calls[0]["arguments"])
        assert args["query"] == "x"


# ---------------------------------------------------------------------------
# web_search handler (mock HTTP)
# ---------------------------------------------------------------------------

class TestWebSearchHandler:
    @pytest.mark.asyncio
    async def test_web_search_returns_results(self, tmp_path):
        """AgentRunner._execute_local_tool web_search path returns mocked results."""
        from dharma_swarm.agent_runner import AgentRunner
        from dharma_swarm.models import Task

        config = AgentConfig(
            name="ws-agent",
            role=AgentRole.RESEARCHER,
            provider=ProviderType.OLLAMA,
            model="m",
        )
        runner = AgentRunner(config)
        await runner.start()

        task = Task(id="t", title="web search test")

        mock_results = "Result 1: some content\nResult 2: more content"
        with patch(
            "dharma_swarm.web_search.search_web",
            new=AsyncMock(return_value=mock_results),
        ):
            result = await runner._execute_local_tool(
                "web_search",
                {"query": "AI safety", "max_results": 3},
                task=task,
            )
        assert result == mock_results

    @pytest.mark.asyncio
    async def test_web_search_empty_query_returns_error(self, tmp_path):
        """web_search with empty query returns ERROR string."""
        from dharma_swarm.agent_runner import AgentRunner

        config = AgentConfig(
            name="ws-agent",
            role=AgentRole.RESEARCHER,
            provider=ProviderType.OLLAMA,
            model="m",
        )
        runner = AgentRunner(config)
        await runner.start()

        task = Task(id="t", title="web search test")

        with patch("dharma_swarm.web_search.search_web", new=AsyncMock(return_value="")):
            result = await runner._execute_local_tool("web_search", {"query": ""}, task=task)

        assert result.startswith("ERROR")

    @pytest.mark.asyncio
    async def test_web_search_exception_returns_error_string(self):
        """web_search backend exception is caught and returned as ERROR string."""
        from dharma_swarm.agent_runner import AgentRunner

        config = AgentConfig(
            name="ws-agent",
            role=AgentRole.RESEARCHER,
            provider=ProviderType.OLLAMA,
            model="m",
        )
        runner = AgentRunner(config)
        await runner.start()

        task = Task(id="t", title="web search test")

        with patch(
            "dharma_swarm.web_search.search_web",
            new=AsyncMock(side_effect=RuntimeError("network down")),
        ):
            result = await runner._execute_local_tool(
                "web_search", {"query": "something"}, task=task
            )

        assert "ERROR" in result
        assert "web_search" in result.lower() or "network down" in result
