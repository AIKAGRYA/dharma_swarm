#!/usr/bin/env python3
"""Render the read-only cybernetics_codex closure-ledger audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.cybernetics_codex import build_audit, format_markdown  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--state-dir", default=str(Path.home() / ".dharma"))
    parser.add_argument("--runtime-db", default=None)
    parser.add_argument(
        "--since",
        default=None,
        help="limit runtime DB evidence to rows at or after this ISO timestamp",
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    parser.add_argument(
        "--write-report",
        type=Path,
        default=None,
        help="explicitly write the report to this path; default is stdout only",
    )
    args = parser.parse_args(argv)

    report = build_audit(
        repo_root=Path(args.repo_root),
        state_dir=Path(args.state_dir),
        runtime_db=Path(args.runtime_db) if args.runtime_db else None,
        since=args.since,
    )
    text = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.json
        else format_markdown(report) + "\n"
    )
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(text, encoding="utf-8")
        print(f"wrote: {args.write_report}")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
