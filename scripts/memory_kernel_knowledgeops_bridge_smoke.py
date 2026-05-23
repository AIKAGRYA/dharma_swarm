#!/usr/bin/env python3
"""Smoke KnowledgeOps-to-MemoryKernel promotion bridge receipts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dharma_swarm.knowledge_ops.memory_conflict_review import review_memory_conflicts
from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecision,
    MemoryPromotionDecisionKind,
    build_memory_decision_ledger,
)
from dharma_swarm.knowledge_ops.memory_intake import review_memory_atoms
from dharma_swarm.knowledge_ops.memory_kernel_promotion_bridge import (
    append_memory_kernel_promotion_bridge_artifacts,
    execute_memory_kernel_promotion_bridge,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import build_memory_promotion_queue
from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    DEFAULT_PROMOTION_DECISION_PATH,
    DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
    DEFAULT_WRITE_RECEIPT_PATH,
    MemoryAtom,
    MemoryAtomType,
    MemoryScope,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    TruthState,
    WriteMode,
    load_promotion_status,
)
from dharma_swarm.operator_core.control_surface_memory import ROLLBACK_ENV_VAR


DEFAULT_KNOWLEDGEOPS_REQUEST_PATH = Path(
    "reports/memory_kernel/knowledgeops_bridge_requests.jsonl"
)
DEFAULT_KNOWLEDGEOPS_RECEIPT_PATH = Path(
    "reports/memory_kernel/knowledgeops_bridge_receipts.jsonl"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--target-authority-surface",
        default="knowledge_authority.shadow_canon",
    )
    parser.add_argument("--write-receipt-out", type=Path, default=DEFAULT_WRITE_RECEIPT_PATH)
    parser.add_argument("--decision-out", type=Path, default=DEFAULT_PROMOTION_DECISION_PATH)
    parser.add_argument(
        "--canonical-receipt-out",
        type=Path,
        default=DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH,
    )
    parser.add_argument(
        "--knowledgeops-request-out",
        type=Path,
        default=DEFAULT_KNOWLEDGEOPS_REQUEST_PATH,
    )
    parser.add_argument(
        "--knowledgeops-receipt-out",
        type=Path,
        default=DEFAULT_KNOWLEDGEOPS_RECEIPT_PATH,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    queue = build_memory_promotion_queue(
        review_memory_conflicts(review_memory_atoms((_synthetic_atom(),)))
    )
    if not queue.proposals:
        print(json.dumps({"error": "synthetic bridge fixture produced no proposal"}))
        return 2

    proposal = queue.proposals[0]
    ledger = build_memory_decision_ledger(
        queue,
        (
            MemoryPromotionDecision(
                proposal_id=proposal.proposal_id,
                atom_id=proposal.atom_id,
                surface_id=proposal.surface_id,
                decision=MemoryPromotionDecisionKind.ACCEPT,
                reviewer="human",
                rationale="reviewed KnowledgeOps bridge provenance and MemoryKernel gates",
                approved_gates=proposal.required_gates,
            ),
        ),
    )
    rollback_engaged = _truthy(os.environ.get(ROLLBACK_ENV_VAR, ""))
    result = execute_memory_kernel_promotion_bridge(
        queue,
        ledger,
        target_authority_surface=args.target_authority_surface,
        rollback_engaged=rollback_engaged,
    )

    write_receipt_path = _resolve_output(args.write_receipt_out, args.repo_root)
    decision_path = _resolve_output(args.decision_out, args.repo_root)
    canonical_path = _resolve_output(args.canonical_receipt_out, args.repo_root)
    if not args.dry_run:
        append_memory_kernel_promotion_bridge_artifacts(
            result,
            write_receipt_path=write_receipt_path,
            decision_path=decision_path,
            canonical_receipt_path=canonical_path,
            dry_run_request_path=_resolve_output(args.knowledgeops_request_out, args.repo_root),
            dry_run_receipt_path=_resolve_output(args.knowledgeops_receipt_out, args.repo_root),
            forbidden_roots=_memory_surface_roots(args.repo_root),
        )

    status = load_promotion_status(canonical_path, rollback_engaged=rollback_engaged)
    payload = {
        "queue": queue.to_json(),
        "ledger": ledger.to_json(),
        "bridge": result.to_json(),
        "status": status.to_json(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    bridge_ready = result.bridge_record_count > 0 and result.blocked_canonical_receipt_count == 0
    if args.fail_on_blocked and (not bridge_ready or not status.promotion_ready):
        return 5
    return 0


def _synthetic_atom() -> MemoryAtom:
    surface = MemorySurface(
        surface_id="knowledgeops.bridge.synthetic_authority",
        path="/synthetic/knowledgeops_bridge.jsonl",
        owner_module="scripts/memory_kernel_knowledgeops_bridge_smoke.py",
        role=MemorySurfaceRole.RUNTIME_STATE,
        category=SurfaceCategory.RUNTIME_CONTROL,
        authority_level=AuthorityLevel.HIGH,
        write_mode=WriteMode.READ_WRITE,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.SNAPSHOT,
        health=MemorySurfaceHealth(exists=True),
        provenance_quality="synthetic_bridge_smoke",
        canon_risk=RiskLevel.LOW,
        pii_secrets_risk=RiskLevel.LOW,
        latency_risk=RiskLevel.LOW,
    )
    return MemoryAtom.build(
        surface=surface,
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="knowledgeops_bridge:synthetic_reviewed_evidence",
        timestamp="2026-05-17T00:00:00Z",
        source_path="knowledgeops_bridge:synthetic_reviewed_evidence",
        adapter_name="knowledgeops_bridge_smoke",
        read_mode=ReadMode.READ_ONLY,
        scope=MemoryScope.PROJECT,
        truth_state=TruthState.OBSERVED,
        promotion_allowed=True,
    )


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
