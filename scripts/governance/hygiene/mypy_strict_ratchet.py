#!/usr/bin/env python3
"""mypy --strict per-module ratchet.

A typing-quality membrane. Modules in `STRICT_MODULES` MUST pass
`mypy --strict`. New modules can be added as they're cleaned.
Existing modules CANNOT regress out of strict (the ratchet only turns up).

Design: per-module allowlist (not whole-package strict) so the ratchet
ticks forward at human pace without blocking unrelated PRs.

Exit codes:
  0 - all listed modules pass strict
  1 - one or more modules failed
  2 - mypy invocation error
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Modules that MUST pass `mypy --strict`. Add to this list ONLY when
# the module passes cleanly. Removing requires a governance-comment PR.
STRICT_MODULES: list[str] = [
    "dharma_swarm/event_log.py",
    "dharma_swarm/checkpoint.py",
    "dharma_swarm/revenue/spine.py",
    "dharma_swarm/revenue/spine_models.py",
    "dharma_swarm/ontology.py",
    # canonical_replay.py has 2 trivial untyped lines (lines 283, 354)
    # — pending cleanup PR; will be added once those are fixed.
]


def run_mypy_on(module: str, repo_root: Path) -> tuple[bool, str]:
    """Run mypy --strict on a single module. Return (ok, output)."""
    full = repo_root / module
    if not full.exists():
        return False, f"FILE NOT FOUND: {module}"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-incremental",
            "--follow-imports=silent",
            str(full),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, (result.stdout + result.stderr).strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    failures: list[tuple[str, str]] = []
    print(f"mypy --strict ratchet: checking {len(STRICT_MODULES)} modules")
    print("=" * 60)
    for module in STRICT_MODULES:
        ok, output = run_mypy_on(module, repo_root)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {module}")
        if not ok:
            failures.append((module, output))

    print("=" * 60)
    if failures:
        print(f"\n{len(failures)} module(s) failed:\n")
        for module, output in failures:
            print(f"--- {module} ---")
            print(output)
            print()
        return 1
    print(f"OK: all {len(STRICT_MODULES)} modules pass mypy --strict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
