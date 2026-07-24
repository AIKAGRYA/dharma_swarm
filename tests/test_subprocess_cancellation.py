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
    return all(
        callable(getattr(os, name, None)) for name in ("getpgid", "killpg")
    ) and getattr(signal, "SIGKILL", None) is not None


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


class _FallbackProcess:
    pid = 123456
    returncode = None

    def __init__(self) -> None:
        self.killed = False

    def kill(self) -> None:
        self.killed = True


def test_kill_process_group_falls_back_without_posix_apis(monkeypatch):
    proc = _FallbackProcess()
    monkeypatch.delattr(os, "getpgid", raising=False)
    monkeypatch.delattr(os, "killpg", raising=False)

    kill_process_group(proc)  # type: ignore[arg-type]

    assert proc.killed is True


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
    diff = (
        "--- a/hello.py\n"
        "+++ b/hello.py\n"
        "@@ -1,3 +1,3 @@\n"
        " # header\n"
        "-old_value = 1\n"
        "+new_value = 2\n"
        " # footer\n"
    )
    applier = DiffApplier(workspace=tmp_path)

    task = asyncio.create_task(
        applier.apply_and_test(
            diff,
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
