"""WP-0C1 (TIT-005): governance subprocesses get closed stdin and finite timeouts.

Contract under test: ``scripts/uplift_guards/shakti_warrant_guard.py`` and the
``_run_git`` helper in ``scripts/governance/check_shakti_warrant.py``. A child
process that waits on stdin must terminate promptly (closed stdin, not a TTY
inheritance hang); a child that exceeds its wall-clock budget becomes a named
nonzero failure; a passing child still returns its real output and exit code.
"""
from __future__ import annotations

import stat
import subprocess
import textwrap
import time
from pathlib import Path

import pytest

from scripts.governance import check_shakti_warrant
from scripts.uplift_guards import shakti_warrant_guard

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fake_check_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_check_shakti_warrant.py"
    script.write_text(textwrap.dedent(body))
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_child_waiting_on_stdin_terminates_promptly(tmp_path, monkeypatch):
    script = _fake_check_script(
        tmp_path,
        """\
        import sys
        data = sys.stdin.read()  # closed stdin -> immediate EOF, no hang
        print(f"warrant ok with {len(data)} stdin bytes")
        sys.exit(0)
        """,
    )
    monkeypatch.setattr(shakti_warrant_guard, "CHECK_SCRIPT", script)
    started = time.monotonic()
    ok, message = shakti_warrant_guard.check_fourfold_shakti_warrant(REPO_ROOT)
    elapsed = time.monotonic() - started
    assert ok, message
    assert "warrant ok with 0 stdin bytes" in message
    assert elapsed < 30, f"stdin wait took {elapsed:.1f}s — stdin is not closed"


def test_child_timeout_is_named_nonzero_failure(tmp_path, monkeypatch):
    script = _fake_check_script(
        tmp_path,
        """\
        import time
        time.sleep(300)
        """,
    )
    monkeypatch.setattr(shakti_warrant_guard, "CHECK_SCRIPT", script)
    monkeypatch.setenv("DHARMA_UPLIFT_GUARD_TIMEOUT", "1")
    started = time.monotonic()
    ok, message = shakti_warrant_guard.check_fourfold_shakti_warrant(REPO_ROOT)
    elapsed = time.monotonic() - started
    assert not ok
    assert "UPLIFT_GUARD_TIMEOUT" in message
    assert elapsed < 60, f"timeout took {elapsed:.1f}s to fire"


def test_passing_child_returns_real_output(tmp_path, monkeypatch):
    script = _fake_check_script(
        tmp_path,
        """\
        print("WARRANT_OK bounded diff verdict")
        raise SystemExit(0)
        """,
    )
    monkeypatch.setattr(shakti_warrant_guard, "CHECK_SCRIPT", script)
    ok, message = shakti_warrant_guard.check_fourfold_shakti_warrant(REPO_ROOT)
    assert ok
    assert "WARRANT_OK bounded diff verdict" in message


def test_failing_child_returns_output_and_nonzero(tmp_path, monkeypatch):
    script = _fake_check_script(
        tmp_path,
        """\
        import sys
        print("WARRANT_BLOCK evidence missing", file=sys.stderr)
        raise SystemExit(3)
        """,
    )
    monkeypatch.setattr(shakti_warrant_guard, "CHECK_SCRIPT", script)
    ok, message = shakti_warrant_guard.check_fourfold_shakti_warrant(REPO_ROOT)
    assert not ok
    assert "WARRANT_BLOCK evidence missing" in message


def test_invalid_timeout_env_falls_back_without_crash(tmp_path, monkeypatch):
    script = _fake_check_script(tmp_path, "raise SystemExit(0)\n")
    monkeypatch.setattr(shakti_warrant_guard, "CHECK_SCRIPT", script)
    monkeypatch.setenv("DHARMA_UPLIFT_GUARD_TIMEOUT", "not-a-number")
    ok, _message = shakti_warrant_guard.check_fourfold_shakti_warrant(REPO_ROOT)
    assert ok


def test_warrant_subprocess_carries_closed_stdin_and_timeout(monkeypatch):
    captured: dict = {}
    real_run = subprocess.run

    def recording_run(*args, **kwargs):
        captured.update(kwargs)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(shakti_warrant_guard.subprocess, "run", recording_run)
    shakti_warrant_guard.check_fourfold_shakti_warrant(REPO_ROOT)
    assert captured.get("stdin") == subprocess.DEVNULL
    assert isinstance(captured.get("timeout"), (int, float))
    assert captured["timeout"] > 0


def test_run_git_carries_closed_stdin_and_timeout(monkeypatch):
    captured: dict = {}
    real_run = subprocess.run

    def recording_run(*args, **kwargs):
        captured.update(kwargs)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(check_shakti_warrant.subprocess, "run", recording_run)
    out = check_shakti_warrant._run_git(REPO_ROOT, ["rev-parse", "--git-dir"])
    assert out.strip()
    assert captured.get("stdin") == subprocess.DEVNULL
    assert isinstance(captured.get("timeout"), (int, float))
    assert captured["timeout"] > 0


def test_run_git_timeout_is_named_failure(monkeypatch):
    def timing_out_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(check_shakti_warrant.subprocess, "run", timing_out_run)
    with pytest.raises(SystemExit) as excinfo:
        check_shakti_warrant._run_git(REPO_ROOT, ["status", "--porcelain"])
    assert "GIT_TIMEOUT" in str(excinfo.value)
