"""Append-only burn-in receipts for MemoryKernel context preview gates.

The receipts summarize shadow and parity evidence. They are proof artifacts,
not memory truth, prompt context, canon, or retrieval feedback.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


BURN_IN_RECEIPT_SCHEMA_VERSION = "memory_kernel_burn_in_receipt.v1"
DEFAULT_BURN_IN_RECEIPT_PATH = Path("reports/memory_kernel/burn_in_receipts.jsonl")
DEFAULT_BURN_IN_SUMMARY_PATH = Path("reports/memory_kernel/burn_in_latest.json")


@dataclass(frozen=True)
class MemoryKernelBurnInReceipt:
    schema_version: str
    receipt_id: str
    digest: str
    created_at: str
    status: str
    strict_readiness_ready: bool
    synthetic_canary_detected: bool
    rollback_available: bool
    context_case_count: int
    context_case_failure_count: int
    context_case_hard_failure_count: int
    shadow_scenario_count: int
    parity_hard_failure_count: int
    warning_count: int
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryKernelBurnInStatus:
    schema_version: str
    receipt_path: str
    required_run_count: int
    max_age_seconds: int
    ready_receipt_count: int
    latest_receipt_id: str
    latest_created_at: str
    latest_age_seconds: int | None
    synthetic_canary_detected: bool
    parity_hard_failure_count: int
    immutable_log: bool
    burn_in_ready: bool
    blockers: tuple[str, ...]
    receipts: tuple[dict[str, object], ...]

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def build_burn_in_receipt(
    *,
    strict_readiness_ready: bool,
    synthetic_canary_detected: bool,
    rollback_available: bool,
    context_case_count: int,
    context_case_failure_count: int,
    context_case_hard_failure_count: int,
    shadow_scenario_count: int,
    parity_hard_failure_count: int,
    warning_count: int,
    created_at: str | None = None,
    warnings: Iterable[str] = (),
) -> MemoryKernelBurnInReceipt:
    resolved_created_at = created_at or utc_now()
    status = "passed"
    blockers = []
    if not strict_readiness_ready:
        blockers.append("strict_readiness_not_ready")
    if not synthetic_canary_detected:
        blockers.append("synthetic_canary_not_detected")
    if not rollback_available:
        blockers.append("rollback_unavailable")
    if context_case_failure_count:
        blockers.append("context_case_failures")
    if context_case_hard_failure_count:
        blockers.append("context_case_hard_failures")
    if parity_hard_failure_count:
        blockers.append("parity_hard_failures")
    if blockers:
        status = "blocked"
    payload = {
        "schema_version": BURN_IN_RECEIPT_SCHEMA_VERSION,
        "created_at": resolved_created_at,
        "status": status,
        "strict_readiness_ready": strict_readiness_ready,
        "synthetic_canary_detected": synthetic_canary_detected,
        "rollback_available": rollback_available,
        "context_case_count": context_case_count,
        "context_case_failure_count": context_case_failure_count,
        "context_case_hard_failure_count": context_case_hard_failure_count,
        "shadow_scenario_count": shadow_scenario_count,
        "parity_hard_failure_count": parity_hard_failure_count,
        "warning_count": warning_count,
        "warnings": tuple(dict.fromkeys((*warnings, *blockers))),
    }
    digest = stable_digest(payload)
    return MemoryKernelBurnInReceipt(
        receipt_id=f"memory_kernel_burn_in:{digest[:24]}",
        digest=digest,
        **payload,
    )


def append_burn_in_receipt(
    path: Path,
    receipt: MemoryKernelBurnInReceipt,
    *,
    forbidden_roots: Iterable[Path] = (),
) -> None:
    resolved = path.expanduser().resolve()
    for root in forbidden_roots:
        if is_relative_to(resolved, root.expanduser().resolve()):
            raise ValueError("burn-in receipts must not be written under memory surfaces")
    existing = _receipt_digest_index(resolved)
    prior = existing.get(receipt.receipt_id)
    if prior is not None and prior != receipt.digest:
        raise ValueError("burn-in receipt log contains conflicting immutable receipt")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(receipt.to_json()) + "\n")


def write_burn_in_summary(path: Path, status: MemoryKernelBurnInStatus) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(canonical_json(status.to_json()) + "\n", encoding="utf-8")


def load_burn_in_status(
    path: Path,
    *,
    min_run_count: int = 1,
    max_age_seconds: int = 86_400,
    now: datetime | None = None,
) -> MemoryKernelBurnInStatus:
    resolved = path.expanduser().resolve()
    receipts, immutable = load_burn_in_receipts(resolved)
    ready_receipts = tuple(row for row in receipts if row.get("status") == "passed")
    latest = ready_receipts[-1] if ready_receipts else {}
    latest_created_at = str(latest.get("created_at", ""))
    latest_age = _age_seconds(latest_created_at, now=now) if latest_created_at else None
    blockers = []
    if not resolved.exists():
        blockers.append("burn_in_receipt_log_missing")
    if not immutable:
        blockers.append("burn_in_receipt_log_not_immutable")
    if len(ready_receipts) < min_run_count:
        blockers.append("burn_in_min_run_count_not_met")
    if latest_age is None:
        blockers.append("burn_in_latest_receipt_missing")
    elif latest_age < 0:
        blockers.append("burn_in_latest_receipt_from_future")
    elif latest_age > max_age_seconds:
        blockers.append("burn_in_latest_receipt_stale")
    return MemoryKernelBurnInStatus(
        schema_version=BURN_IN_RECEIPT_SCHEMA_VERSION,
        receipt_path=resolved.as_posix(),
        required_run_count=min_run_count,
        max_age_seconds=max_age_seconds,
        ready_receipt_count=len(ready_receipts),
        latest_receipt_id=str(latest.get("receipt_id", "")),
        latest_created_at=latest_created_at,
        latest_age_seconds=latest_age,
        synthetic_canary_detected=bool(latest.get("synthetic_canary_detected")),
        parity_hard_failure_count=int(latest.get("parity_hard_failure_count", 0) or 0),
        immutable_log=immutable,
        burn_in_ready=not blockers,
        blockers=tuple(blockers),
        receipts=ready_receipts[-5:],
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


def load_burn_in_receipts(path: Path) -> tuple[tuple[dict[str, object], ...], bool]:
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


def _valid_receipt_row(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("schema_version") != BURN_IN_RECEIPT_SCHEMA_VERSION:
        return False
    digest = row.get("digest")
    return isinstance(digest, str) and digest == stable_digest(_receipt_digest_payload(row))


def _receipt_digest_index(path: Path) -> dict[str, str]:
    receipts, _ = load_burn_in_receipts(path)
    return {str(row["receipt_id"]): str(row["digest"]) for row in receipts}


def _receipt_digest_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"receipt_id", "digest"}
    }


def _age_seconds(value: str, *, now: datetime | None) -> int | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    reference = now or datetime.now(UTC)
    return int((reference - parsed).total_seconds())
