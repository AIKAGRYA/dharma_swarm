"""Fourfold Shakti Warrant guard for staged pre-commit diffs."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .hotpath_guard import impact_acknowledged

CHECK_SCRIPT = Path(__file__).resolve().parents[1] / "governance/check_shakti_warrant.py"


def _summarize_warrant_output(output: str) -> str:
    lines = output.splitlines()
    first_line = lines[0] if lines else "no warrant output"
    for index, line in enumerate(lines):
        if line.strip() == "Warnings:" and index + 1 < len(lines):
            return f"{first_line} | warning: {lines[index + 1].removeprefix('- ').strip()}"
    return first_line


def _command(repo_root: Path, *, impact_checked: bool) -> list[str]:
    cmd = [
        sys.executable,
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

    proc = subprocess.run(
        _command(
            repo_root,
            impact_checked=impact_acknowledged(repo_root, commit_msg_file),
        ),
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part.strip() for part in [proc.stdout, proc.stderr] if part.strip())
    if proc.returncode == 0:
        return True, _summarize_warrant_output(output)
    return False, output or f"shakti warrant exited {proc.returncode}"
