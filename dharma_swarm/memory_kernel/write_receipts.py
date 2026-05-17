"""Governed append-only write receipts for MemoryKernel proposals.

This API records proposed MemoryKernel writes as immutable artifacts. It does
not write canon, Chetana, prompt context, projection stores, or legacy memory DBs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.context_admission import redact_context_text


WRITE_RECEIPT_SCHEMA_VERSION = "memory_kernel_write_receipt.v1"
DEFAULT_WRITE_RECEIPT_PATH = Path("reports/memory_kernel/write_receipts.jsonl")
APPEND_ONLY_OPERATIONS = {
    "append_proposal",
    "append_receipt",
    "append_review",
    "append_tombstone",
}
FORBIDDEN_DIRECT_TARGET_TOKENS = {
    "canon",
    "chetana",
    "context",
    "legacy",
    "lancedb",
    "memory_plane",
    "prompt",
    "projection",
    "runtime_state",
    "smriti",
    "vector",
}
FORBIDDEN_DIRECT_TARGET_FRAGMENTS = {
    "canon",
    "canonical",
    "chetana",
    "context",
    "lancedb",
    "legacy",
    "memoryplane",
    "projection",
    "prompt",
    "runtime",
    "runtimestate",
    "smriti",
    "vector",
}
SOURCE_ATOM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,159}$")
REDACTION_MARKERS = ("<local_path_redacted>", "<secret_like_redacted>")


class MemoryKernelWritePolicyOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class MemoryKernelWriteReceiptInput:
    source_atom_ids: tuple[str, ...]
    proposed_operation: str
    target_surface: str
    reason: str
    reviewer_state: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKernelWritePolicyDecision:
    outcome: MemoryKernelWritePolicyOutcome
    reasons: tuple[str, ...]
    target_surface: str
    append_only: bool
    direct_mutation_blocked: bool

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["outcome"] = self.outcome.value
        return payload


@dataclass(frozen=True)
class MemoryKernelWriteReceipt:
    schema_version: str
    receipt_id: str
    digest: str
    created_at: str
    request: MemoryKernelWriteReceiptInput
    policy_decision: MemoryKernelWritePolicyDecision
    rollback_reference: str
    mutation_performed: bool
    artifact_record_only: bool

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "digest": self.digest,
            "created_at": self.created_at,
            "request": self.request.to_json(),
            "policy_decision": self.policy_decision.to_json(),
            "rollback_reference": self.rollback_reference,
            "mutation_performed": self.mutation_performed,
            "artifact_record_only": self.artifact_record_only,
        }


@dataclass(frozen=True)
class MemoryKernelWriteReceiptStatus:
    schema_version: str
    receipt_path: str
    receipt_count: int
    allowed_receipt_count: int
    denied_receipt_count: int
    denied_direct_mutation_count: int
    immutable_log: bool
    ready: bool
    blockers: tuple[str, ...]
    latest_allowed_receipt_id: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def governed_write_receipt(
    request: MemoryKernelWriteReceiptInput,
    *,
    created_at: str | None = None,
) -> MemoryKernelWriteReceipt:
    resolved_created_at = created_at or utc_now()
    safe_request = MemoryKernelWriteReceiptInput(
        source_atom_ids=tuple(
            _safe_source_atom_id(atom_id) for atom_id in request.source_atom_ids
        ),
        proposed_operation=redact_context_text(request.proposed_operation.strip()),
        target_surface=redact_context_text(request.target_surface.strip()),
        reason=redact_context_text(request.reason.strip()),
        reviewer_state=redact_context_text(request.reviewer_state.strip()),
    )
    decision = decide_write_receipt_policy(safe_request)
    rollback_reference = _stable_id(
        "memory_kernel_write_rollback",
        safe_request.proposed_operation,
        safe_request.target_surface,
        *safe_request.source_atom_ids,
    )
    digest_payload = {
        "schema_version": WRITE_RECEIPT_SCHEMA_VERSION,
        "created_at": resolved_created_at,
        "request": safe_request.to_json(),
        "policy_decision": decision.to_json(),
        "rollback_reference": rollback_reference,
        "mutation_performed": False,
        "artifact_record_only": True,
    }
    digest = stable_digest(digest_payload)
    return MemoryKernelWriteReceipt(
        schema_version=WRITE_RECEIPT_SCHEMA_VERSION,
        receipt_id=f"memory_kernel_write_receipt:{digest[:24]}",
        digest=digest,
        created_at=resolved_created_at,
        request=safe_request,
        policy_decision=decision,
        rollback_reference=rollback_reference,
        mutation_performed=False,
        artifact_record_only=True,
    )


def decide_write_receipt_policy(
    request: MemoryKernelWriteReceiptInput,
) -> MemoryKernelWritePolicyDecision:
    operation = request.proposed_operation.strip().lower()
    append_only = operation in APPEND_ONLY_OPERATIONS
    direct_blocked = is_protected_memory_target(request.target_surface)
    reasons = []
    if not request.source_atom_ids:
        reasons.append("missing_source_atom_ids")
    elif not source_atom_ids_are_admissible(request.source_atom_ids):
        reasons.append("source_atom_ids_redacted_or_invalid")
    if not append_only:
        reasons.append("operation_not_append_only")
    if direct_blocked:
        reasons.append("direct_memory_or_canon_mutation_blocked")
    if not request.reason.strip():
        reasons.append("missing_reason")
    if not request.reviewer_state.strip():
        reasons.append("missing_reviewer_state")
    outcome = (
        MemoryKernelWritePolicyOutcome.DENY
        if reasons
        else MemoryKernelWritePolicyOutcome.ALLOW
    )
    if not reasons:
        reasons.append("append_only_receipt_or_proposal_allowed")
    return MemoryKernelWritePolicyDecision(
        outcome=outcome,
        reasons=tuple(reasons),
        target_surface=request.target_surface,
        append_only=append_only,
        direct_mutation_blocked=direct_blocked,
    )


def append_write_receipts(
    path: Path,
    receipts: Iterable[MemoryKernelWriteReceipt],
    *,
    forbidden_roots: Iterable[Path] = (),
) -> None:
    resolved = path.expanduser().resolve()
    for root in forbidden_roots:
        if is_relative_to(resolved, root.expanduser().resolve()):
            raise ValueError("write receipts must not be written under memory surfaces")
    materialized = tuple(receipts)
    if not materialized:
        return
    existing = _receipt_digest_index(resolved)
    for receipt in materialized:
        prior = existing.get(receipt.receipt_id)
        if prior is not None and prior != receipt.digest:
            raise ValueError("write receipt log contains conflicting immutable receipt")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        for receipt in materialized:
            handle.write(canonical_json(receipt.to_json()) + "\n")


def load_write_receipt_status(path: Path) -> MemoryKernelWriteReceiptStatus:
    resolved = path.expanduser().resolve()
    receipts, immutable = load_write_receipts(resolved)
    allowed = tuple(
        row
        for row in receipts
        if _policy_outcome(row) == MemoryKernelWritePolicyOutcome.ALLOW.value
    )
    denied = tuple(
        row
        for row in receipts
        if _policy_outcome(row) == MemoryKernelWritePolicyOutcome.DENY.value
    )
    denied_direct = tuple(
        row
        for row in denied
        if bool(row.get("policy_decision", {}).get("direct_mutation_blocked"))
    )
    blockers = []
    if not resolved.exists():
        blockers.append("write_receipt_log_missing")
    if not immutable:
        blockers.append("write_receipt_log_not_immutable")
    if not allowed:
        blockers.append("no_allowed_append_only_write_receipt")
    if not denied_direct:
        blockers.append("direct_mutation_denial_receipt_missing")
    return MemoryKernelWriteReceiptStatus(
        schema_version=WRITE_RECEIPT_SCHEMA_VERSION,
        receipt_path=resolved.as_posix(),
        receipt_count=len(receipts),
        allowed_receipt_count=len(allowed),
        denied_receipt_count=len(denied),
        denied_direct_mutation_count=len(denied_direct),
        immutable_log=immutable,
        ready=not blockers,
        blockers=tuple(blockers),
        latest_allowed_receipt_id=str(allowed[-1].get("receipt_id", "")) if allowed else "",
    )


def load_write_receipts(path: Path) -> tuple[tuple[dict[str, object], ...], bool]:
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
        if not _valid_receipt_row(row):
            immutable = False
            continue
        receipt_id = str(row["receipt_id"])
        digest = str(row["digest"])
        if receipt_id in seen and seen[receipt_id] != digest:
            immutable = False
        seen[receipt_id] = digest
        rows.append(row)
    return tuple(rows), immutable


def receipt_from_json(row: dict[str, object]) -> MemoryKernelWriteReceipt:
    request = row.get("request", {})
    policy = row.get("policy_decision", {})
    if not isinstance(request, dict) or not isinstance(policy, dict):
        raise ValueError("invalid write receipt row")
    return MemoryKernelWriteReceipt(
        schema_version=str(row.get("schema_version", "")),
        receipt_id=str(row.get("receipt_id", "")),
        digest=str(row.get("digest", "")),
        created_at=str(row.get("created_at", "")),
        request=MemoryKernelWriteReceiptInput(
            source_atom_ids=tuple(str(item) for item in request.get("source_atom_ids", ())),
            proposed_operation=str(request.get("proposed_operation", "")),
            target_surface=str(request.get("target_surface", "")),
            reason=str(request.get("reason", "")),
            reviewer_state=str(request.get("reviewer_state", "")),
        ),
        policy_decision=MemoryKernelWritePolicyDecision(
            outcome=MemoryKernelWritePolicyOutcome(str(policy.get("outcome", ""))),
            reasons=tuple(str(item) for item in policy.get("reasons", ())),
            target_surface=str(policy.get("target_surface", "")),
            append_only=bool(policy.get("append_only")),
            direct_mutation_blocked=bool(policy.get("direct_mutation_blocked")),
        ),
        rollback_reference=str(row.get("rollback_reference", "")),
        mutation_performed=bool(row.get("mutation_performed")),
        artifact_record_only=bool(row.get("artifact_record_only")),
    )


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def stable_digest(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def is_protected_memory_target(target_surface: str) -> bool:
    tokens = _target_tokens(target_surface)
    if tokens & FORBIDDEN_DIRECT_TARGET_TOKENS:
        return True
    fingerprint = _target_fingerprint(target_surface)
    return any(fragment in fingerprint for fragment in FORBIDDEN_DIRECT_TARGET_FRAGMENTS)


def source_atom_ids_are_admissible(source_atom_ids: Iterable[str]) -> bool:
    ids = tuple(str(atom_id) for atom_id in source_atom_ids)
    return bool(ids) and all(_source_atom_id_is_admissible(atom_id) for atom_id in ids)


def with_digest(receipt: MemoryKernelWriteReceipt, digest: str) -> MemoryKernelWriteReceipt:
    return replace(receipt, digest=digest)


def _valid_receipt_row(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("schema_version") != WRITE_RECEIPT_SCHEMA_VERSION:
        return False
    digest = row.get("digest")
    return isinstance(digest, str) and digest == stable_digest(_digest_payload(row))


def _digest_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": row.get("schema_version"),
        "created_at": row.get("created_at"),
        "request": row.get("request"),
        "policy_decision": row.get("policy_decision"),
        "rollback_reference": row.get("rollback_reference"),
        "mutation_performed": row.get("mutation_performed"),
        "artifact_record_only": row.get("artifact_record_only"),
    }


def _receipt_digest_index(path: Path) -> dict[str, str]:
    receipts, _ = load_write_receipts(path)
    return {str(row["receipt_id"]): str(row["digest"]) for row in receipts}


def _policy_outcome(row: dict[str, object]) -> str:
    policy = row.get("policy_decision", {})
    if not isinstance(policy, dict):
        return ""
    value = policy.get("outcome")
    return value if isinstance(value, str) else ""


def _target_tokens(target_surface: str) -> set[str]:
    normalized = target_surface.lower()
    return {part for part in re.split(r"[^a-z0-9]+|_", normalized) if part}


def _target_fingerprint(target_surface: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", target_surface.lower())


def _safe_source_atom_id(value: object) -> str:
    redacted = redact_context_text(str(value).strip())
    return redacted[:180].rstrip()


def _source_atom_id_is_admissible(value: str) -> bool:
    stripped = value.strip()
    if stripped != value or not stripped:
        return False
    if any(marker in stripped for marker in REDACTION_MARKERS):
        return False
    return bool(SOURCE_ATOM_ID_PATTERN.fullmatch(stripped))


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:24]}"
