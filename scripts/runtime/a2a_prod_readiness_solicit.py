#!/usr/bin/env python3
"""Prepare A2A production-readiness quorum review requests.

This script does not claim consensus and does not mark the A2A track ready. It
creates reviewer request packets and a receipt so persistent agents can produce
the JSON records validated by ``a2a_prod_readiness_quorum.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "reports" / "a2a" / "prod_readiness_quorum"
SOLICITATION_SCHEMA = "dharma.a2a.prod_readiness_solicitation.v1"
SOLICITATION_RECEIPT_SCHEMA = "dharma.a2a.prod_readiness_solicitation_receipt.v1"
REVIEWER_SCHEMA = "dharma.a2a.prod_readiness_reviewer.v1"

DEFAULT_EVIDENCE_REFS = [
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/README.md",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/PRODUCTION_READINESS_QUORUM.md",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/NATS_DRAIN_AND_RESET_RUNBOOK.md",
    "reports/a2a/nats_reset/2026-06-13/AFTER.json",
    "reports/a2a/nats_reset/2026-06-13/DRAIN_APPLIED_RECEIPT.json",
    "reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json",
    "reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json",
    "reports/a2a/nats_reset/2026-06-13/NATS_COMMON_FAILURES.md",
    "reports/a2a/nats_reset/2026-06-13/NATS_INTERACTION_HISTORY_72H.json",
    "reports/a2a/nats_reset/2026-06-13/FILE_INBOX_QUARANTINE_THIRD_PASS_APPLIED.json",
    "reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json",
    "reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json",
    "reports/a2a/inbox_quarantine_receipts/20260612T182948Z-a2a-inbox-quarantine.json",
    "reports/a2a/inbox_quarantine_receipts/20260612T183000Z-a2a-inbox-quarantine.json",
    "reports/a2a/inbox_quarantine_receipts/20260612T192816Z-a2a-inbox-quarantine.json",
    "reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json",
    "reports/a2a/agni_live_contact_drill/2026-06-13/AGNI_A2A_LIVE_CONTACT_DRILL_RECEIPT.json",
    "reports/a2a/prod_readiness_quorum/latest_delivery_status.json",
    "reports/a2a/prod_readiness_quorum/latest.json",
]


@dataclass(frozen=True)
class ReviewerTarget:
    agent_id: str
    model_family_hint: str
    role: str
    route: str = "a2a"


DEFAULT_REVIEWERS = [
    ReviewerTarget(
        agent_id="codex_composer",
        model_family_hint="openai",
        role="ops_verifier",
    ),
    ReviewerTarget(
        agent_id="fable_composer",
        model_family_hint="anthropic",
        role="adversarial_security_reviewer",
    ),
    ReviewerTarget(
        agent_id="hermes_m5",
        model_family_hint="hermes",
        role="agent_harness_reviewer",
    ),
    ReviewerTarget(
        agent_id="qwen_code",
        model_family_hint="alibaba",
        role="adversarial_security_reviewer",
    ),
    ReviewerTarget(
        agent_id="gemini_reviewer",
        model_family_hint="google",
        role="independent_production_reviewer",
        route="cli",
    ),
]

TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_token(value: str, *, label: str) -> str:
    token = value.strip()
    if not token or not TOKEN_RE.fullmatch(token):
        raise ValueError(f"{label} must contain only letters, digits, underscore, dash, or dot")
    return token


def parse_reviewer_spec(spec: str) -> ReviewerTarget:
    parts = spec.split(":")
    if len(parts) not in (3, 4):
        raise ValueError(
            "--reviewer must use agent_id:model_family_hint:role[:route]"
        )
    agent_id, model_family_hint, role = (
        safe_token(parts[0], label="agent_id"),
        safe_token(parts[1], label="model_family_hint"),
        safe_token(parts[2], label="role"),
    )
    route = safe_token(parts[3], label="route") if len(parts) == 4 else "a2a"
    return ReviewerTarget(
        agent_id=agent_id,
        model_family_hint=model_family_hint,
        role=role,
        route=route,
    )


def reviewer_record_path(root: Path, date: str, agent_id: str) -> str:
    return str(root / date / f"{agent_id}.json")


def build_request(
    *,
    root: Path,
    date: str,
    requested_by: str,
    target: ReviewerTarget,
    evidence_refs: list[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    when = created_at or utc_now()
    return {
        "schema_version": SOLICITATION_SCHEMA,
        "created_at": when,
        "date": date,
        "requested_by": requested_by,
        "target_agent_id": target.agent_id,
        "model_family_hint": target.model_family_hint,
        "requested_role": target.role,
        "route": target.route,
        "reviewer_record_schema": REVIEWER_SCHEMA,
        "reviewer_record_path": reviewer_record_path(root, date, target.agent_id),
        "quorum_requirements": {
            "min_persistent_agent_ids": 2,
            "min_model_families": 3,
            "median_readiness_percent_min": 80,
            "red_blockers_allowed": 0,
            "requires_adversarial_or_security_role": True,
            "requires_operations_or_devops_role": True,
            "requires_evidence_refs": True,
        },
        "requested_output_fields": [
            "schema_version",
            "agent_id",
            "model_family",
            "role",
            "readiness_percent",
            "verdict",
            "red_blockers",
            "evidence_refs",
            "created_at",
        ],
        "review_questions": [
            "Is the A2A Runtime Spine ready for limited operator-supervised production?",
            "What exact readiness percentage do you assign, from 0 to 100?",
            "Which red blockers, if any, prevent production readiness?",
            "Which receipts or code paths ground your verdict?",
            "Does any claim confuse publish ack, handler ack, domain receipt, or filesystem inbox presence?",
        ],
        "evidence_refs": evidence_refs,
        "instructions": (
            "Write exactly one JSON reviewer record at reviewer_record_path. "
            "Self-report the actual model_family used; model_family_hint is only a routing hint. "
            "Do not mark ready if red blockers remain."
        ),
    }


def write_solicitations(
    *,
    root: Path,
    date: str,
    reviewers: list[ReviewerTarget],
    requested_by: str,
    evidence_refs: list[str],
    write: bool = True,
    created_at: str | None = None,
) -> dict[str, Any]:
    if not reviewers:
        raise ValueError("at least one reviewer is required")
    when = created_at or utc_now()
    request_dir = root / date / "requests"
    requests = [
        build_request(
            root=root,
            date=date,
            requested_by=requested_by,
            target=reviewer,
            evidence_refs=evidence_refs,
            created_at=when,
        )
        for reviewer in reviewers
    ]

    request_paths: list[str] = []
    if write:
        request_dir.mkdir(parents=True, exist_ok=True)
        for request in requests:
            path = request_dir / f"{request['target_agent_id']}.json"
            path.write_text(
                json.dumps(request, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            request_paths.append(str(path))
    else:
        request_paths = [str(request_dir / f"{request['target_agent_id']}.json") for request in requests]

    receipt = {
        "schema_version": SOLICITATION_RECEIPT_SCHEMA,
        "created_at": when,
        "date": date,
        "status": "SOLICITATION_WRITTEN" if write else "DRY_RUN",
        "transport_status": "NOT_SENT",
        "transport_note": (
            "Request packets are durable repo artifacts only. Send them through "
            "scripts/runtime/a2a_send.py or another governed A2A route to prove delivery."
        ),
        "requested_by": requested_by,
        "root": str(root),
        "request_dir": str(request_dir),
        "request_count": len(requests),
        "request_paths": request_paths,
        "target_agent_ids": [reviewer.agent_id for reviewer in reviewers],
        "model_family_hints": sorted({reviewer.model_family_hint for reviewer in reviewers}),
        "roles": [reviewer.role for reviewer in reviewers],
        "evidence_refs": evidence_refs,
        "next_command": (
            f"python3 scripts/runtime/a2a_prod_readiness_quorum.py --date {date} "
            "--allow-not-ready --write-latest"
        ),
    }
    if write:
        receipt_path = root / date / "SOLICITATION_RECEIPT.json"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipt["receipt_path"] = str(receipt_path)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--requested-by", default="codex_composer")
    parser.add_argument(
        "--reviewer",
        action="append",
        help="agent_id:model_family_hint:role[:route]; repeat for multiple reviewers",
    )
    parser.add_argument(
        "--evidence-ref",
        action="append",
        help="Evidence path to include; defaults to current A2A reset/readiness receipts",
    )
    parser.add_argument("--dry-run", action="store_true", help="print receipt without writing files")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reviewers = (
            [parse_reviewer_spec(spec) for spec in args.reviewer]
            if args.reviewer
            else list(DEFAULT_REVIEWERS)
        )
        evidence_refs = args.evidence_ref or list(DEFAULT_EVIDENCE_REFS)
        receipt = write_solicitations(
            root=args.root,
            date=args.date,
            reviewers=reviewers,
            requested_by=safe_token(args.requested_by, label="requested_by"),
            evidence_refs=evidence_refs,
            write=not args.dry_run,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    output = json.dumps(receipt, indent=2, sort_keys=True)
    if args.json or args.dry_run:
        print(output)
    else:
        print(
            f"{receipt['status']} requests={receipt['request_count']} "
            f"dir={receipt['request_dir']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
