"""Tests for ClaudeAdapter canonical normalization (v1.1 layer)."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest

from dharma_swarm.tui.engine.adapters.base import CompletionRequest, ProviderConfig
from dharma_swarm.tui.engine.adapters.claude import ClaudeAdapter
from dharma_swarm.tui.engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    TextDelta,
    ThinkingComplete,
    ThinkingDelta,
    ToolArgumentsDelta,
    ToolCallComplete,
    ToolProgress,
    ToolResult,
    UsageReport,
)


def _j(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"))


def _adapter() -> ClaudeAdapter:
    return ClaudeAdapter(config=ProviderConfig(provider_id="claude", default_model="claude-sonnet-4-5"))


def test_build_command_is_permission_checked_by_default() -> None:
    cmd = _adapter()._build_command(
        CompletionRequest(messages=[{"role": "user", "content": "inspect the repo"}])
    )

    permission_index = cmd.index("--permission-mode")
    assert cmd[permission_index + 1] == "default"
    assert "--dangerously-skip-permissions" not in cmd
    assert "--allowedTools" not in cmd


def test_build_env_clears_all_nested_claude_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "nested")
    monkeypatch.setenv("CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES", "true")
    monkeypatch.setenv("HELM_ENV_SENTINEL", "preserved")

    env = _adapter()._build_env(
        CompletionRequest(messages=[{"role": "user", "content": "hello"}])
    )

    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_ENTRYPOINT" not in env
    assert "CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES" not in env
    assert env["HELM_ENV_SENTINEL"] == "preserved"


def test_subscription_only_environment_cannot_be_forced_to_metered_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "metered-key-must-not-cross")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "metered-token-must-not-cross")
    monkeypatch.setenv("DHARMA_FORCE_ANTHROPIC_API", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-openai-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unrelated-router-secret")
    monkeypatch.setenv("KIMI_API_KEY", "unrelated-kimi-secret")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://unrelated-cloud.invalid")
    monkeypatch.setenv("XAI_API_KEY", "unrelated-xai-secret")
    monkeypatch.setenv("UNREGISTERED_VENDOR_SECRET", "must-not-cross")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-cross")
    monkeypatch.setenv("HELM_ENV_SENTINEL", "preserved")

    env = _adapter()._build_env(
        CompletionRequest(
            messages=[{"role": "user", "content": "hello"}],
            provider_options={
                "scrub_metered_keys": True,
                "subscription_auth_only": True,
            },
        )
    )

    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "DHARMA_FORCE_ANTHROPIC_API" not in env
    assert "OPENAI_API_KEY" not in env
    assert "OPENROUTER_API_KEY" not in env
    assert "KIMI_API_KEY" not in env
    assert "OLLAMA_BASE_URL" not in env
    assert "XAI_API_KEY" not in env
    assert "UNREGISTERED_VENDOR_SECRET" not in env
    assert "DEEPSEEK_API_KEY" not in env
    assert "HELM_ENV_SENTINEL" not in env


def test_build_prompt_and_command_strip_subprocess_nul_bytes() -> None:
    request = CompletionRequest(
        messages=[{"role": "user", "content": "before\x00after"}],
        system_prompt="sys\x00tem",
        model="claude-sonnet-4-5\x00",
    )
    adapter = _adapter()

    prompt = adapter._build_prompt(request)
    command = adapter._build_command(request)

    assert "\x00" not in prompt
    assert "beforeafter" in prompt
    assert all("\x00" not in argument for argument in command)
    assert "system" in command


def test_raw_single_user_prompt_is_exact_in_command_argv() -> None:
    raw_prompt = "  read café/端末.md exactly  \n"
    request = CompletionRequest(
        messages=[{"role": "user", "content": raw_prompt}],
        provider_options={"raw_single_user_prompt": True},
    )

    command = _adapter()._build_command(request)

    prompt_index = command.index("-p") + 1
    assert command[prompt_index].encode("utf-8") == raw_prompt.encode("utf-8")
    assert not command[prompt_index].startswith("User:")


def test_raw_single_user_prompt_rejects_nul_instead_of_rewriting() -> None:
    request = CompletionRequest(
        messages=[{"role": "user", "content": "before\x00after"}],
        provider_options={"raw_single_user_prompt": True},
    )

    with pytest.raises(ValueError, match="NUL"):
        _adapter()._build_command(request)


def test_raw_prompt_option_preserves_normal_serializer_for_other_shapes() -> None:
    request = CompletionRequest(
        messages=[
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
        ],
        provider_options={"raw_single_user_prompt": True},
    )

    assert _adapter()._build_prompt(request) == "User: first\n\nAssistant: second"


@pytest.mark.asyncio
async def test_list_models_and_profile() -> None:
    a = _adapter()
    models = await a.list_models()
    assert len(models) >= 3
    assert any(m.model_id == "claude-sonnet-4-5" for m in models)
    p = a.get_profile("claude-sonnet-4-5")
    assert p.display_name
    assert p.supports(type(p.capabilities).STREAMING)


def test_normalize_simple_success_flow() -> None:
    a = _adapter()
    p = a.get_profile("claude-sonnet-4-5")
    sid = "dgc-test-1"

    lines = [
        _j(
            {
                "type": "system",
                "subtype": "init",
                "session_id": "provider-session-1",
                "model": "claude-sonnet-4-5",
                "tools": ["Read", "Bash"],
                "cwd": "/repo",
                "permissionMode": "default",
                "claude_code_version": "2.1.69",
            }
        ),
        _j(
            {
                "type": "assistant",
                "session_id": "provider-session-1",
                "uuid": "u1",
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            }
        ),
        _j(
            {
                "type": "result",
                "session_id": "provider-session-1",
                "subtype": "success",
                "is_error": False,
                "total_cost_usd": 0.01,
                "duration_ms": 1200,
                "num_turns": 1,
                "model_usage": {"input_tokens": 10, "output_tokens": 20},
            }
        ),
    ]

    out = []
    for line in lines:
        out.extend(a._normalize_line(line, session_id=sid, profile=p))

    assert any(isinstance(e, SessionStart) for e in out)
    assert any(isinstance(e, TextComplete) and e.content == "Hello" for e in out)
    assert any(isinstance(e, UsageReport) and e.total_cost_usd == 0.01 for e in out)
    assert any(isinstance(e, SessionEnd) and e.success for e in out)


def test_normalize_tool_and_stream_deltas() -> None:
    a = _adapter()
    p = a.get_profile("claude-sonnet-4-5")
    sid = "dgc-test-2"

    assistant_tool = _j(
        {
            "type": "assistant",
            "session_id": "provider-session-2",
            "uuid": "u2",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "toolu_123", "name": "Read", "input": {"file_path": "x.py"}}
                ]
            },
        }
    )
    tool_result = _j(
        {
            "type": "user",
            "session_id": "provider-session-2",
            "uuid": "u3",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_123", "content": "ok"}]},
        }
    )
    text_delta = _j(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": "He"},
            },
        }
    )
    think_delta = _j(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "analyzing"},
            },
        }
    )
    arg_delta = _j(
        {
            "type": "stream_event",
            "parent_tool_use_id": "toolu_123",
            "event": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"a":1'},
            },
        }
    )
    progress = _j(
        {"type": "tool_progress", "tool_use_id": "toolu_123", "tool_name": "Read", "elapsed_time_seconds": 1.2}
    )

    out = []
    for line in [assistant_tool, tool_result, text_delta, think_delta, arg_delta, progress]:
        out.extend(a._normalize_line(line, session_id=sid, profile=p))

    assert any(isinstance(e, ToolCallComplete) and e.tool_call_id == "toolu_123" for e in out)
    assert any(isinstance(e, ToolResult) and e.tool_call_id == "toolu_123" for e in out)
    assert any(isinstance(e, TextDelta) and e.content == "He" for e in out)
    assert any(isinstance(e, ThinkingDelta) and "analyzing" in e.content for e in out)
    assert any(isinstance(e, ToolArgumentsDelta) and e.tool_call_id == "toolu_123" for e in out)
    assert any(isinstance(e, ToolProgress) and e.tool_call_id == "toolu_123" for e in out)


def test_normalize_thinking_and_error_flow() -> None:
    a = _adapter()
    p = a.get_profile("claude-sonnet-4-5")
    sid = "dgc-test-3"

    thinking = _j(
        {
            "type": "assistant",
            "session_id": "provider-session-3",
            "uuid": "u4",
            "message": {"content": [{"type": "thinking", "thinking": "deep thought"}]},
        }
    )
    err = _j(
        {
            "type": "result",
            "session_id": "provider-session-3",
            "subtype": "error_max_turns",
            "is_error": True,
            "total_cost_usd": 0.03,
            "duration_ms": 5000,
            "num_turns": 4,
            "errors": ["turn limit reached"],
        }
    )

    out = []
    for line in [thinking, err]:
        out.extend(a._normalize_line(line, session_id=sid, profile=p))

    assert any(isinstance(e, ThinkingComplete) and e.content == "deep thought" for e in out)
    assert any(isinstance(e, ErrorEvent) and e.code == "error_max_turns" for e in out)
    assert any(isinstance(e, SessionEnd) and (not e.success) for e in out)


class _FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]

    async def readline(self) -> bytes:
        if not self._lines:
            await asyncio.sleep(0)
            return b""
        return self._lines.pop(0)


class _RawFakeStdout:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        if not self._lines:
            await asyncio.sleep(0)
            return b""
        return self._lines.pop(0)


class _BrokenStdout:
    async def readline(self) -> bytes:
        raise RuntimeError("Separator is found, but chunk is longer than limit")


class _FakeStderr:
    async def read(self, _: int = -1) -> bytes:
        return b""


class _FakeProc:
    def __init__(self, lines: list[str], exit_code: int = 0) -> None:
        self.stdout = _FakeStdout(lines)
        self.stderr = _FakeStderr()
        self.returncode: int | None = None
        self._exit_code = exit_code

    async def wait(self) -> int:
        if self.returncode is None:
            self.returncode = self._exit_code
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class _BrokenProc(_FakeProc):
    def __init__(self, exit_code: int = 0) -> None:
        super().__init__(lines=[], exit_code=exit_code)
        self.stdout = _BrokenStdout()


@pytest.mark.asyncio
async def test_stream_uses_subprocess_and_yields_events(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _adapter()
    lines = [
        _j(
            {
                "type": "system",
                "subtype": "init",
                "session_id": "provider-session-x",
                "model": "claude-sonnet-4-5",
                "tools": [],
                "cwd": "/repo",
                "permissionMode": "default",
                "claude_code_version": "2.1.69",
            }
        ),
        _j(
            {
                "type": "result",
                "session_id": "provider-session-x",
                "subtype": "success",
                "is_error": False,
                "total_cost_usd": 0.0,
                "duration_ms": 1,
                "num_turns": 1,
            }
        ),
    ]

    async def _fake_spawn(cmd: list[str], env: dict[str, str]) -> _FakeProc:
        assert "claude" in cmd[0]
        return _FakeProc(lines, exit_code=0)

    monkeypatch.setattr(a, "_spawn_process", _fake_spawn)

    req = CompletionRequest(messages=[{"role": "user", "content": "hello"}])
    events = [e async for e in a.stream(req, session_id="dgc-test-stream")]
    assert any(isinstance(e, SessionStart) for e in events)
    assert any(isinstance(e, SessionEnd) for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hostile_line",
    [
        b'{"type":"future_event","tool_calls":[{"name":"shell"}]}\n',
        b'{"type":"assistant","message":{"content":[{"type":"tool_use","type":"text","text":"PONG"}]}}\n',
        b'{"type":"assistant","message":{"content":[{"type":"text","text":"PO\xffNG"}]}}\n',
        b'{"type":"result","subtype":"error_max_turns","total_cost_usd":0,"duration_ms":1,"num_turns":1}\n',
        b'{"type":"assistant","message":{"content":[{"type":"text","text":{"secret":"must-not-escape"}}]}}\n',
        b'{"type":"system","subtype":"init","session_id":{"secret":"must-not-escape"},"model":"claude-sonnet-4-5","tools":[]}\n',
        b'{"type":"stream_event","event":{"type":"content_block_delta","delta":{"type":"text_delta","text":{"secret":"must-not-escape"}}}}\n',
    ],
)
async def test_strict_preview_protocol_rejects_unknown_duplicate_or_invalid_bytes(
    monkeypatch: pytest.MonkeyPatch,
    hostile_line: bytes,
) -> None:
    adapter = _adapter()
    process = _FakeProc([], exit_code=0)
    process.stdout = _RawFakeStdout([hostile_line])

    async def spawn(*args: object, **kwargs: object) -> _FakeProc:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", spawn)
    request = CompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        provider_options={"strict_preview_protocol": True},
    )

    events = [
        event async for event in adapter.stream(request, session_id="strict-preview")
    ]

    assert not any(isinstance(event, SessionStart | TextComplete) for event in events)
    assert any(isinstance(event, ErrorEvent) for event in events)
    terminal = next(event for event in events if isinstance(event, SessionEnd))
    assert terminal.success is False


@pytest.mark.asyncio
async def test_strict_preview_requires_explicit_result_and_marks_exact_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter()
    process = _FakeProc(
        [
            _j(
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": "provider-strict",
                    "model": "claude-sonnet-4-5",
                    "tools": [],
                }
            ),
            _j(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "PONG"}]},
                }
            ),
        ],
        exit_code=0,
    )

    async def spawn(*args: object, **kwargs: object) -> _FakeProc:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", spawn)
    request = CompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="claude-sonnet-4-5",
        provider_options={"strict_preview_protocol": True},
    )

    events = [
        event async for event in adapter.stream(request, session_id="strict-incomplete")
    ]

    start = next(event for event in events if isinstance(event, SessionStart))
    assert start.system_info["served_model"] == "claude-sonnet-4-5"
    assert start.system_info["exact_model_proven"] is True
    assert start.system_info["tool_authority"] == "none"
    assert start.system_info["tools_disabled"] is True
    assert "tool_use" not in start.capabilities
    assert "parallel_tools" not in start.capabilities
    terminal = next(event for event in events if isinstance(event, SessionEnd))
    assert terminal.success is False
    assert terminal.error_code == "incomplete_provider_response"


@pytest.mark.asyncio
async def test_strict_preview_rejects_untyped_cost_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "provider-cost-secret-must-not-escape"
    adapter = _adapter()
    process = _FakeProc(
        [
            _j(
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": "provider-strict-cost",
                    "model": "claude-sonnet-4-5",
                    "tools": [],
                }
            ),
            _j(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "PONG"}]},
                }
            ),
            _j(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "total_cost_usd": secret,
                    "duration_ms": 1,
                    "num_turns": 1,
                }
            ),
        ],
        exit_code=0,
    )

    async def spawn(*args: object, **kwargs: object) -> _FakeProc:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", spawn)
    request = CompletionRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="claude-sonnet-4-5",
        provider_options={"strict_preview_protocol": True},
    )

    events = [
        event async for event in adapter.stream(request, session_id="strict-cost")
    ]

    rendered = repr(events)
    assert secret not in rendered
    assert not any(isinstance(event, UsageReport) for event in events)
    terminal = next(event for event in events if isinstance(event, SessionEnd))
    assert terminal.success is False
    assert terminal.error_code == "malformed_provider_event"


@pytest.mark.asyncio
async def test_cancel_without_active_process_is_safe() -> None:
    a = _adapter()
    await a.cancel()


@pytest.mark.asyncio
async def test_stream_handles_stdout_read_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    a = _adapter()

    async def _fake_spawn(cmd: list[str], env: dict[str, str]) -> _BrokenProc:
        return _BrokenProc(exit_code=0)

    monkeypatch.setattr(a, "_spawn_process", _fake_spawn)

    req = CompletionRequest(messages=[{"role": "user", "content": "hello"}])
    events = [e async for e in a.stream(req, session_id="dgc-test-broken-stdout")]
    assert any(isinstance(e, ErrorEvent) and e.code == "stream_read_error" for e in events)
    terminals = [event for event in events if isinstance(event, SessionEnd)]
    assert len(terminals) == 1
    assert terminals[0].success is False
    assert terminals[0].error_code == "stream_read_error"


@pytest.mark.asyncio
async def test_stream_drains_large_stderr_without_deadlock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter()
    child = (
        "import json, sys; "
        "sys.stderr.write('x' * 300000); sys.stderr.flush(); "
        "print(json.dumps({'type':'result','subtype':'success','is_error':False,"
        "'total_cost_usd':0.0,'duration_ms':1,'num_turns':1}))"
    )

    async def spawn(*args: object, **kwargs: object) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            child,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    monkeypatch.setattr(adapter, "_spawn_process", spawn)

    async def collect() -> list[object]:
        request = CompletionRequest(messages=[{"role": "user", "content": "hello"}])
        return [event async for event in adapter.stream(request, session_id="dgc-stderr")]

    events = await asyncio.wait_for(collect(), timeout=5)
    assert any(isinstance(event, SessionEnd) and event.success for event in events)


@pytest.mark.asyncio
async def test_stream_reaps_child_when_normalization_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter()
    process = _FakeProc(["{}"], exit_code=0)

    async def spawn(*args: object, **kwargs: object) -> _FakeProc:
        return process

    def fail_normalize(*args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("normalization exploded")

    monkeypatch.setattr(adapter, "_spawn_process", spawn)
    monkeypatch.setattr(adapter, "_normalize_line", fail_normalize)
    request = CompletionRequest(messages=[{"role": "user", "content": "hello"}])

    with pytest.raises(RuntimeError, match="normalization exploded"):
        _ = [event async for event in adapter.stream(request, session_id="dgc-reap")]

    assert process.returncode == -15
    assert adapter._proc is None


@pytest.mark.asyncio
async def test_spawn_process_sets_large_stream_reader_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a = ClaudeAdapter(
        config=ProviderConfig(
            provider_id="claude",
            default_model="claude-sonnet-4-5",
            extra={"stream_reader_limit": 1_500_000},
        )
    )
    captured: dict[str, object] = {}

    async def _fake_create(*args: object, **kwargs: object) -> _FakeProc:
        captured.update(kwargs)
        return _FakeProc(lines=[], exit_code=0)

    monkeypatch.setattr(
        "dharma_swarm.tui.engine.adapters.claude.asyncio.create_subprocess_exec",
        _fake_create,
    )

    proc = await a._spawn_process(["claude", "-p", "x"], {})
    assert isinstance(proc, _FakeProc)
    assert captured["limit"] == 1_500_000
