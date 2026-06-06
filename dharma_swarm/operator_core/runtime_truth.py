"""Shared runtime-truth packet helpers for operator projections.

This module owns no live state. It provides shell-neutral shapes that scripts
can use when they project receipts, probes, and cache files into runtime truth.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class RuntimeTruthState(StrEnum):
    RUNNING_BY_HEARTBEAT = "RUNNING_BY_HEARTBEAT"
    PROGRESSING_BY_ARTIFACT = "PROGRESSING_BY_ARTIFACT"
    STALLED_BY_ARTIFACT_PROGRESS = "STALLED_BY_ARTIFACT_PROGRESS"
    BLOCKED_BY_RECEIPT = "BLOCKED_BY_RECEIPT"
    COMPLETED_BY_RECEIPT = "COMPLETED_BY_RECEIPT"
    EXTERNAL_GATED = "EXTERNAL_GATED"
    DEGRADED_BY_PROBE_FAILURE = "DEGRADED_BY_PROBE_FAILURE"
    PROJECTION_ONLY = "PROJECTION_ONLY"
    CACHE_ONLY_NON_AUTHORITATIVE = "CACHE_ONLY_NON_AUTHORITATIVE"
    UNKNOWN = "UNKNOWN"


class RuntimeSourceKind(StrEnum):
    DIRECT_PROBE = "direct_probe"
    RECEIPT = "receipt"
    ARTIFACT = "artifact"
    CACHE_FILE = "cache_file"
    DECLARED_INTENT = "declared_intent"
    DERIVED_RECONCILIATION = "derived_reconciliation"
    EXTERNAL_OPERATOR_STATE = "external_operator_state"
    PROBE_FAILURE = "probe_failure"
    PROBE_SKIPPED = "probe_skipped"
    MANUAL_FIXTURE = "manual_fixture"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def stable_payload_hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(data.encode('utf-8')).hexdigest()}"


def file_ref(path: Path | str, *, repo_root: Path | None = None, kind: str = "artifact") -> dict[str, Any]:
    resolved = Path(path).expanduser()
    display = str(resolved)
    if repo_root is not None:
        try:
            display = str(resolved.relative_to(repo_root))
        except ValueError:
            display = str(resolved)
    exists = resolved.exists()
    return {
        "kind": kind,
        "path": display,
        "exists": exists,
        "sha256": sha256_file(resolved) if exists and resolved.is_file() else "",
    }


@dataclass(slots=True)
class ProbeTruth:
    command: list[str] = field(default_factory=list)
    observed_at: str = ""
    ok: bool | None = None
    returncode: int | None = None
    error: str = ""
    source_kind: str = RuntimeSourceKind.DIRECT_PROBE.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MutationTruth:
    repo_files_changed: bool = False
    external_actions: bool = False
    process_actions: bool = False
    archive_fitness_mutated: bool = False
    payment_or_publish: bool = False
    push_merge: bool = False
    dry_run_only: bool = False
    human_review_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeTruthPacket:
    surface_id: str
    kind: str
    run_id: str = ""
    mission_id: str = ""
    correlation_id: str = ""
    correlation_id_inferred: bool = False
    task_id: str = ""
    claim_id: str = ""
    runner_id: str = ""
    receipt_refs: list[dict[str, Any]] = field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    heartbeat_state: str = RuntimeTruthState.UNKNOWN.value
    progress_state: str = RuntimeTruthState.UNKNOWN.value
    completion_state: str = RuntimeTruthState.UNKNOWN.value
    authority_state: str = RuntimeTruthState.PROJECTION_ONLY.value
    mutation_truth: MutationTruth = field(default_factory=MutationTruth)
    source_kind: str = RuntimeSourceKind.DERIVED_RECONCILIATION.value
    probe_truth: ProbeTruth = field(default_factory=ProbeTruth)
    missing_machine_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_truth"] = self.mutation_truth.to_dict()
        payload["probe_truth"] = self.probe_truth.to_dict()
        return payload


def task_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"open": 0, "claimed": 0, "completed": 0, "failed": 0, "blocked": 0}
    for task in tasks:
        status = str(task.get("status") or "open")
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = len(tasks)
    return counts


def reconcile_tasks_from_receipts(
    tasks: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    *,
    closing_statuses: set[str],
    nonclosing_statuses: set[str],
    observed_at: str | None = None,
) -> dict[str, Any]:
    observed = observed_at or utc_now()
    raw_counts = task_counts(tasks)
    latest_by_task: dict[str, dict[str, Any]] = {}
    closing_seen: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        task_id = str(receipt.get("task_id") or "")
        status = str(receipt.get("status") or "")
        if task_id and (status in closing_statuses or status in nonclosing_statuses):
            latest_by_task[task_id] = receipt
        if task_id and status in closing_statuses:
            closing_seen[task_id] = receipt

    reconciled_tasks = copy.deepcopy(tasks)
    changes: list[dict[str, Any]] = []
    terminal_receipts: list[dict[str, Any]] = []
    superseded_terminal_receipts: list[dict[str, Any]] = []
    missing_machine_fields: list[str] = []
    for task in reconciled_tasks:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            missing_machine_fields.append("task_id")
            continue
        latest = latest_by_task.get(task_id)
        closing = closing_seen.get(task_id)
        if closing and latest is not closing:
            superseded_terminal_receipts.append(
                {
                    "task_id": task_id,
                    "receipt_id": str(closing.get("receipt_id") or ""),
                    "terminal_status": str(closing.get("status") or ""),
                    "superseded_by_status": str(latest.get("status") or "") if latest else "",
                    "superseded_by_receipt_id": str(latest.get("receipt_id") or "") if latest else "",
                }
            )
        if not latest or str(latest.get("status") or "") not in closing_statuses:
            continue
        old_status = str(task.get("status") or "open")
        receipt_status = str(latest.get("status") or "")
        task["status"] = receipt_status
        task["updated_at"] = str(latest.get("created_at") or observed)
        task["closed_by_receipt"] = True
        task["receipt_id"] = str(latest.get("receipt_id") or "")
        terminal_receipts.append(
            {
                "task_id": task_id,
                "receipt_id": task["receipt_id"],
                "status": receipt_status,
                "artifact_path": str(latest.get("artifact_path") or ""),
                "evidence_present": bool(latest.get("evidence")),
            }
        )
        if receipt_status == "completed" and not latest.get("evidence"):
            missing_machine_fields.append(f"completed_evidence:{task_id}")
        if old_status != receipt_status:
            changes.append(
                {
                    "task_id": task_id,
                    "from": old_status,
                    "to": receipt_status,
                    "receipt_id": task["receipt_id"],
                }
            )

    reconciled_counts = task_counts(reconciled_tasks)
    progress_states: list[str] = []
    if reconciled_counts.get("completed", 0):
        progress_states.append(RuntimeTruthState.COMPLETED_BY_RECEIPT.value)
    if reconciled_counts.get("blocked", 0) or reconciled_counts.get("failed", 0):
        progress_states.append(RuntimeTruthState.BLOCKED_BY_RECEIPT.value)
    if raw_counts.get("claimed", 0) and not changes:
        progress_states.append(RuntimeTruthState.RUNNING_BY_HEARTBEAT.value)
    if changes:
        progress_states.append(RuntimeTruthState.PROGRESSING_BY_ARTIFACT.value)
    if not progress_states:
        progress_states.append(RuntimeTruthState.UNKNOWN.value)

    summary = {
        "schema_version": "dharma.autonomy_reconciled_task_summary.v1",
        "observed_at": observed,
        "authority_state": RuntimeTruthState.PROJECTION_ONLY.value,
        "source_kind": RuntimeSourceKind.DERIVED_RECONCILIATION.value,
        "raw_counts": raw_counts,
        "reconciled_counts": reconciled_counts,
        "raw_reconciled_mismatch": raw_counts != reconciled_counts,
        "changed_task_ids": [change["task_id"] for change in changes],
        "changes": changes,
        "terminal_receipts": terminal_receipts,
        "superseded_terminal_receipts": superseded_terminal_receipts,
        "progress_states": progress_states,
        "missing_machine_fields": sorted(set(missing_machine_fields)),
    }
    summary["idempotency_key"] = stable_payload_hash(
        {
            "raw_counts": raw_counts,
            "reconciled_counts": reconciled_counts,
            "changes": changes,
            "terminal_receipts": terminal_receipts,
            "superseded_terminal_receipts": superseded_terminal_receipts,
        }
    )

    return {
        **summary,
        "tasks": reconciled_tasks,
        "summary": summary,
    }


__all__ = [
    "MutationTruth",
    "ProbeTruth",
    "RuntimeSourceKind",
    "RuntimeTruthPacket",
    "RuntimeTruthState",
    "file_ref",
    "reconcile_tasks_from_receipts",
    "sha256_file",
    "stable_payload_hash",
    "task_counts",
    "utc_now",
]
