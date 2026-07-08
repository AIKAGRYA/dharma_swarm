"""Scorer sandbox hardening — the gym's security boundary for untrusted diffs.

The G1 scorer applies an attacker-shaped candidate diff to a base tree and
runs the landed tests against it. The diff controls everything in the tree
except the overlaid test bodies, so without guards it can (verified in the
2026-07-07 chamber review): drop a root ``conftest.py`` /
``sitecustomize.py`` / pytest config that forces every test green without
fixing the bug; escape the sandbox via ``../`` paths or symlinks; or
exfiltrate credentials from the inherited environment.

This module is the pre-execution guard: reject dangerous diffs, hand the
scorer a scrubbed minimal environment, and re-check the tree for symlinks
after apply.

NOT a full jail. Process/network/filesystem isolation (seccomp-class caps)
is the sandbox-jail component the substrate ruling (doctrine §3.6) names as
the FIRST earned Rust carve-out, and it MUST land before the live untrusted
solver lane opens (track next-item). These Python guards raise the cost of
the cheap, high-value attacks; they do not contain arbitrary native code.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Files a candidate diff must never create/modify: they change the test
# EXECUTION ENVIRONMENT rather than the code under test, which is how a diff
# scores a pass without fixing anything.
_FORBIDDEN_BASENAMES = frozenset({
    "conftest.py", "sitecustomize.py", "usercustomize.py",
    "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml",
})
_FORBIDDEN_SUFFIXES = (".pth",)
# Env vars carrying secrets — never inherited by the scorer subprocess.
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CRED",
                   "ANTHROPIC", "OPENAI", "AWS", "AZURE", "GCP", "GITHUB",
                   "GH_", "DHARMA", "SLACK", "HF_", "COHERE", "MISTRAL")
_ENV_ALLOWLIST = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR",
                  "PYTHONHASHSEED", "SYSTEMROOT")


class DiffPolicyError(RuntimeError):
    """A candidate diff violated the sandbox diff policy (rejected pre-apply)."""


def _diff_target_paths(diff: str) -> list[str]:
    """Every path a unified diff would create/modify/rename-to."""
    paths: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            if p == "/dev/null":
                continue
            if p.startswith(("a/", "b/")):
                p = p[2:]
            paths.append(p)
        elif line.startswith(("rename to ", "copy to ")):
            paths.append(line.split(" to ", 1)[1].strip())
    return paths


def diff_policy_reason(diff: str) -> str | None:
    """Return a rejection reason if the diff is unsafe, else None.

    Kills the scorer-gaming class (config/hook files), the traversal escape
    (absolute / ``..`` paths), and the symlink-redirect vector (git's
    ``120000`` mode)."""
    if re.search(r"^new file mode 120000|^new mode 120000|^old mode 120000",
                 diff, re.MULTILINE):
        return "diff creates or converts to a symlink (mode 120000) — rejected"
    for p in _diff_target_paths(diff):
        norm = p.replace("\\", "/").strip()
        parts = Path(norm).parts
        if norm.startswith("/") or ".." in parts:
            return f"diff targets an out-of-tree path {p!r} — rejected"
        base = parts[-1] if parts else norm
        if base in _FORBIDDEN_BASENAMES or base.endswith(_FORBIDDEN_SUFFIXES):
            return (f"diff touches test-execution-environment file {p!r} — "
                    "rejected (scorer-gaming vector)")
    return None


def scrubbed_env(sandbox: Path) -> dict[str, str]:
    """Minimal environment for scorer subprocesses: no secrets, HOME
    redirected away from the real ~/.dharma, no repo discovery above the
    sandbox. Blocks the cheap credential-exfil and state-clobber paths."""
    base = os.environ
    env = {k: base[k] for k in _ENV_ALLOWLIST if k in base}
    for k, v in base.items():
        ku = k.upper()
        if k in env or any(m in ku for m in _SECRET_MARKERS):
            continue
    env["HOME"] = str(sandbox)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_CEILING_DIRECTORIES"] = str(sandbox.parent)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def find_symlinks(root: Path) -> list[Path]:
    """Every symlink in the tree (empty list == none)."""
    return [p for p in root.rglob("*") if p.is_symlink()]


def assert_within(root: Path, target: Path) -> None:
    """target must resolve inside root (no symlink/`..` redirect out)."""
    root_r = root.resolve()
    try:
        target.resolve().relative_to(root_r)
    except ValueError:
        raise DiffPolicyError(
            f"overlay target {target} escapes the sandbox {root} — VOID")


__all__ = [
    "DiffPolicyError",
    "assert_within",
    "diff_policy_reason",
    "find_symlinks",
    "scrubbed_env",
]
