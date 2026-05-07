"""Operator-facing CLI for build protocol utilities."""

from __future__ import annotations

import argparse
import asyncio
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
    seal.add_argument("--build-packet-id", default=None)
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

    shadow_apply = subcommands.add_parser(
        "shadow-apply",
        help="ingest a sealed packet through Darwin shadow evaluation",
    )
    shadow_apply.add_argument("dryrun_root", type=Path)
    shadow_apply.add_argument("--workspace", type=Path, default=None)
    shadow_apply.add_argument("--proof-timeout", type=float, default=120.0)
    shadow_apply.add_argument("--max-diff-lines", type=int, default=50)
    shadow_apply.add_argument("--halt-path", type=Path, default=None)
    shadow_apply.add_argument("--archive-path", type=Path, default=None)
    shadow_apply.add_argument("--traces-path", type=Path, default=None)
    shadow_apply.add_argument("--predictor-path", type=Path, default=None)

    opportunity_spec = subcommands.add_parser(
        "opportunity-to-spec",
        help="emit a Pilot-00 spec from one opportunity board row",
    )
    opportunity_spec.add_argument("--board", type=Path, default=None)
    opportunity_spec.add_argument("--opportunity-id", default=None)
    opportunity_spec.add_argument("--index", type=int, default=0)
    opportunity_spec.add_argument("--output-dir", type=Path, default=None)
    opportunity_spec.add_argument("--print", action="store_true")

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
        build_packet_id = _resolve_build_packet_id(root, args.build_packet_id)
        sealed = seal_packet(
            build_packet_id=build_packet_id,
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
    if args.command == "shadow-apply":
        return asyncio.run(_run_shadow_apply(args))
    if args.command == "opportunity-to-spec":
        return _run_opportunity_to_spec(args)
    return 2


def _parse_gates(values: Sequence[str]) -> dict[str, dict[str, str]]:
    gates: dict[str, dict[str, str]] = {}
    for value in values:
        name, sep, result = value.partition("=")
        if not sep or result not in {"pass", "fail", "hold"}:
            raise SystemExit(f"gate must use NAME=pass|fail|hold: {value}")
        gates[name] = {"result": result, "reason": result, "evidence": value}
    return gates or {"manual_review": {"result": "pass", "reason": "manual", "evidence": ""}}


def _resolve_build_packet_id(root: Path, provided: str | None) -> str:
    build_packet_path = root / "build_packet.json"
    canonical = ""
    if build_packet_path.is_file():
        try:
            build_packet = json.loads(build_packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"cannot read build_packet.json: {exc}") from exc
        if isinstance(build_packet, dict):
            canonical = str(build_packet.get("id") or build_packet.get("title") or "").strip()

    value = str(provided or canonical).strip()
    if not value:
        raise SystemExit("--build-packet-id is required when build_packet.json has no id/title")
    if provided and canonical and value != canonical:
        raise SystemExit(
            f"--build-packet-id {value!r} does not match build_packet.json id/title {canonical!r}"
        )
    return value


async def _run_shadow_apply(args: argparse.Namespace) -> int:
    from dharma_swarm.evolution import DarwinEngine

    engine = DarwinEngine(
        archive_path=args.archive_path,
        traces_path=args.traces_path,
        predictor_path=args.predictor_path,
    )
    await engine.init()
    try:
        result = await engine.apply_sealed_packet(
            args.dryrun_root,
            shadow=True,
            workspace=args.workspace,
            proof_timeout=args.proof_timeout,
            max_diff_lines=args.max_diff_lines,
            halt_path=args.halt_path,
        )
    finally:
        await engine.close()

    print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0 if result.accepted else 2


def _run_opportunity_to_spec(args: argparse.Namespace) -> int:
    from tools.build_protocol.opportunity_to_spec import (
        load_opportunity_board,
        render_spec,
        select_opportunity,
        spec_needs_operator_completion,
        write_spec,
    )

    board_path = (
        args.board.expanduser()
        if args.board is not None
        else Path.home() / ".dharma" / "meta" / "opportunity_board.json"
    )
    rows = load_opportunity_board(board_path)
    selected = select_opportunity(
        rows,
        board_path=board_path,
        opportunity_id=args.opportunity_id,
        index=args.index,
    )
    spec_text = render_spec(selected)
    if args.print:
        print(spec_text, end="")
        return 0

    out = write_spec(
        spec_text,
        output_dir=args.output_dir,
        title_slug=_slug_for_opportunity(selected.opportunity_id, selected.title),
    )
    print(out)
    return 2 if spec_needs_operator_completion(spec_text) else 0


def _slug_for_opportunity(opportunity_id: str, title: str) -> str:
    import re

    slug = re.sub(
        r"[^a-zA-Z0-9]+",
        "-",
        f"opportunity-{opportunity_id}-{title}".strip().lower(),
    ).strip("-")
    return slug[:64] or "opportunity"


if __name__ == "__main__":
    raise SystemExit(main())
