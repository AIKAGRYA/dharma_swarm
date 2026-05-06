#!/usr/bin/env python3
"""Run Dharma Swarm governance checks from one stable entrypoint.

This wrapper keeps local and CI invocations independent from the internal
layout of the governance scripts. It intentionally covers Wave A checks only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def build_commands(
    *,
    base_ref: str,
    head_ref: str,
    warn_only: bool,
    skip_module_budget: bool,
) -> list[list[str]]:
    test_hygiene = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "governance" / "check_test_hygiene.py"),
    ]
    if warn_only:
        test_hygiene.append("--warn-only")

    commands = [test_hygiene]
    if not skip_module_budget:
        commands.append(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "governance" / "check_module_budget.py"),
                "--base-ref",
                base_ref,
                "--head-ref",
                head_ref,
            ]
        )
    return commands


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Report findings but exit 0 for advisory local runs.",
    )
    parser.add_argument(
        "--skip-module-budget",
        action="store_true",
        help="Skip the module line-budget gate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    failures = 0
    for command in build_commands(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        warn_only=args.warn_only,
        skip_module_budget=args.skip_module_budget,
    ):
        result = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if result.returncode:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
