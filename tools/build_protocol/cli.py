"""Operator-facing CLI for build protocol utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from tools.build_protocol.pilot00_dryrun_generator import run_dryrun
from tools.build_protocol.seal_packet import seal_packet


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dharma-build")
    subcommands = parser.add_subparsers(dest="command", required=True)

    plan = subcommands.add_parser("plan", help="emit Pilot-00 dispatch artifacts")
    plan.add_argument("spec_path", type=Path)
    plan.add_argument("--output-base", type=Path, default=None)
    plan.add_argument("--run-id", default=None)

    seal = subcommands.add_parser("seal", help="write ReviewPacket and ProofPacket artifacts")
    seal.add_argument("dryrun_root", type=Path)
    seal.add_argument("--build-packet-id", required=True)
    seal.add_argument("--work-packet-id", default="wp_001")
    seal.add_argument("--reviewer-agent", required=True)
    seal.add_argument("--builder-agent", required=True)
    seal.add_argument("--diff-ref", required=True)
    seal.add_argument("--test-output-ref", default="test_output.txt")
    seal.add_argument("--files", type=int, required=True)
    seal.add_argument("--added", type=int, required=True)
    seal.add_argument("--removed", type=int, default=0)
    seal.add_argument("--gate", action="append", default=[])
    seal.add_argument("--decision", choices=("pass", "fixup", "reject"), default="pass")
    seal.add_argument("--reason", default="WorkPacket passed review and proof seal.")

    args = parser.parse_args(argv)
    if args.command == "plan":
        result = run_dryrun(
            args.spec_path,
            output_base=args.output_base,
            run_id=args.run_id,
        )
        print(result.root)
        return 0
    if args.command == "seal":
        root = args.dryrun_root.expanduser()
        sealed = seal_packet(
            build_packet_id=args.build_packet_id,
            work_packet_id=args.work_packet_id,
            session_id=root.name,
            reviewer_agent=args.reviewer_agent,
            builder_agent=args.builder_agent,
            diff_ref=args.diff_ref,
            test_output_ref=args.test_output_ref,
            diff_summary={"files": args.files, "added": args.added, "removed": args.removed},
            gate_results=_parse_gates(args.gate),
            decision=args.decision,
            reason=args.reason,
        )
        (root / "review_packet.json").write_text(
            json.dumps(sealed["review_packet"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (root / "proof_packet.json").write_text(
            json.dumps(sealed["proof_packet"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(root)
        return 0
    return 2


def _parse_gates(values: Sequence[str]) -> dict[str, dict[str, str]]:
    gates: dict[str, dict[str, str]] = {}
    for value in values:
        name, sep, result = value.partition("=")
        if not sep or result not in {"pass", "fail", "hold"}:
            raise SystemExit(f"gate must use NAME=pass|fail|hold: {value}")
        gates[name] = {"result": result, "reason": result, "evidence": value}
    return gates or {"manual_review": {"result": "pass", "reason": "manual", "evidence": ""}}


if __name__ == "__main__":
    raise SystemExit(main())
