#!/usr/bin/env python3
"""Dry-run the operator command spine and print a packet draft.

This CLI is intentionally non-executing. It does not create worktrees, run
gates, commit, merge, push, or launch live swarm/autonomy. It converts an
operator prompt into a JSON plan plus AgentOps-compatible packet draft.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.command_spine import (
    OperatorCommandRequest,
    plan_operator_command,
    plan_to_dict,
    work_packet_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan a governed operator command packet")
    parser.add_argument("--prompt", required=True, help="Operator prompt to plan")
    parser.add_argument("--base-ref", default="HEAD")
    parser.add_argument("--branch", default="chore/operator-command")
    parser.add_argument("--worktree", default="/tmp/dharma_swarm_operator_command")
    parser.add_argument("--allowed-file", action="append", default=[], help="Repo-relative allowed file/glob")
    parser.add_argument("--forbidden-file", action="append", default=[], help="Repo-relative forbidden file/glob")
    parser.add_argument("--gate", action="append", default=[], help="Gate command; may be repeated")
    parser.add_argument("--knowledge-db", default=None)
    parser.add_argument("--mission-state-dir", default=None)
    parser.add_argument("--mission-path", default=None)
    parser.add_argument("--packet-only", action="store_true", help="Print only the AgentOps packet shape")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gates: list[dict[str, str]] = [
        {"name": f"gate-{index + 1}", "command": command}
        for index, command in enumerate(args.gate)
    ]
    request_kwargs: dict[str, Any] = {
        "prompt": args.prompt,
        "base_ref": args.base_ref,
        "branch": args.branch,
        "worktree": args.worktree,
        "allowed_files": args.allowed_file,
        "knowledge_db_path": args.knowledge_db,
        "mission_state_dir": args.mission_state_dir,
        "mission_path": args.mission_path,
    }
    if args.forbidden_file:
        request_kwargs["forbidden_files"] = args.forbidden_file
    if gates:
        request_kwargs["gates"] = gates

    plan = plan_operator_command(OperatorCommandRequest(**request_kwargs))
    payload = work_packet_to_dict(plan.work_packet) if args.packet_only else plan_to_dict(plan)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
