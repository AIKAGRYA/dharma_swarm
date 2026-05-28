#!/usr/bin/env python3
"""Anti-accretion CI gate for the Runtime Truth Spine. Exit 0/1."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DHARMA_PKG = _REPO_ROOT / "dharma_swarm"

_SPINE_DECL_RE = re.compile(r"^#\s*spine:\s*\S+", re.MULTILINE)

_SQLITE_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?:sqlite3|aiosqlite)|from\s+(?:sqlite3|aiosqlite)\s+import)",
    re.MULTILINE,
)


def _check_sqlite_declarations() -> list[str]:
    """Check all .py files under dharma_swarm/ that import sqlite3/aiosqlite."""
    failures: list[str] = []

    for root, _dirs, files in os.walk(_DHARMA_PKG):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = Path(root) / fname
            rel = fpath.relative_to(_REPO_ROOT)

            try:
                content = fpath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if not _SQLITE_IMPORT_RE.search(content):
                continue

            # File imports sqlite — check for spine declaration
            if _SPINE_DECL_RE.search(content):
                continue

            # Exempt: files that existed before the spine (grandfathered).
            # The spine_check only enforces declarations on NEW files.
            # We use git to determine if the file is new in this branch.
            # For CI simplicity, we exempt all files present on the merge base.
            # This is implemented via a marker list that PRs B+ will shrink.
            if _is_grandfathered(rel):
                continue

            failures.append(
                f"FAIL: {rel} imports sqlite3/aiosqlite but has no "
                f"'# spine: ...' declaration. Add one of:\n"
                f"  # spine: writes EvidenceReceipt\n"
                f"  # spine: reads EvidenceReceipt\n"
                f"  # spine: derived view\n"
                f"  # spine: plugin sink\n"
                f"  # spine: denormalized cache\n"
                f"  # spine: migration compatibility mirror\n"
                f"  # spine: exempt — <reason>"
            )

    return failures


def _is_grandfathered(rel: Path) -> bool:
    """Files that existed before the spine are grandfathered.

    PR A grandfathers ALL existing files. Future PRs will shrink this list
    as each module declares its relation to EvidenceReceipt.
    """
    # All files under dharma_swarm/spine/ must declare (they're new).
    if str(rel).startswith("dharma_swarm/spine/"):
        return False
    # Everything else is grandfathered in PR A.
    return True


def _check_spine_importable() -> list[str]:
    """Verify spine modules parse and export expected symbols."""
    import subprocess

    failures: list[str] = []
    # Run in a subprocess with a clean PYTHONPATH pointing at repo root.
    # Use a flat import that bypasses dharma_swarm/__init__.py (which needs
    # pydantic and other heavy deps not available in the CI minimal env).
    script = (
        "import sys, types, os\n"
        "root = os.environ['REPO_ROOT']\n"
        "sys.path.insert(0, root)\n"
        "# Register parent packages as empty stubs so submodule imports resolve\n"
        "sys.modules.setdefault('dharma_swarm', types.ModuleType('dharma_swarm'))\n"
        "sys.modules['dharma_swarm'].__path__ = [os.path.join(root, 'dharma_swarm')]\n"
        "sp = types.ModuleType('dharma_swarm.spine')\n"
        "sp.__path__ = [os.path.join(root, 'dharma_swarm', 'spine')]\n"
        "sys.modules['dharma_swarm.spine'] = sp\n"
        "from dharma_swarm.spine import receipt, routing, invoke\n"
        "assert hasattr(receipt, 'EvidenceReceipt'), 'missing EvidenceReceipt'\n"
        "assert hasattr(routing, 'RoutingDecision'), 'missing RoutingDecision'\n"
        "assert hasattr(invoke, 'invoke_agent'), 'missing invoke_agent'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True,
        env={**os.environ, "REPO_ROOT": str(_REPO_ROOT)},
    )
    if result.returncode != 0:
        err = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
        failures.append(f"FAIL: cannot import dharma_swarm.spine: {err}")
    return failures


def main() -> int:
    failures: list[str] = []
    failures.extend(_check_spine_importable())
    failures.extend(_check_sqlite_declarations())

    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(f"\n{len(failures)} spine-check failure(s).", file=sys.stderr)
        return 1

    print("spine-check: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
