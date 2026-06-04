"""Typed proposal packets for the read-only live ops cockpit.

The cockpit may render these packets or write them as draft evidence. It must
not execute the proposed action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow, _utc_now_iso


ProposalKind = Literal[
    "runtime_restart_proposal",
    "runtime_stop_proposal",
    "vps_migration_proposal",
    "pr_packet_proposal",
    "pr_close_proposal",
    "pr_merge_proposal",
    "pr_rebase_proposal",
    "operator_hold_proposal",
]


class ActionProposalPacket(BaseModel):
    """Operator-facing proposal packet with no inline execution authority."""

    proposal_id: str
    kind: ProposalKind
    created_at: str
    surface_id: str
    authority_required: str
    source_refs: list[dict[str, Any]]
    evidence_refs: list[dict[str, Any]]
    proposed_command_text: str
    forbidden_inline_execution: bool = True
    risk: str
    rollback: str
    operator_confirmation_token: str
    status: Literal["draft"] = "draft"
    pr_number: int | None = None
    head_sha: str = ""
    queue_status: str = ""
    gate_decision: str = ""
    blockers: list[str] = Field(default_factory=list)
    review_receipts: list[str] = Field(default_factory=list)
    close_reason: str = ""
    survivor_pr: int | None = None
    external_execution_eligible: bool = False


@dataclass(frozen=True)
class ProposalWriteResult:
    """Result of optionally writing proposal packets."""

    packets: list[ActionProposalPacket]
    written_paths: list[Path]


def _stable_proposal_id(kind: str, surface_id: str, raw: dict[str, Any]) -> str:
    material = {
        "kind": kind,
        "surface_id": surface_id,
        "pr_number": raw.get("pr_number"),
        "head_sha": raw.get("head_sha") or raw.get("headRefOid"),
        "queue_status": raw.get("queue_status") or raw.get("status"),
        "gate_decision": raw.get("gate_decision"),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "proposal_" + hashlib.sha256(encoded).hexdigest()[:16]


def _refs_from_row(row: ControlSurfaceRow) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        [ref.model_dump() for ref in row.source_refs],
        [item.model_dump() for item in row.evidence],
    )


def _risk_for_row(row: ControlSurfaceRow) -> str:
    raw_risk = str(row.raw.get("risk") or "").lower()
    if raw_risk:
        return raw_risk
    if row.priority == "p0":
        return "high"
    if row.priority == "p1":
        return "medium"
    return "low"


def _operator_token(proposal_id: str) -> str:
    return f"CONFIRM_OPERATOR_ONLY::{proposal_id}"


def _packet(
    row: ControlSurfaceRow,
    *,
    kind: ProposalKind,
    proposed_command_text: str,
    rollback: str,
    created_at: str | None = None,
    external_execution_eligible: bool = False,
    **extra: Any,
) -> ActionProposalPacket:
    source_refs, evidence_refs = _refs_from_row(row)
    proposal_id = _stable_proposal_id(kind, row.id, row.raw)
    return ActionProposalPacket(
        proposal_id=proposal_id,
        kind=kind,
        created_at=created_at or _utc_now_iso(),
        surface_id=row.id,
        authority_required="operator_explicit_confirmation",
        source_refs=source_refs,
        evidence_refs=evidence_refs,
        proposed_command_text=proposed_command_text,
        risk=_risk_for_row(row),
        rollback=rollback,
        operator_confirmation_token=_operator_token(proposal_id),
        external_execution_eligible=external_execution_eligible,
        **extra,
    )


def proposal_kind_for_row(row: ControlSurfaceRow) -> ProposalKind:
    """Classify the safest proposal kind for a control-surface row."""
    if row.kind == "pr_queue":
        queue_status = str(row.raw.get("queue_status") or row.raw.get("status") or "")
        if row.raw.get("close_reason") or row.raw.get("survivor_pr"):
            return "pr_close_proposal"
        if queue_status == "GITHUB_GREEN_NEEDS_PACKET":
            return "pr_packet_proposal"
        if queue_status in {"NEEDS_REFRESH", "BLOCKED_CONFLICT"}:
            return "pr_rebase_proposal"
        return "operator_hold_proposal"

    next_action = row.next_action.lower()
    if "vps_candidate" in row.gap_codes or "vps" in next_action:
        return "vps_migration_proposal"
    if "stop" in next_action or "kill" in next_action or "quiet" in next_action:
        return "runtime_stop_proposal"
    if "restart" in next_action or "start" in next_action:
        return "runtime_restart_proposal"
    return "operator_hold_proposal"


def proposal_for_row(row: ControlSurfaceRow, *, created_at: str | None = None) -> ActionProposalPacket:
    """Build a non-executable draft proposal packet from a row."""
    kind = proposal_kind_for_row(row)
    if kind == "pr_close_proposal":
        pr_number = int(row.raw.get("pr_number") or row.raw.get("number") or 0) or None
        close_reason = str(row.raw.get("close_reason") or "operator review required before closure")
        survivor = row.raw.get("survivor_pr")
        return _packet(
            row,
            kind=kind,
            proposed_command_text=f"draft PR close packet for #{pr_number}: {close_reason}",
            rollback="reopen PR or remove close packet before operator action",
            created_at=created_at,
            pr_number=pr_number,
            head_sha=str(row.raw.get("head_sha") or ""),
            queue_status=str(row.raw.get("queue_status") or ""),
            blockers=[str(item) for item in row.raw.get("blockers", [])],
            close_reason=close_reason,
            survivor_pr=int(survivor) if survivor else None,
        )
    if kind == "pr_packet_proposal":
        pr_number = int(row.raw.get("pr_number") or row.raw.get("number") or 0) or None
        return _packet(
            row,
            kind=kind,
            proposed_command_text=f"make pr-packet PR={pr_number}",
            rollback="delete draft packet before operator action",
            created_at=created_at,
            pr_number=pr_number,
            head_sha=str(row.raw.get("head_sha") or ""),
            queue_status=str(row.raw.get("queue_status") or ""),
            blockers=[str(item) for item in row.raw.get("blockers", [])],
        )
    if kind == "pr_rebase_proposal":
        pr_number = int(row.raw.get("pr_number") or row.raw.get("number") or 0) or None
        return _packet(
            row,
            kind=kind,
            proposed_command_text=f"prepare rebase/refresh packet for PR #{pr_number}; do not mutate from cockpit",
            rollback="discard refresh packet before operator action",
            created_at=created_at,
            pr_number=pr_number,
            head_sha=str(row.raw.get("head_sha") or ""),
            queue_status=str(row.raw.get("queue_status") or ""),
            blockers=[str(item) for item in row.raw.get("blockers", [])],
        )
    if kind == "runtime_restart_proposal":
        return _packet(
            row,
            kind=kind,
            proposed_command_text=f"operator-approved restart proposal for {row.id}: {row.next_action}",
            rollback="leave process unchanged; discard draft restart packet",
            created_at=created_at,
        )
    if kind == "runtime_stop_proposal":
        return _packet(
            row,
            kind=kind,
            proposed_command_text=f"operator-approved stop proposal for {row.id}: {row.next_action}",
            rollback="leave process unchanged; discard draft stop packet",
            created_at=created_at,
        )
    if kind == "vps_migration_proposal":
        return _packet(
            row,
            kind=kind,
            proposed_command_text=f"draft VPS migration packet for {row.id}; no migration from cockpit",
            rollback="keep workload local; discard draft migration packet",
            created_at=created_at,
        )
    return _packet(
        row,
        kind="operator_hold_proposal",
        proposed_command_text=f"operator hold for {row.id}: {row.next_action or 'review row evidence'}",
        rollback="remove hold packet after operator decision",
        created_at=created_at,
    )


def pr_merge_proposal_for_row(
    row: ControlSurfaceRow,
    *,
    created_at: str | None = None,
    allow_external_execution: bool = False,
) -> ActionProposalPacket:
    """Build a PR merge proposal and gate optional external eligibility."""
    pr_number = int(row.raw.get("pr_number") or row.raw.get("number") or 0) or None
    head_sha = str(row.raw.get("head_sha") or row.raw.get("headRefOid") or "")
    gate_decision = str(row.raw.get("gate_decision") or "")
    review_receipts = [str(item) for item in row.raw.get("review_receipts", [])]
    blockers = [str(item) for item in row.raw.get("blockers", [])]
    human_authority_explicit = bool(row.raw.get("human_authority_explicit"))
    risk = _risk_for_row(row)

    eligible = (
        gate_decision == "PASS"
        and bool(head_sha)
        and bool(review_receipts)
        and not blockers
        and (risk not in {"high", "critical"} or human_authority_explicit)
    )
    if allow_external_execution and not eligible:
        raise ValueError("PR merge proposal is not externally execution-eligible")

    return _packet(
        row,
        kind="pr_merge_proposal",
        proposed_command_text=f"make pr-merge PR={pr_number} EXPECT_HEAD={head_sha} --dry-run",
        rollback="do not merge; discard draft merge proposal",
        created_at=created_at,
        external_execution_eligible=allow_external_execution and eligible,
        pr_number=pr_number,
        head_sha=head_sha,
        queue_status=str(row.raw.get("queue_status") or ""),
        gate_decision=gate_decision,
        blockers=blockers,
        review_receipts=review_receipts,
    )


def proposal_packets_for_rows(
    rows: list[ControlSurfaceRow],
    *,
    created_at: str | None = None,
) -> list[ActionProposalPacket]:
    """Return one draft proposal for every row that has an operator action."""
    packets: list[ActionProposalPacket] = []
    for row in rows:
        if row.next_action or row.human_decision_required or row.kind == "pr_queue":
            packets.append(proposal_for_row(row, created_at=created_at))
    return packets


def emit_proposal_packets(
    packets: list[ActionProposalPacket],
    *,
    output_dir: Path | None = None,
    write: bool = False,
) -> ProposalWriteResult:
    """Optionally write proposal packets. No files are written unless write=True."""
    if not write:
        return ProposalWriteResult(packets=packets, written_paths=[])
    if output_dir is None:
        raise ValueError("output_dir is required when write=True")
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for packet in packets:
        path = output_dir / f"{packet.proposal_id}.json"
        path.write_text(json.dumps(packet.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return ProposalWriteResult(packets=packets, written_paths=written)
