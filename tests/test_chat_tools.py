from __future__ import annotations

import pytest

from api import chat_tool_execution as execution_module
from api.chat_tools import (
    SecurityVulnerabilityException,
    exec_grep,
    exec_shell,
    exec_stigmergy_query,
)
from dharma_swarm.models import GateCheckResult, GateDecision, SandboxResult
from dharma_swarm.stigmergy import StigmergicMark


class _FakeShellBackend:
    name = "fake"

    def __init__(
        self,
        result: SandboxResult | None = None,
        exc: Exception | None = None,
    ) -> None:
        self.result = result or SandboxResult(exit_code=0, stdout="ok")
        self.exc = exc
        self.calls: list[tuple[str, float]] = []

    async def execute(self, command: str, timeout: float) -> SandboxResult:
        self.calls.append((command, timeout))
        if self.exc is not None:
            raise self.exc
        return self.result


def _redirect_shell_quarantine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        execution_module,
        "dharma_state_dir",
        lambda *_args, **_kwargs: tmp_path,
    )


async def _allow_shell_gate(_command: str) -> GateCheckResult:
    return GateCheckResult(decision=GateDecision.ALLOW, reason="ok")


@pytest.mark.asyncio
async def test_exec_stigmergy_query_awaits_async_store_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStore:
        def density(self) -> int:
            return 1

        async def read_marks(self, *, limit: int = 20, **_kwargs):
            return [
                StigmergicMark(
                    agent="tester",
                    file_path="core.py",
                    action="observe",
                    observation=f"recent-{limit}",
                    salience=0.8,
                )
            ]

        async def hot_paths(self, **_kwargs):
            return [("core.py", 4), ("other.py", 2)]

        async def high_salience(self, *, limit: int = 20, **_kwargs):
            return [
                StigmergicMark(
                    agent="tester",
                    file_path=f"high-{limit}.py",
                    action="observe",
                    observation="important",
                    salience=0.95,
                )
            ]

    monkeypatch.setattr("dharma_swarm.stigmergy.StigmergyStore", FakeStore)

    recent = await exec_stigmergy_query({"action": "recent", "limit": 3})
    assert "core.py" in recent
    assert "recent-3" in recent

    hot_paths = await exec_stigmergy_query({"action": "hot_paths", "limit": 1})
    assert "core.py" in hot_paths
    assert "other.py" not in hot_paths

    high = await exec_stigmergy_query({"action": "high_salience", "limit": 2})
    assert "high-2.py" in high


@pytest.mark.asyncio
async def test_exec_shell_requires_explicit_gate_allow_and_uses_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    backend = _FakeShellBackend(
        SandboxResult(exit_code=0, stdout="hello", stderr="warn")
    )
    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", _allow_shell_gate)
    monkeypatch.setattr(execution_module, "_shell_backend_from_env", lambda: backend)

    result = await exec_shell({"command": "echo hello", "timeout": 5})

    assert backend.calls == [("echo hello", 5.0)]
    assert "exit_code: 0" in result
    assert "stdout:\nhello" in result
    assert "stderr:\nwarn" in result


@pytest.mark.asyncio
async def test_exec_shell_gate_exception_fails_closed_before_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    backend = _FakeShellBackend()

    async def broken_gate(_command: str) -> GateCheckResult:
        raise RuntimeError("gate unavailable")

    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", broken_gate)
    monkeypatch.setattr(execution_module, "_shell_backend_from_env", lambda: backend)

    with pytest.raises(SecurityVulnerabilityException):
        await exec_shell({"command": "echo should-not-run"})

    assert backend.calls == []
    assert list((tmp_path / "quarantine" / "shell_exec").glob("*.json"))


@pytest.mark.asyncio
async def test_exec_shell_review_fails_closed_before_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    backend = _FakeShellBackend()

    async def review_gate(_command: str) -> GateCheckResult:
        return GateCheckResult(decision=GateDecision.REVIEW, reason="needs review")

    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", review_gate)
    monkeypatch.setattr(execution_module, "_shell_backend_from_env", lambda: backend)

    with pytest.raises(SecurityVulnerabilityException):
        await exec_shell({"command": "echo should-not-run"})

    assert backend.calls == []


@pytest.mark.asyncio
async def test_exec_shell_malformed_gate_fails_closed_before_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    backend = _FakeShellBackend()

    async def malformed_gate(_command: str) -> dict[str, str]:
        return {"decision": "allow"}

    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", malformed_gate)
    monkeypatch.setattr(execution_module, "_shell_backend_from_env", lambda: backend)

    with pytest.raises(SecurityVulnerabilityException):
        await exec_shell({"command": "echo should-not-run"})

    assert backend.calls == []


@pytest.mark.asyncio
async def test_exec_shell_dangerous_pattern_fails_closed_after_allow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    backend = _FakeShellBackend()
    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", _allow_shell_gate)
    monkeypatch.setattr(execution_module, "_shell_backend_from_env", lambda: backend)

    with pytest.raises(SecurityVulnerabilityException):
        await exec_shell({"command": "sudo true"})

    assert backend.calls == []


@pytest.mark.asyncio
async def test_exec_shell_backend_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    backend = _FakeShellBackend(exc=RuntimeError("container unavailable"))
    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", _allow_shell_gate)
    monkeypatch.setattr(execution_module, "_shell_backend_from_env", lambda: backend)

    with pytest.raises(SecurityVulnerabilityException):
        await exec_shell({"command": "echo should-not-run"})

    assert backend.calls == [("echo should-not-run", 30.0)]


@pytest.mark.asyncio
async def test_exec_shell_host_backend_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _redirect_shell_quarantine(monkeypatch, tmp_path)
    monkeypatch.setattr(execution_module, "_evaluate_shell_gate", _allow_shell_gate)
    monkeypatch.setenv("DHARMA_SHELL_EXEC_BACKEND", "host")
    monkeypatch.delenv("DHARMA_ALLOW_HOST_SHELL_EXEC", raising=False)

    with pytest.raises(SecurityVulnerabilityException):
        await exec_shell({"command": "echo should-not-run"})


@pytest.mark.asyncio
async def test_exec_grep_searches_in_process_within_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(execution_module, "ALLOWED_ROOTS", [tmp_path])
    source = tmp_path / "sample.py"
    source.write_text("alpha\nneedle here\n", encoding="utf-8")
    ignored = tmp_path / "sample.txt"
    ignored.write_text("needle outside glob\n", encoding="utf-8")

    result = await exec_grep({
        "pattern": "needle",
        "path": str(tmp_path),
        "glob": "*.py",
        "max_results": 5,
    })

    assert f"{source}:2:needle here" in result
    assert "sample.txt" not in result
