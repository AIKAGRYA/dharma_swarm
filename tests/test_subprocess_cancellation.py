"""Regression tests for bounded subprocess cleanup after Titanium WP-0D."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import sys
import time
from pathlib import Path

import pytest

from dharma_swarm.diff_applier import DiffApplier
from dharma_swarm.sandbox import LocalSandbox, kill_process_group


def _process_groups_supported() -> bool:
    return callable(getattr(os, "killpg", None)) and getattr(
        signal, "SIGKILL", None
    ) is not None


async def _wait_for_path(path: Path, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            pytest.fail(f"timed out waiting for marker: {path}")
        await asyncio.sleep(0.02)


def _delayed_marker_command(started: Path, survived: Path) -> str:
    code = (
        "from pathlib import Path; import time; "
        f"Path({str(started)!r}).write_text('started', encoding='utf-8'); "
        "time.sleep(2); "
        f"Path({str(survived)!r}).write_text('survived', encoding='utf-8')"
    )
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def _exited_parent_with_delayed_child(survived: Path) -> str:
    child = (
        "from pathlib import Path; import time; "
        "time.sleep(2); "
        f"Path({str(survived)!r}).write_text('survived', encoding='utf-8')"
    )
    parent = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}])"
    )
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(parent)}"


class _FallbackProcess:
    pid = 123456
    returncode = None

    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        self.killed = True


def test_kill_process_group_falls_back_without_posix_apis(monkeypatch):
    proc = _FallbackProcess()
    monkeypatch.delattr(os, "killpg", raising=False)

    kill_process_group(proc)  # type: ignore[arg-type]

    assert proc.killed is True


def test_kill_process_group_signals_group_after_shell_exit(monkeypatch):
    proc = _FallbackProcess()
    proc.returncode = 0
    calls: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))

    kill_process_group(proc)  # type: ignore[arg-type]

    assert calls == [(proc.pid, signal.SIGKILL)]
    assert proc.killed is False


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _process_groups_supported(),
    reason="process-group cancellation proof requires POSIX group APIs",
)
async def test_timeout_kills_descendant_after_session_leader_exits(tmp_path: Path):
    survived = tmp_path / "exited-parent-survived"
    sandbox = LocalSandbox(workdir=tmp_path)
    started_at = time.monotonic()

    try:
        result = await sandbox.execute(
            _exited_parent_with_delayed_child(survived), timeout=0.3
        )
        elapsed = time.monotonic() - started_at
        assert result.timed_out is True
        assert elapsed < 1.5
        await asyncio.sleep(2.2)
        assert not survived.exists(), "descendant survived its exited session leader"
    finally:
        await sandbox.cleanup()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _process_groups_supported(),
    reason="process-group cancellation proof requires POSIX group APIs",
)
async def test_local_sandbox_cancellation_kills_delayed_child(tmp_path: Path):
    started = tmp_path / "sandbox-started"
    survived = tmp_path / "sandbox-survived"
    sandbox = LocalSandbox(workdir=tmp_path)

    task = asyncio.create_task(
        sandbox.execute(_delayed_marker_command(started, survived), timeout=30)
    )
    try:
        await _wait_for_path(started)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(2.2)
        assert not survived.exists(), "cancelled sandbox child continued running"
    finally:
        if not task.done():
            task.cancel()
        await sandbox.cleanup()


def _existing_file_diff() -> str:
    return (
        "--- a/hello.py\n"
        "+++ b/hello.py\n"
        "@@ -1,3 +1,3 @@\n"
        " # header\n"
        "-old_value = 1\n"
        "+new_value = 2\n"
        " # footer\n"
    )


def _new_file_diff() -> str:
    return (
        "--- /dev/null\n"
        "+++ b/brand_new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+created = True\n"
        "+print(created)\n"
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _process_groups_supported(),
    reason="process-group cancellation proof requires POSIX group APIs",
)
async def test_diff_applier_cancellation_kills_child_and_rolls_back(
    tmp_path: Path,
):
    target = tmp_path / "hello.py"
    original = "# header\nold_value = 1\n# footer\n"
    target.write_text(original, encoding="utf-8")
    started = tmp_path / "diff-started"
    survived = tmp_path / "diff-survived"
    applier = DiffApplier(workspace=tmp_path)

    task = asyncio.create_task(
        applier.apply_and_test(
            _existing_file_diff(),
            test_command=_delayed_marker_command(started, survived),
            timeout=30,
        )
    )
    await _wait_for_path(started)
    assert "new_value = 2" in target.read_text(encoding="utf-8")

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert target.read_text(encoding="utf-8") == original
    assert not target.with_suffix(".py.bak").exists()
    await asyncio.sleep(2.2)
    assert not survived.exists(), "cancelled test command continued running"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _process_groups_supported(),
    reason="process-group cancellation proof requires POSIX group APIs",
)
async def test_diff_applier_cancellation_removes_new_file(tmp_path: Path):
    target = tmp_path / "brand_new.py"
    started = tmp_path / "new-file-started"
    survived = tmp_path / "new-file-survived"
    applier = DiffApplier(workspace=tmp_path)

    task = asyncio.create_task(
        applier.apply_and_test(
            _new_file_diff(),
            test_command=_delayed_marker_command(started, survived),
            timeout=30,
        )
    )
    await _wait_for_path(started)
    assert target.exists()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert not target.exists(), "cancellation left a newly created file behind"
    await asyncio.sleep(2.2)
    assert not survived.exists(), "cancelled test command continued running"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _process_groups_supported(),
    reason="process-group cancellation proof requires POSIX group APIs",
)
async def test_repeated_cancellation_cannot_interrupt_rollback(
    tmp_path: Path, monkeypatch
):
    target = tmp_path / "hello.py"
    original = "# header\nold_value = 1\n# footer\n"
    target.write_text(original, encoding="utf-8")
    started = tmp_path / "repeat-started"
    survived = tmp_path / "repeat-survived"
    rollback_started = asyncio.Event()
    applier = DiffApplier(workspace=tmp_path)
    original_rollback = applier.rollback

    async def delayed_rollback(result):
        rollback_started.set()
        await asyncio.sleep(0.25)
        await original_rollback(result)

    monkeypatch.setattr(applier, "rollback", delayed_rollback)
    task = asyncio.create_task(
        applier.apply_and_test(
            _existing_file_diff(),
            test_command=_delayed_marker_command(started, survived),
            timeout=30,
        )
    )
    await _wait_for_path(started)
    task.cancel()
    await asyncio.wait_for(rollback_started.wait(), timeout=3)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert target.read_text(encoding="utf-8") == original
    assert not target.with_suffix(".py.bak").exists()
    await asyncio.sleep(2.2)
    assert not survived.exists(), "repeated cancellation left child work running"
