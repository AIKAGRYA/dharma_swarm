"""Module line-budget gate (Rule 10).

For each Python file under `dharma_swarm/` and `api/`, compare the line
count between the PR base and the PR head. Fail if any module crosses
the 1000-line threshold without an open issue tagged `decomposition`
that mentions the file by name.

Modules already over budget at the time the rule was introduced are
grandfathered (see `GRANDFATHERED` below). Grandfathered modules can
grow up to 10% beyond their grandfather line count before failing.

Usage (locally):
    python3 scripts/governance/check_module_budget.py \\
        --base-ref origin/main --head-ref HEAD

In CI, the workflow passes the PR base/head SHAs.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Hot-path modules already over the 1000-line budget at 2026-04-26.
# Each entry: file path -> grandfathered line count at install time.
# Decomposition tracking issues are linked from
# docs/governance/ANTI_SLOP_RULES.md.
GRANDFATHERED: dict[str, int] = {
    "dharma_swarm/dgc_cli.py": 7115,
    "dharma_swarm/thinkodynamic_director.py": 5215,
    "dharma_swarm/telos_substrate.py": 4511,
    "dharma_swarm/agent_runner.py": 3691,
    "dharma_swarm/evolution.py": 3401,
    "dharma_swarm/swarm.py": 3252,
    "dharma_swarm/providers.py": 3096,
    "dharma_swarm/orchestrator.py": 2525,
    "dharma_swarm/tui/app.py": 2520,
    "dharma_swarm/terminal_bridge.py": 2539,
}

LINE_BUDGET = 1000  # New modules: hard limit.
GROWTH_TOLERANCE = 0.10  # Grandfathered: +10% before failing.

INCLUDE_PREFIXES = ("dharma_swarm/", "api/")
EXCLUDE_PATTERNS = (
    re.compile(r"^.*/__pycache__/.*$"),
    re.compile(r"^.*/migrations/.*$"),
    re.compile(r"^migration_delta/.*$"),
    re.compile(r"^dharma_swarm_old/.*$"),
)


def is_target_file(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    if not path.startswith(INCLUDE_PREFIXES):
        return False
    return not any(p.match(path) for p in EXCLUDE_PATTERNS)


def line_count(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def file_at_ref(ref: str, path: str) -> str | None:
    """Return file content at `ref`, or None if it didn't exist there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def changed_files(base: str, head: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=AM", base, head],
        text=True,
    )
    return [p.strip() for p in out.splitlines() if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    args = parser.parse_args()

    repo_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    os.chdir(repo_root)

    files = [p for p in changed_files(args.base_ref, args.head_ref) if is_target_file(p)]
    if not files:
        print("No target Python files changed. OK.")
        return 0

    failures: list[str] = []
    warnings: list[str] = []

    for path in files:
        head_path = repo_root / path
        head_lines = line_count(head_path)

        base_content = file_at_ref(args.base_ref, path)
        base_lines = base_content.count("\n") + 1 if base_content else 0

        if path in GRANDFATHERED:
            ceiling = int(GRANDFATHERED[path] * (1 + GROWTH_TOLERANCE))
            if head_lines > ceiling:
                failures.append(
                    f"  {path}: {head_lines} lines exceeds grandfathered "
                    f"ceiling {ceiling} (grandfather={GRANDFATHERED[path]} "
                    f"+{int(GROWTH_TOLERANCE * 100)}%). "
                    f"Open a decomposition issue or shrink the file."
                )
            elif head_lines > GRANDFATHERED[path]:
                warnings.append(
                    f"  {path}: {head_lines} lines (grandfather={GRANDFATHERED[path]}, "
                    f"ceiling={ceiling}). Approaching the budget."
                )
            continue

        # Non-grandfathered files: hard limit at LINE_BUDGET.
        if head_lines > LINE_BUDGET and base_lines <= LINE_BUDGET:
            failures.append(
                f"  {path}: {base_lines} → {head_lines} lines crosses the "
                f"{LINE_BUDGET}-line budget. "
                f"Decompose before merge, or open a decomposition issue and "
                f"add this path to GRANDFATHERED in scripts/governance/check_module_budget.py "
                f"(with the issue link in the PR description)."
            )
        elif head_lines > LINE_BUDGET:
            # Already over budget but not crossing in this PR — warn only.
            warnings.append(
                f"  {path}: {head_lines} lines already exceeds budget; "
                f"this PR did not introduce the breach."
            )

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(w)
        print()

    if failures:
        print("::error::Rule 10 violation(s) — module line budget:")
        for f in failures:
            print(f)
        return 1

    print("Module line-budget check OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
