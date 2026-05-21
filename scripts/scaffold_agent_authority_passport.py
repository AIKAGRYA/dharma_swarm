#!/usr/bin/env python3
"""Scaffold an authority passport for a registered external agent.

This deliberately does not promote, dispatch, or grant runtime power. It writes
the first reviewable authority artifact under the agent's own sandbox.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402


PASSPORT_SCHEMA_VERSION = "dharma_agent_authority_passport.v0"
REVIEW_LOG_SCHEMA_VERSION = "dharma_agent_authority_review_log.v0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_dump(payload), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _agent_root(dharma_home: Path, agent_uid: str) -> Path:
    return dharma_home / "external_agents" / agent_uid


def _require_registered_agent(root: Path) -> dict[str, Any]:
    registration_path = root / "registration.json"
    if not registration_path.exists():
        raise SystemExit(f"missing registration.json: {registration_path}")
    return _read_json(registration_path)


def build_passport(
    *,
    dharma_home: Path,
    registration: dict[str, Any],
    rank: str,
    lanes: tuple[str, ...],
    review_days: int,
    reviewer: str,
) -> dict[str, Any]:
    now = _utc_now()
    agent_uid = str(registration["agent_uid"])
    callsign = str(registration["callsign"])
    root = _agent_root(dharma_home, agent_uid)
    review_after = now + timedelta(days=review_days)

    allowed = [
        "read_registered_identity_surfaces",
        "read_own_sandbox",
        "write_own_action_log",
        "write_own_wake_receipts",
        "write_own_self_model",
        "emit_kaizenops_events_about_self",
        "emit_stigmergy_marks_about_observed_work",
        "produce_operator_briefs",
        "propose_agentops_work_packets",
        "request_operator_approval",
    ]
    gated = [
        "run_agentops_work_packet",
        "write_repo_files",
        "modify_cron_or_launchd",
        "send_external_messages",
        "register_or_modify_other_agents",
        "write_memory_kernel_proposals",
        "change_model_or_provider",
    ]
    forbidden = [
        "read_or_write_secrets_without_operator_approval",
        "approve_prs",
        "merge_or_push_code",
        "mutate_meta_dharma",
        "mutate_telos",
        "mutate_dharma_kernel",
        "mutate_dgm_protected_files",
        "author_context_bundles",
        "delete_shared_state",
        "self_promote_authority",
    ]

    return {
        "schema_version": PASSPORT_SCHEMA_VERSION,
        "agent_uid": agent_uid,
        "callsign": callsign,
        "display_name": registration.get("display_name", callsign),
        "harness": registration.get("harness", ""),
        "model_identity": registration.get("model_identity", ""),
        "registration_authority": registration.get("authority", ""),
        "rank": rank,
        "status": "scaffolded_not_promoted",
        "active_lanes": list(lanes),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "review_after": review_after.isoformat(),
        "reviewer": reviewer,
        "principle": (
            "Authority is capability-specific, evidence-backed, expiring, "
            "and never granted by registration alone."
        ),
        "lanes": {
            "morning_ops_operator": {
                "purpose": "Daily/overnight operational awareness and briefing.",
                "allowed": [
                    "read ops telemetry and own Hermes/dharma receipts",
                    "summarize overnight state",
                    "emit KaizenOps events",
                    "emit Stigmergy marks",
                    "append action and wake receipts",
                    "propose scoped AgentOps packets",
                ],
                "requires_approval_for": [
                    "source writes",
                    "cron changes",
                    "external messaging",
                    "secret access",
                    "model/provider changes",
                ],
            }
        },
        "capabilities": {
            "allowed": allowed,
            "gated": gated,
            "forbidden": forbidden,
        },
        "evidence_requirements": {
            "maintain_rank": [
                "complete action_log.jsonl entries for material actions",
                "recent wake_receipts.jsonl entries for unattended wakes",
                "no forbidden write attempts",
                "clear stop/approval requests for gated actions",
            ],
            "consider_promotion": [
                "7 consecutive days of healthy wake receipts",
                "at least 3 useful operator briefs or equivalent artifacts",
                "no secret/protected-surface incidents",
                "operator attestation for expanded lane",
                "successful dry-run AgentOps packet proposal",
            ],
        },
        "receipt_paths": {
            "registration": str(root / "registration.json"),
            "living_agent": str(dharma_home / "agents" / agent_uid / "living_agent.json"),
            "a2a_card": str(dharma_home / "a2a" / "cards" / f"{callsign}.json"),
            "action_log": str(root / "logs" / "action_log.jsonl"),
            "wake_receipts": str(root / "logs" / "wake_receipts.jsonl"),
            "agentops_contract": str(root / "agentops" / "contract.json"),
        },
        "promotion_model": {
            "automatic_promotion": False,
            "operator_review_required": True,
            "capability_specific": True,
            "expires_without_review": True,
            "revocation_path": str(root / "authority" / "reviews.jsonl"),
        },
    }


def scaffold_passport(
    *,
    dharma_home: Path,
    agent_uid: str,
    rank: str,
    lanes: tuple[str, ...],
    review_days: int,
    reviewer: str,
    dry_run: bool,
) -> dict[str, Any]:
    root = _agent_root(dharma_home, agent_uid)
    registration = _require_registered_agent(root)
    passport = build_passport(
        dharma_home=dharma_home,
        registration=registration,
        rank=rank,
        lanes=lanes,
        review_days=review_days,
        reviewer=reviewer,
    )
    if dry_run:
        return passport

    passport_path = root / "authority" / "passport.json"
    reviews_path = root / "authority" / "reviews.jsonl"
    _write_json(passport_path, passport)
    _append_jsonl(
        reviews_path,
        {
            "schema_version": REVIEW_LOG_SCHEMA_VERSION,
            "timestamp": passport["created_at"],
            "agent_uid": agent_uid,
            "event": "authority_passport_scaffolded",
            "rank": rank,
            "lanes": list(lanes),
            "reviewer": reviewer,
            "status": "scaffolded_not_promoted",
            "passport_path": str(passport_path),
        },
    )
    return passport


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold an authority passport for a registered external agent."
    )
    parser.add_argument("--agent-uid", required=True)
    parser.add_argument("--rank", default="operator_candidate")
    parser.add_argument(
        "--lane",
        action="append",
        default=["morning_ops_operator"],
        help="Authority lane to scaffold. May be repeated.",
    )
    parser.add_argument("--review-days", type=int, default=14)
    parser.add_argument("--reviewer", default="operator:dhyana")
    parser.add_argument(
        "--dharma-home",
        type=Path,
        default=dharma_state_dir("DHARMA_HOME"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    passport = scaffold_passport(
        dharma_home=args.dharma_home.expanduser().resolve(),
        agent_uid=args.agent_uid,
        rank=args.rank,
        lanes=tuple(dict.fromkeys(args.lane)),
        review_days=args.review_days,
        reviewer=args.reviewer,
        dry_run=args.dry_run,
    )
    print(json.dumps(passport, indent=2, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
