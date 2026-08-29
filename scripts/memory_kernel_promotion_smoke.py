#!/usr/bin/env python3
"""Smoke human-gated MemoryKernel promotion receipts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dharma_swarm.memory_kernel import (
    DEFAULT_PROMOTION_DECISION_PATH,
    DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
    DEFAULT_WRITE_RECEIPT_PATH,
    append_promotion_artifacts,
    build_promotion_decision,
    latest_allowed_write_receipt,
    load_promotion_status,
    reviewed_canonical_receipt,
)
from dharma_swarm.operator_core.control_surface_memory import ROLLBACK_ENV_VAR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--write-receipts", type=Path, default=DEFAULT_WRITE_RECEIPT_PATH)
    parser.add_argument("--decision-out", type=Path, default=DEFAULT_PROMOTION_DECISION_PATH)
    parser.add_argument(
        "--canonical-receipt-out",
        type=Path,
        default=DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_receipt = latest_allowed_write_receipt(
        _resolve_output(args.write_receipts, args.repo_root)
    )
    if write_receipt is None:
        print(json.dumps({"error": "no allowed write receipt available"}, indent=2))
        return 2
    rollback_engaged = _truthy(os.environ.get(ROLLBACK_ENV_VAR, ""))
    decision = build_promotion_decision(
        write_receipt_id=str(write_receipt["receipt_id"]),
        human_approved=True,
        rationale="reviewed provenance, conflicts, privacy, and canon policy",
    )
    canonical_receipt = reviewed_canonical_receipt(
        write_receipt,
        decision,
        rollback_engaged=rollback_engaged,
    )
    decision_path = _resolve_output(args.decision_out, args.repo_root)
    canonical_path = _resolve_output(args.canonical_receipt_out, args.repo_root)
    if not args.dry_run:
        append_promotion_artifacts(
            decision_path=decision_path,
            canonical_receipt_path=canonical_path,
            decisions=(decision,),
            canonical_receipts=(canonical_receipt,),
            forbidden_roots=_memory_surface_roots(args.repo_root),
        )
    status = load_promotion_status(canonical_path, rollback_engaged=rollback_engaged)
    payload = {
        "decision": decision.to_json(),
        "canonical_receipt": canonical_receipt.to_json(),
        "status": status.to_json(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.fail_on_blocked and not status.promotion_ready:
        return 5
    return 0


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _memory_surface_roots(repo_root: Path) -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".dharma",
        home / ".smriti",
        home / ".codex" / "memories",
        repo_root / ".dharma",
        repo_root / ".swarm",
    )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "rollback"}


if __name__ == "__main__":
    raise SystemExit(main())
