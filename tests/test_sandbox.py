"""Tests for dharma_swarm.sandbox."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from dharma_swarm.sandbox import (
    IsolationUnavailableError,
    LocalSandbox,
    SandboxError,
    SandboxManager,
)


@pytest.mark.asyncio
async def test_execute_echo():
    sb = LocalSandbox()
    result = await sb.execute("echo hello")
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.duration_seconds > 0
    await sb.cleanup()


@pytest.mark.asyncio
async def test_execute_python():
    sb = LocalSandbox()
    result = await sb.execute_python("print(2 + 2)")
    assert result.exit_code == 0
    assert "4" in result.stdout
    await sb.cleanup()


@pytest.mark.asyncio
async def test_execute_timeout():
    sb = LocalSandbox()
    started = time.monotonic()
    result = await sb.execute("sleep 10", timeout=0.5)
    elapsed = time.monotonic() - started
    assert result.timed_out
    # A lone proc.kill() only signals the shell; without killing the whole
    # process group a non-exec'd grandchild survives it, keeps the piped
    # stdout/stderr open, and execute() silently blocks for the full 10s
    # instead of honoring `timeout` -- result.timed_out alone doesn't catch
    # that, only wall-clock does.
    assert elapsed < 5, f"execute() took {elapsed:.1f}s, timeout=0.5 was not enforced"
    await sb.cleanup()


@pytest.mark.asyncio
async def test_execute_timeout_kills_non_exec_grandchild():
    """dash doesn't always exec-replace a single command, so a plain
    proc.kill() can leave the real work alive under a dead shell PID."""
    sb = LocalSandbox()
    started = time.monotonic()
    result = await sb.execute('python3 -c "import time; time.sleep(10)"', timeout=0.5)
    elapsed = time.monotonic() - started
    assert result.timed_out
    assert elapsed < 5, f"execute() took {elapsed:.1f}s, timeout=0.5 was not enforced"
    await sb.cleanup()


@pytest.mark.asyncio
async def test_execute_failure():
    sb = LocalSandbox()
    result = await sb.execute("exit 1")
    assert result.exit_code == 1
    await sb.cleanup()


def test_safety_rm_rf():
    with pytest.raises(SandboxError):
        LocalSandbox._check_safety("rm -rf /")


def test_safety_fork_bomb():
    with pytest.raises(SandboxError):
        LocalSandbox._check_safety(":(){ :|:& };:")


def test_safety_safe_command():
    # Should not raise
    LocalSandbox._check_safety("echo hello")
    LocalSandbox._check_safety("ls -la")
    LocalSandbox._check_safety("python3 script.py")


@pytest.mark.asyncio
async def test_sandbox_manager():
    mgr = SandboxManager()
    sb = mgr.create()
    assert mgr.active_count == 1
    result = await sb.execute("echo test")
    assert result.exit_code == 0
    await mgr.shutdown_all()
    assert mgr.active_count == 0


def test_sandbox_manager_invalid_type():
    mgr = SandboxManager()
    with pytest.raises(SandboxError, match="Unknown sandbox type"):
        mgr.create(sandbox_type="nonexistent")


def test_sandbox_manager_docker_sync_raises():
    """Docker sandbox requires async creation via create_async()."""
    mgr = SandboxManager()
    with pytest.raises(SandboxError, match="async creation"):
        mgr.create(sandbox_type="docker")


@pytest.mark.asyncio
async def test_explicit_docker_request_never_falls_back_to_host():
    mgr = SandboxManager()
    with patch.object(mgr, "_check_docker", AsyncMock(return_value=False)):
        with pytest.raises(IsolationUnavailableError, match="explicitly requested"):
            await mgr.create_async(sandbox_type="docker")
    assert mgr.active_count == 0


@pytest.mark.asyncio
async def test_required_auto_isolation_never_falls_back_to_host():
    mgr = SandboxManager(prefer_docker=True)
    with patch.object(mgr, "_check_docker", AsyncMock(return_value=False)):
        with pytest.raises(IsolationUnavailableError, match="refusing LocalSandbox"):
            await mgr.create_async(sandbox_type="auto", require_isolation=True)
    assert mgr.active_count == 0


@pytest.mark.asyncio
async def test_async_unknown_sandbox_type_fails_closed():
    mgr = SandboxManager()
    with pytest.raises(SandboxError, match="Unknown sandbox type"):
        await mgr.create_async(sandbox_type="invented")
