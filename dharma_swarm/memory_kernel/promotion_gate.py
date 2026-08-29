"""Human-gated MemoryKernel promotion receipts.

Promotion emits reviewed canonical receipts only. It never mutates canon,
Chetana, prompt context, projection stores, or legacy memory databases.

Human approval is a single explicit boolean supplied by the caller
(`human_approved`) plus a free-text `rationale`. There is no self-checked
gate battery here: provenance/conflict/privacy/canon review happens upstream
(KnowledgeOps decision ledger, write-receipt policy) or it does not happen.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.context_admission import redact_context_text
from dharma_swarm.memory_kernel.write_receipts import (
    MemoryKernelWritePolicyOutcome,
    MemoryKernelWriteReceiptInput,
    WRITE_RECEIPT_SCHEMA_VERSION,
    canonical_json,
    decide_write_receipt_policy,
    is_protected_memory_target,
    is_relative_to,
    load_write_receipts,
    source_atom_ids_are_admissible,
    stable_digest,
)


PROMOTION_DECISION_SCHEMA_VERSION = "memory_kernel_promotion_decision.v1"
REVIEWED_CANONICAL_RECEIPT_SCHEMA_VERSION = "memory_kernel_reviewed_canonical_receipt.v1"
DEFAULT_PROMOTION_DECISION_PATH = Path("reports/memory_kernel/promotion_decisions.jsonl")
DEFAULT_REVIEWED_CANONICAL_RECEIPT_PATH = Path(
    "reports/memory_kernel/reviewed_canonical_receipts.jsonl"
)


class MemoryKernelPromotionDecisionKind(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"


class MemoryKernelPromotionReceiptStatus(StrEnum):
    REVIEWED = "reviewed_canonical_receipt"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class MemoryKernelPromotionDecision:
    schema_version: str
    decision_id: str
    write_receipt_id: str
    decision: MemoryKernelPromotionDecisionKind
    human_approved: bool
    rationale: str
    created_at: str
    source_proposal_id: str = ""
    source_decision_id: str = ""
    target_authority_surface: str = ""

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        return payload


@dataclass(frozen=True)
class MemoryKernelReviewedCanonicalReceipt:
    schema_version: str
    canonical_receipt_id: str
    digest: str
    created_at: str
    source_write_receipt_id: str
    source_atom_ids: tuple[str, ...]
    source_proposal_id: str
    source_decision_id: str
    target_authority_surface: str
    status: MemoryKernelPromotionReceiptStatus
    human_approved: bool
    mutation_performed: bool
    artifact_record_only: bool
    rollback_reference: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class MemoryKernelPromotionStatus:
    schema_version: str
    receipt_path: str
    reviewed_receipt_count: int
    blocked_receipt_count: int
    human_approved_count: int
    immutable_log: bool
    rollback_engaged: bool
    promotion_ready: bool
    blockers: tuple[str, ...]
    latest_canonical_receipt_id: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def build_promotion_decision(
    *,
    write_receipt_id: str,
    human_approved: bool,
    rationale: str,
    decision: MemoryKernelPromotionDecisionKind = MemoryKernelPromotionDecisionKind.APPROVE,
    created_at: str | None = None,
    source_proposal_id: str = "",
    source_decision_id: str = "",
    target_authority_surface: str = "",
) -> MemoryKernelPromotionDecision:
    resolved_created_at = created_at or utc_now()
    safe_rationale = redact_context_text(rationale.strip())
    safe_source_proposal_id = redact_context_text(source_proposal_id.strip())
    safe_source_decision_id = redact_context_text(source_decision_id.strip())
    safe_target_authority_surface = redact_context_text(target_authority_surface.strip())
    decision_id_parts = [
        write_receipt_id,
        decision.value,
        str(bool(human_approved)),
        safe_rationale,
    ]
    if safe_source_proposal_id:
        decision_id_parts.extend(("source_proposal_id", safe_source_proposal_id))
    if safe_source_decision_id:
        decision_id_parts.extend(("source_decision_id", safe_source_decision_id))
    if safe_target_authority_surface:
        decision_id_parts.extend(("target_authority_surface", safe_target_authority_surface))
    decision_id = _stable_id("memory_kernel_promotion_decision", *decision_id_parts)
    return MemoryKernelPromotionDecision(
        schema_version=PROMOTION_DECISION_SCHEMA_VERSION,
        decision_id=decision_id,
        write_receipt_id=write_receipt_id,
        decision=decision,
        human_approved=bool(human_approved),
        rationale=safe_rationale,
        created_at=resolved_created_at,
        source_proposal_id=safe_source_proposal_id,
        source_decision_id=safe_source_decision_id,
        target_authority_surface=safe_target_authority_surface,
    )


def reviewed_canonical_receipt(
    write_receipt: dict[str, object],
    decision: MemoryKernelPromotionDecision,
    *,
    rollback_engaged: bool = False,
    created_at: str | None = None,
) -> MemoryKernelReviewedCanonicalReceipt:
    resolved_created_at = created_at or utc_now()
    source_atom_ids = _source_atom_ids(write_receipt)
    blockers = list(_promotion_blockers(write_receipt, decision, rollback_engaged))
    human_approved = (
        decision.decision == MemoryKernelPromotionDecisionKind.APPROVE
        and decision.human_approved
    )
    status = (
        MemoryKernelPromotionReceiptStatus.BLOCKED
        if blockers
        else MemoryKernelPromotionReceiptStatus.REVIEWED
    )
    rollback_reference = _stable_id(
        "memory_kernel_promotion_rollback",
        str(write_receipt.get("receipt_id", "")),
        decision.decision_id,
    )
    digest_payload = {
        "schema_version": REVIEWED_CANONICAL_RECEIPT_SCHEMA_VERSION,
        "created_at": resolved_created_at,
        "source_write_receipt_id": str(write_receipt.get("receipt_id", "")),
        "source_atom_ids": source_atom_ids,
        "source_proposal_id": decision.source_proposal_id,
        "source_decision_id": decision.source_decision_id,
        "target_authority_surface": decision.target_authority_surface,
        "status": status.value,
        "human_approved": human_approved,
        "mutation_performed": False,
        "artifact_record_only": True,
        "rollback_reference": rollback_reference,
        "blockers": tuple(blockers),
        "warnings": (
            "reviewed_canonical_receipt_only",
            "no_silent_memory_or_canon_mutation",
        ),
    }
    digest = stable_digest(digest_payload)
    return MemoryKernelReviewedCanonicalReceipt(
        schema_version=REVIEWED_CANONICAL_RECEIPT_SCHEMA_VERSION,
        canonical_receipt_id=f"memory_kernel_canonical_receipt:{digest[:24]}",
        digest=digest,
        created_at=resolved_created_at,
        source_write_receipt_id=str(write_receipt.get("receipt_id", "")),
        source_atom_ids=source_atom_ids,
        source_proposal_id=decision.source_proposal_id,
        source_decision_id=decision.source_decision_id,
        target_authority_surface=decision.target_authority_surface,
        status=status,
        human_approved=human_approved,
        mutation_performed=False,
        artifact_record_only=True,
        rollback_reference=rollback_reference,
        blockers=tuple(blockers),
        warnings=(
            "reviewed_canonical_receipt_only",
            "no_silent_memory_or_canon_mutation",
        ),
    )


def append_promotion_artifacts(
    *,
    decision_path: Path | None,
    canonical_receipt_path: Path | None,
    decisions: Iterable[MemoryKernelPromotionDecision],
    canonical_receipts: Iterable[MemoryKernelReviewedCanonicalReceipt],
    forbidden_roots: Iterable[Path] = (),
) -> None:
    if decision_path is not None:
        _append_jsonl(
            decision_path,
            (decision.to_json() for decision in decisions),
            forbidden_roots=forbidden_roots,
        )
    if canonical_receipt_path is not None:
        _append_canonical_receipts(
            canonical_receipt_path,
            canonical_receipts,
            forbidden_roots=forbidden_roots,
        )


def load_promotion_status(
    path: Path,
    *,
    rollback_engaged: bool = False,
) -> MemoryKernelPromotionStatus:
    resolved = path.expanduser().resolve()
    receipts, immutable = load_canonical_receipts(resolved)
    reviewed = tuple(
        row
        for row in receipts
        if row.get("status") == MemoryKernelPromotionReceiptStatus.REVIEWED.value
    )
    blocked = tuple(
        row
        for row in receipts
        if row.get("status") == MemoryKernelPromotionReceiptStatus.BLOCKED.value
    )
    human_approved = tuple(row for row in reviewed if bool(row.get("human_approved")))
    blockers = []
    if not resolved.exists():
        blockers.append("promotion_receipt_log_missing")
    if not immutable:
        blockers.append("promotion_receipt_log_not_immutable")
    if rollback_engaged:
        blockers.append("rollback_engaged")
    if not human_approved:
        blockers.append("no_human_approved_reviewed_canonical_receipt")
    return MemoryKernelPromotionStatus(
        schema_version=REVIEWED_CANONICAL_RECEIPT_SCHEMA_VERSION,
        receipt_path=resolved.as_posix(),
        reviewed_receipt_count=len(reviewed),
        blocked_receipt_count=len(blocked),
        human_approved_count=len(human_approved),
        immutable_log=immutable,
        rollback_engaged=rollback_engaged,
        promotion_ready=not blockers,
        blockers=tuple(blockers),
        latest_canonical_receipt_id=(
            str(human_approved[-1].get("canonical_receipt_id", ""))
            if human_approved
            else ""
        ),
    )


def latest_allowed_write_receipt(path: Path) -> dict[str, object] | None:
    receipts, immutable = load_write_receipts(path.expanduser().resolve())
    if not immutable:
        return None
    allowed = [
        row
        for row in receipts
        if row.get("schema_version") == WRITE_RECEIPT_SCHEMA_VERSION
        and row.get("policy_decision", {}).get("outcome")
        == MemoryKernelWritePolicyOutcome.ALLOW.value
    ]
    return allowed[-1] if allowed else None


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _promotion_blockers(
    write_receipt: dict[str, object],
    decision: MemoryKernelPromotionDecision,
    rollback_engaged: bool,
) -> tuple[str, ...]:
    blockers = []
    policy = write_receipt.get("policy_decision", {})
    request = write_receipt.get("request", {})
    if rollback_engaged:
        blockers.append("rollback_engaged")
    if not isinstance(policy, dict) or policy.get("outcome") != "allow":
        blockers.append("write_receipt_policy_not_allow")
    if not bool(write_receipt.get("artifact_record_only")):
        blockers.append("write_receipt_not_artifact_only")
    if bool(write_receipt.get("mutation_performed")):
        blockers.append("write_receipt_claims_mutation")
    if not _source_atom_ids(write_receipt):
        blockers.append("missing_source_atom_ids")
    if isinstance(request, dict):
        target_surface = str(request.get("target_surface", "")).lower()
        policy_recheck = decide_write_receipt_policy(
            MemoryKernelWriteReceiptInput(
                source_atom_ids=tuple(
                    str(item) for item in request.get("source_atom_ids", ())
                ),
                proposed_operation=str(request.get("proposed_operation", "")),
                target_surface=str(request.get("target_surface", "")),
                reason=str(request.get("reason", "")),
                reviewer_state=str(request.get("reviewer_state", "")),
            )
        )
        if policy_recheck.outcome != MemoryKernelWritePolicyOutcome.ALLOW:
            blockers.append("write_receipt_policy_recheck_not_allow")
        if is_protected_memory_target(target_surface):
            blockers.append("protected_target_surface_not_promotable")
        if not source_atom_ids_are_admissible(_source_atom_ids(write_receipt)):
            blockers.append("source_atom_ids_not_admissible")
        if "projection" in target_surface:
            blockers.append("projection_target_not_authority")
        if "secret" in str(request.get("reason", "")).lower():
            blockers.append("unredacted_secret_like_reason")
        if str(request.get("reviewer_state", "")) != "human_approved":
            blockers.append("write_receipt_not_human_approved")
    else:
        blockers.append("write_receipt_request_missing")
    if decision.decision != MemoryKernelPromotionDecisionKind.APPROVE:
        blockers.append("promotion_decision_not_approve")
    if not decision.human_approved:
        blockers.append("promotion_not_human_approved")
    if not decision.rationale.strip():
        blockers.append("missing_human_rationale")
    return tuple(blockers)


def _source_atom_ids(write_receipt: dict[str, object]) -> tuple[str, ...]:
    request = write_receipt.get("request", {})
    if not isinstance(request, dict):
        return ()
    return tuple(str(item) for item in request.get("source_atom_ids", ()))


def _append_jsonl(
    path: Path,
    rows: Iterable[dict[str, object]],
    *,
    forbidden_roots: Iterable[Path],
) -> None:
    resolved = path.expanduser().resolve()
    for root in forbidden_roots:
        if is_relative_to(resolved, root.expanduser().resolve()):
            raise ValueError("promotion artifacts must not be written under memory surfaces")
    materialized = tuple(rows)
    if not materialized:
        return
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(canonical_json(row) + "\n")


def _append_canonical_receipts(
    path: Path,
    receipts: Iterable[MemoryKernelReviewedCanonicalReceipt],
    *,
    forbidden_roots: Iterable[Path],
) -> None:
    resolved = path.expanduser().resolve()
    for root in forbidden_roots:
        if is_relative_to(resolved, root.expanduser().resolve()):
            raise ValueError("promotion artifacts must not be written under memory surfaces")
    materialized = tuple(receipts)
    if not materialized:
        return
    existing = _canonical_receipt_digest_index(resolved)
    for receipt in materialized:
        prior = existing.get(receipt.canonical_receipt_id)
        if prior is not None and prior != receipt.digest:
            raise ValueError("promotion receipt log contains conflicting immutable receipt")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        for receipt in materialized:
            handle.write(canonical_json(receipt.to_json()) + "\n")


def load_canonical_receipts(path: Path) -> tuple[tuple[dict[str, object], ...], bool]:
    if not path.exists():
        return (), True
    rows = []
    seen: dict[str, str] = {}
    immutable = True
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            immutable = False
            continue
        if not _valid_canonical_receipt_row(row):
            immutable = False
            continue
        receipt_id = str(row["canonical_receipt_id"])
        digest = str(row["digest"])
        if receipt_id in seen and seen[receipt_id] != digest:
            immutable = False
        seen[receipt_id] = digest
        rows.append(row)
    return tuple(rows), immutable


def _valid_canonical_receipt_row(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("schema_version") != REVIEWED_CANONICAL_RECEIPT_SCHEMA_VERSION:
        return False
    digest = row.get("digest")
    return isinstance(digest, str) and digest == stable_digest(_canonical_digest_payload(row))


def _canonical_receipt_digest_index(path: Path) -> dict[str, str]:
    receipts, _ = load_canonical_receipts(path)
    return {str(row["canonical_receipt_id"]): str(row["digest"]) for row in receipts}


def _canonical_digest_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"canonical_receipt_id", "digest"}
    }


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"
