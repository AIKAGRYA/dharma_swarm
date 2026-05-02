"""Detect cross-module private method access.

Catches the pattern where swarm.py calls orchestrator._classify_failure()
directly — a structural contract violation that breaks silently on refactor.

Allowlist known violations until they're refactored. New violations fail the test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent / "dharma_swarm"

# Known violations that exist today — refactor these, then remove from allowlist
ALLOWLIST = {
    ("swarm.py", "orchestrator", "_classify_failure"),
    ("swarm.py", "orchestrator", "_resolve_retry_policy"),
    ("swarm.py", "orchestrator", "_apply_failure_retry_defaults"),
    ("swarm.py", "task_board", "_open"),
    ("dharma_context_mcp.py", "idx", "_get_conn"),
    ("artifact_store.py", "engine", "_artifact_path"),
}

# Pattern: self._something._private_method(
CROSS_PRIVATE_RE = re.compile(
    r"self\._([\w]+)\.(_[a-z]\w+)\s*\("
)


def _scan_file(path: Path) -> list[tuple[str, str, str]]:
    """Return (file, target_attr, private_method) for cross-module private calls."""
    violations = []
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    for match in CROSS_PRIVATE_RE.finditer(text):
        target = match.group(1)  # e.g. "orchestrator"
        method = match.group(2)  # e.g. "_classify_failure"
        if method.startswith("__"):
            continue  # dunder methods are fine
        violations.append((path.name, target, method))
    return violations


def test_no_new_cross_module_private_access():
    """No NEW cross-module private method calls beyond the allowlist."""
    all_violations = []
    for py_file in REPO_ROOT.glob("*.py"):
        all_violations.extend(_scan_file(py_file))

    new_violations = [v for v in all_violations if v not in ALLOWLIST]
    if new_violations:
        msg = "New cross-module private method access detected:\n"
        for fname, target, method in new_violations:
            msg += f"  {fname}: self._{target}.{method}()\n"
        msg += "\nEither refactor to use a public API or add to ALLOWLIST with justification."
        pytest.fail(msg)


def test_allowlist_not_stale():
    """Verify allowlisted violations still exist (remove when refactored)."""
    all_violations = set()
    for py_file in REPO_ROOT.glob("*.py"):
        all_violations.update(_scan_file(py_file))

    stale = ALLOWLIST - all_violations
    if stale:
        msg = "Allowlisted violations no longer exist (remove from ALLOWLIST):\n"
        for fname, target, method in stale:
            msg += f"  {fname}: self._{target}.{method}()\n"
        pytest.fail(msg)
