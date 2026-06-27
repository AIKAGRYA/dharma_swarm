#!/usr/bin/env python3
"""Verify a LivingDock projection without creating or repairing files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.living_dock_verifier import verify_living_dock  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-uid", required=True)
    parser.add_argument("--dharma-home", default=str(Path.home() / ".dharma"))
    parser.add_argument("--agents-root", default="")
    parser.add_argument("--require-dialogue", action="store_true")
    parser.add_argument("--require-sanctum", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = verify_living_dock(
        args.agent_uid,
        dharma_home=Path(args.dharma_home),
        agents_root=Path(args.agents_root) if args.agents_root else None,
        require_dialogue=args.require_dialogue,
        require_sanctum=args.require_sanctum,
    )
    data = report.to_dict()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(f"LivingDock {report.agent_uid}: {report.status}")
        print(f"path: {report.living_dock_path}")
        for finding in report.findings:
            print(f"- {finding.severity.upper()} {finding.code}: {finding.message} {finding.path}")
    return 1 if report.status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

