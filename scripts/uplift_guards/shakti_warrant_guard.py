"""Fourfold Shakti Warrant guard for staged pre-commit diffs."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CHECK_SCRIPT = Path(__file__).resolve().parents[1] / "governance/check_shakti_warrant.py"
_REPO_ROOT = Path(__file__).resolve().parents[2]
ACK_TAG = "[impact-checked]"
ACK_ENV = "DHARMA_UPLIFT_ACK"
ACK_ENV_VALUE = "impact-checked"
# WP-0C1 (TIT-005): the warrant subprocess must never inherit an open stdin
# (a non-TTY pipe blocks it forever) and must carry a finite wall clock.
TIMEOUT_ENV = "DHARMA_UPLIFT_GUARD_TIMEOUT"
DEFAULT_TIMEOUT_SECONDS = 300.0


def _guard_timeout() -> float:
    raw = os.environ.get(TIMEOUT_ENV, "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_TIMEOUT_SECONDS


def _python_executable() -> str:
    """Return the venv Python if available, else fall back to sys.executable."""
    venv_python = _REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    return sys.executable


def _read_commit_message(repo_root: Path, msg_file: str | None) -> str:
    if msg_file:
        return Path(msg_file).read_text(errors="replace")
    candidate = repo_root / ".git" / "COMMIT_EDITMSG"
    if candidate.exists():
        return candidate.read_text(errors="replace")
    return ""


def _impact_acknowledged(repo_root: Path, msg_file: str | None = None) -> bool:
    if ACK_TAG in _read_commit_message(repo_root, msg_file):
        return True
    return os.environ.get(ACK_ENV, "").strip().lower() == ACK_ENV_VALUE.lower()


def _summarize_warrant_output(output: str) -> str:
    lines = output.splitlines()
    first_line = lines[0] if lines else "no warrant output"
    for index, line in enumerate(lines):
        if line.strip() == "Warnings:" and index + 1 < len(lines):
            return f"{first_line} | warning: {lines[index + 1].removeprefix('- ').strip()}"
    return first_line


def _command(repo_root: Path, *, impact_checked: bool) -> list[str]:
    cmd = [
        _python_executable(),
        str(CHECK_SCRIPT),
        "--intent",
        (
            "pre-commit staged diff fourfold governance warrant for system telos, "
            "semantic architecture, bounded change, deterministic evidence, "
            "exact paths, and verification"
        ),
        "--diff-scope",
        "staged",
        "--no-include-untracked",
        "--pass-on-empty-diff",
        "--max-diff-chars",
        "12000",
        "--tool",
        "pytest",
        "--metadata",
        "allowed_tools=pytest",
        "--metadata",
        "requires_diff_evidence=true",
        "--metadata",
        "enforce_hotpath_ack=true",
        "--fail-on",
        "block",
        "--fail-on",
        "hold",
    ]
    if impact_checked:
        cmd.extend(["--metadata", "impact_checked=true"])
    return cmd


def check_fourfold_shakti_warrant(
    repo_root: Path | None = None,
    *,
    commit_msg_file: str | None = None,
) -> tuple[bool, str]:
    """Run an evidence-bound Fourfold Shakti Warrant against staged changes."""
    repo_root = repo_root or Path.cwd()
    if os.environ.get("DHARMA_SKIP_SHAKTI_WARRANT_GUARD", "").strip() == "1":
        return True, "shakti warrant guard skipped by DHARMA_SKIP_SHAKTI_WARRANT_GUARD=1"

    timeout_seconds = _guard_timeout()
    try:
        proc = subprocess.run(
            _command(
                repo_root,
                impact_checked=_impact_acknowledged(repo_root, commit_msg_file),
            ),
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"UPLIFT_GUARD_TIMEOUT: fourfold shakti warrant exceeded "
            f"{timeout_seconds:g}s wall clock (named nonzero failure; raise "
            f"{TIMEOUT_ENV} only with cause)"
        )
    output = "\n".join(part.strip() for part in [proc.stdout, proc.stderr] if part.strip())
    if proc.returncode == 0:
        return True, _summarize_warrant_output(output)
    return False, output or f"shakti warrant exited {proc.returncode}"
