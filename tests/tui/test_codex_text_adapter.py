"""Tests for the sealed subscription-backed Codex text adapter."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from dharma_swarm.tui.engine.adapters.base import CompletionRequest, ProviderConfig
from dharma_swarm.tui.engine.adapters.codex_text import (
    CODEX_TEXT_DISABLED_FEATURES,
    CodexTextAdapter,
    _contains_structural_tool_evidence,
)
from dharma_swarm.tui.engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
)


MODEL = "test-exact-sol-model"


@pytest.mark.parametrize(
    "raw",
    [
        {"message": {"stop_reason": "tool_use"}},
        {"message": {"stopReason": "tool_calls"}},
        {"metadata": {"functionCall": {"name": "shell"}}},
        {"metadata": {"webSearchCall": {"query": "secret"}}},
        {"metadata": {"type": "functionCall"}},
        {"metadata": {"finishReason": "toolCalls"}},
    ],
)
def test_structural_stop_reason_tool_evidence_is_rejected(raw: dict) -> None:
    assert _contains_structural_tool_evidence(raw) is True


def _json_line(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"))


class _FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._chunks = [f"{line}\n".encode() for line in lines]

    async def read(self, size: int = -1) -> bytes:
        await asyncio.sleep(0)
        if not self._chunks:
            return b""
        chunk = self._chunks[0]
        if size < 0 or len(chunk) <= size:
            return self._chunks.pop(0)
        self._chunks[0] = chunk[size:]
        return chunk[:size]


class _RawFakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def read(self, size: int = -1) -> bytes:
        await asyncio.sleep(0)
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class _FakeStderr:
    def __init__(self, value: bytes = b"") -> None:
        self._value = value

    async def read(self, size: int = -1) -> bytes:
        await asyncio.sleep(0)
        value, self._value = self._value, b""
        return value


class _FakeStdin:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.closed = False

    def write(self, value: bytes) -> None:
        self.buffer.extend(value)

    async def drain(self) -> None:
        await asyncio.sleep(0)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        await asyncio.sleep(0)


class _FakeProcess:
    def __init__(
        self,
        lines: list[str],
        *,
        exit_code: int = 0,
        stderr: bytes = b"",
    ) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(lines)
        self.stderr = _FakeStderr(stderr)
        self.returncode: int | None = None
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False

    async def wait(self) -> int:
        await asyncio.sleep(0)
        if self.returncode is None:
            self.returncode = self.exit_code
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class _HangingProcess(_FakeProcess):
    async def wait(self) -> int:
        if not self.killed:
            await asyncio.Event().wait()
        assert self.returncode is not None
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True


def _adapter(tmp_path: Path) -> CodexTextAdapter:
    return CodexTextAdapter(
        ProviderConfig(provider_id="codex_text", default_model=MODEL),
        workdir=tmp_path,
    )


def _request(prompt: str = "PING") -> CompletionRequest:
    return CompletionRequest(
        messages=[{"role": "user", "content": prompt}],
        model=MODEL,
        tools=[],
        tool_choice="none",
    )


def test_command_physically_disables_execution_features(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)

    command = adapter._build_command(_request())

    assert command[:2] == ["codex", "exec"]
    for flag in (
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--json",
    ):
        assert command.count(flag) == 1
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("-m") + 1] == MODEL
    assert command[-1] == "-"
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert "mcp_servers={}" in command
    disabled = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--disable"
    ]
    assert disabled == list(CODEX_TEXT_DISABLED_FEATURES)
    for required in (
        "shell_tool",
        "unified_exec",
        "code_mode_host",
        "apps",
        "browser_use",
        "computer_use",
        "image_generation",
        "goals",
        "multi_agent",
        "plugins",
        "skill_search",
        "memories",
        "hooks",
        "shell_snapshot",
        "workspace_dependencies",
    ):
        assert required in disabled


def test_environment_scrubs_metered_keys_but_keeps_subscription_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "metered-secret")
    monkeypatch.setenv("CODEX_API_KEY", "other-metered-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://metered.invalid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unrelated-provider-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "unrelated-router-secret")
    monkeypatch.setenv("KIMI_API_KEY", "unrelated-kimi-secret")
    monkeypatch.setenv("XAI_API_KEY", "unrelated-xai-secret")
    monkeypatch.setenv("UNREGISTERED_VENDOR_SECRET", "must-not-cross")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-cross")
    monkeypatch.setenv("CODEX_HOME", "/subscription/auth/home")

    environment = _adapter(tmp_path)._build_env()

    assert "OPENAI_API_KEY" not in environment
    assert "CODEX_API_KEY" not in environment
    assert "OPENAI_BASE_URL" not in environment
    assert "ANTHROPIC_API_KEY" not in environment
    assert "OPENROUTER_API_KEY" not in environment
    assert "KIMI_API_KEY" not in environment
    assert "XAI_API_KEY" not in environment
    assert "UNREGISTERED_VENDOR_SECRET" not in environment
    assert "DEEPSEEK_API_KEY" not in environment
    assert environment["CODEX_HOME"] == "/subscription/auth/home"


@pytest.mark.asyncio
async def test_success_buffers_until_no_tool_completion_and_preserves_raw_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    raw_prompt = "  PING\nwith unicode: 無  "
    process = _FakeProcess(
        [
            _json_line({"type": "thread.started", "thread_id": "thread-123"}),
            _json_line({"type": "turn.started"}),
            _json_line(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "PONG"},
                }
            ),
            _json_line(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 11,
                        "cached_input_tokens": 3,
                        "output_tokens": 1,
                    },
                }
            ),
        ]
    )

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [
        event async for event in adapter.stream(_request(raw_prompt), "session-1")
    ]

    assert process.stdin.buffer == raw_prompt.encode("utf-8")
    assert process.stdin.closed is True
    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    start = events[0]
    assert isinstance(start, SessionStart)
    assert start.model == MODEL
    assert start.tools_available == []
    assert start.system_info["served_identity_source"] == "request.model_unverified"
    assert start.system_info["exact_model_proven"] is False
    assert start.system_info["authority"] == "NONE"
    assert isinstance(events[1], TextComplete)
    assert events[1].content == "PONG"
    assert isinstance(events[2], UsageReport)
    assert events[2].cache_read_tokens == 3
    assert isinstance(events[-1], SessionEnd) and events[-1].success is True


@pytest.mark.asyncio
async def test_benign_error_item_is_suppressed_when_turn_completes_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    secret_detail = "feature warning with sensitive local detail"
    process = _FakeProcess(
        [
            _json_line({"type": "turn.started"}),
            _json_line(
                {
                    "type": "item.completed",
                    "item": {"type": "error", "message": secret_detail},
                }
            ),
            _json_line(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "PONG"},
                }
            ),
            _json_line({"type": "turn.completed", "usage": {}}),
        ]
    )

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [event async for event in adapter.stream(_request(), "session-warning")]

    assert [type(event) for event in events] == [
        SessionStart,
        TextComplete,
        UsageReport,
        SessionEnd,
    ]
    assert isinstance(events[1], TextComplete) and events[1].content == "PONG"
    assert secret_detail not in " ".join(str(event) for event in events)


@pytest.mark.asyncio
async def test_error_item_without_clean_completion_still_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    secret_detail = "provider diagnostic must not escape"
    process = _FakeProcess(
        [
            _json_line(
                {
                    "type": "item.completed",
                    "item": {"type": "error", "message": secret_detail},
                }
            )
        ]
    )

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [event async for event in adapter.stream(_request(), "session-diagnostic")]

    assert not any(
        isinstance(event, SessionStart | TextComplete | UsageReport) for event in events
    )
    assert isinstance(events[0], ErrorEvent)
    assert events[0].code == "codex_text_incomplete_response"
    assert isinstance(events[-1], SessionEnd) and events[-1].success is False
    assert secret_detail not in " ".join(str(event) for event in events)


@pytest.mark.asyncio
async def test_tool_event_rejects_buffered_text_before_any_positive_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    process = _FakeProcess(
        [
            _json_line({"type": "thread.started", "thread_id": "thread-hostile"}),
            _json_line(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "PONG"},
                }
            ),
            _json_line(
                {
                    "type": "item.started",
                    "item": {
                        "type": "command_execution",
                        "command": "printenv OPENAI_API_KEY",
                    },
                }
            ),
        ]
    )

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [event async for event in adapter.stream(_request(), "session-hostile")]

    assert process.terminated is True
    assert not any(
        isinstance(event, SessionStart | TextComplete | UsageReport) for event in events
    )
    assert isinstance(events[0], ErrorEvent)
    assert events[0].code == "no_tools_contract_violation"
    assert isinstance(events[-1], SessionEnd)
    assert events[-1].success is False
    assert "OPENAI_API_KEY" not in " ".join(
        str(getattr(event, "message", "")) + str(getattr(event, "error_message", ""))
        for event in events
    )


@pytest.mark.asyncio
async def test_nested_tool_evidence_rejects_safe_looking_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    process = _FakeProcess(
        [
            _json_line(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "PONG",
                        "metadata": {
                            "tool_calls": [{"name": "shell", "arguments": "secret"}]
                        },
                    },
                }
            ),
            _json_line({"type": "turn.completed", "usage": {}}),
        ]
    )

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [event async for event in adapter.stream(_request(), "session-nested-tool")]

    assert process.terminated is True
    assert not any(
        isinstance(event, SessionStart | TextComplete | UsageReport) for event in events
    )
    assert isinstance(events[0], ErrorEvent)
    assert events[0].code == "no_tools_contract_violation"
    assert "secret" not in " ".join(str(event) for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hostile_line",
    [
        b'{"type":"item.completed","item":{"type":"command_execution","type":"agent_message","text":"PONG"}}\n',
        b'{"type":"item.completed","item":{"type":"agent_message","text":"PO\xffNG"}}\n',
    ],
)
async def test_malformed_raw_provider_bytes_never_become_positive_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile_line: bytes,
) -> None:
    adapter = _adapter(tmp_path)
    process = _FakeProcess([])
    process.stdout = _RawFakeStdout(
        [hostile_line, b'{"type":"turn.completed","usage":{}}\n']
    )

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [event async for event in adapter.stream(_request(), "session-raw-hostile")]

    assert not any(
        isinstance(event, SessionStart | TextComplete | UsageReport) for event in events
    )
    assert isinstance(events[0], ErrorEvent)
    assert isinstance(events[-1], SessionEnd) and events[-1].success is False


@pytest.mark.asyncio
@pytest.mark.parametrize("limit_kind", ["line", "cumulative", "assistant"])
async def test_provider_output_limits_fail_before_positive_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit_kind: str,
) -> None:
    adapter = _adapter(tmp_path)
    lines = [
        _json_line(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "PONG!"},
            }
        ),
        _json_line({"type": "turn.completed", "usage": {}}),
    ]
    if limit_kind == "line":
        adapter._MAX_PENDING_EVENT_BYTES = 16
    elif limit_kind == "cumulative":
        adapter._MAX_TOTAL_STDOUT_BYTES = len(lines[0].encode("utf-8")) + 2
    else:
        adapter._MAX_ASSISTANT_BYTES = 4
    process = _FakeProcess(lines)

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [
        event async for event in adapter.stream(_request(), f"session-{limit_kind}")
    ]

    assert process.terminated is True
    assert not any(
        isinstance(event, SessionStart | TextComplete | UsageReport) for event in events
    )
    assert isinstance(events[0], ErrorEvent)
    assert isinstance(events[-1], SessionEnd) and events[-1].success is False


@pytest.mark.asyncio
async def test_wrong_model_fails_before_subprocess_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    spawned = False

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        nonlocal spawned
        spawned = True
        return _FakeProcess([])

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)
    request = _request()
    request.model = "substituted-model"

    events = [event async for event in adapter.stream(request, "session-wrong-model")]

    assert spawned is False
    assert isinstance(events[0], ErrorEvent)
    assert events[0].code == "invalid_text_request"
    assert isinstance(events[-1], SessionEnd) and events[-1].success is False


@pytest.mark.asyncio
async def test_cancel_terminates_then_kills_stubborn_process(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    adapter._CANCEL_GRACE_SECONDS = 0.001
    process = _HangingProcess([])
    adapter._proc = process  # type: ignore[assignment]

    await adapter.cancel()

    assert process.terminated is True
    assert process.killed is True
    assert process.returncode == -9
    assert adapter._proc is None


@pytest.mark.asyncio
async def test_provider_stderr_is_never_forwarded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(tmp_path)
    secret = "sk-never-print-this"
    process = _FakeProcess([], exit_code=1, stderr=secret.encode())

    async def fake_spawn(
        command: list[str], environment: dict[str, str]
    ) -> _FakeProcess:
        return process

    monkeypatch.setattr(adapter, "_spawn_process", fake_spawn)

    events = [event async for event in adapter.stream(_request(), "session-error")]

    rendered = " ".join(
        str(getattr(event, "message", "")) + str(getattr(event, "error_message", ""))
        for event in events
    )
    assert secret not in rendered
    assert isinstance(events[0], ErrorEvent)
    assert isinstance(events[-1], SessionEnd) and events[-1].success is False
