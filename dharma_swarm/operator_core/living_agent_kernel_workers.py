"""External worker lifecycle receipts for LivingAgentKernel wakes.

This module lets already-running workers participate in the existing wake
ledger through registration, heartbeat, lease, result, and recovery receipts.
It does not spawn worker processes, call providers, or create a second queue.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import (
    DEFAULT_KERNEL_RUN_DIR,
    KernelRunStatus,
    KernelRunStore,
    KernelWakeRecord,
)
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

KernelExternalWorkerStateValue = Literal["registered", "online", "stale", "offline"]
KernelExternalWorkerHeartbeatValue = Literal["online", "offline"]
KernelExternalWorkerLeaseStatus = Literal["leased", "idle", "denied"]


class KernelExternalWorkerRecord(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_external_worker.v1"
    worker_id: str
    role: str = "worker"
    allowed_sources: list[str] = Field(default_factory=list)
    max_lease_seconds: int = 300
    metadata: dict[str, Any] = Field(default_factory=dict)
    registered_at: str = Field(default_factory=utc_now)
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelExternalWorkerHeartbeat(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_external_worker_heartbeat.v1"
    worker_id: str
    status: KernelExternalWorkerHeartbeatValue = "online"
    observed_at: str = Field(default_factory=utc_now)
    lease_owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelExternalWorkerState(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_external_worker_state.v1"
    worker_id: str
    role: str = "worker"
    status: KernelExternalWorkerStateValue = "registered"
    observed_at: str = Field(default_factory=utc_now)
    heartbeat_age_seconds: float | None = None
    registered_ref: dict[str, Any] = Field(default_factory=dict)
    heartbeat_ref: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class KernelExternalWorkerLease(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_external_worker_lease.v1"
    status: KernelExternalWorkerLeaseStatus
    worker_id: str
    wake_id: str = ""
    run_id: str = ""
    lease_expires_at: str = ""
    reason: str = ""
    wake_record: KernelWakeRecord | None = None
    created_at: str = Field(default_factory=utc_now)
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelExternalWorkerResult(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_external_worker_result.v1"
    worker_id: str
    wake_id: str
    run_id: str
    status: KernelRunStatus
    summary: str = ""
    result_ref: dict[str, Any] = Field(default_factory=dict)
    completed_at: str = Field(default_factory=utc_now)
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelExternalWorkerRecovery(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_external_worker_recovery.v1"
    status: Literal["completed"] = "completed"
    observed_at: str = Field(default_factory=utc_now)
    stale_worker_ids: list[str] = Field(default_factory=list)
    recovered_wake_ids: list[str] = Field(default_factory=list)
    reason: str = "expired_external_worker_leases_recovered"
    previous_record_hash: str = ""
    record_hash: str = ""


class KernelExternalWorkerStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.base_dir / "worker_registry.jsonl"
        self.heartbeat_path = self.base_dir / "worker_heartbeats.jsonl"
        self.lease_path = self.base_dir / "worker_leases.jsonl"
        self.result_path = self.base_dir / "worker_results.jsonl"
        self.recovery_path = self.base_dir / "worker_recoveries.jsonl"
        self.kernel_store = KernelRunStore(self.base_dir)

    def register_worker(
        self,
        worker_id: str,
        *,
        role: str = "worker",
        allowed_sources: list[str] | tuple[str, ...] | None = None,
        max_lease_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> KernelExternalWorkerRecord:
        record = KernelExternalWorkerRecord(
            worker_id=_required(worker_id, "worker_id"),
            role=role or "worker",
            allowed_sources=_sorted_unique(allowed_sources or []),
            max_lease_seconds=max(1, int(max_lease_seconds)),
            metadata=dict(metadata or {}),
            registered_at=now or utc_now(),
        )
        return _append_hashed(self.registry_path, record, KernelExternalWorkerRecord)

    def heartbeat_worker(
        self,
        worker_id: str,
        *,
        status: KernelExternalWorkerHeartbeatValue = "online",
        metadata: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> KernelExternalWorkerHeartbeat:
        if worker_id not in self.latest_workers():
            raise ValueError(f"external worker is not registered: {worker_id}")
        heartbeat = KernelExternalWorkerHeartbeat(
            worker_id=worker_id,
            status=status,
            observed_at=now or utc_now(),
            lease_owner=worker_id,
            metadata=dict(metadata or {}),
        )
        return _append_hashed(self.heartbeat_path, heartbeat, KernelExternalWorkerHeartbeat)

    def workers(self) -> list[KernelExternalWorkerRecord]:
        return [KernelExternalWorkerRecord.model_validate(row) for row in _jsonl_rows(self.registry_path)]

    def heartbeats(self) -> list[KernelExternalWorkerHeartbeat]:
        return [KernelExternalWorkerHeartbeat.model_validate(row) for row in _jsonl_rows(self.heartbeat_path)]

    def leases(self) -> list[KernelExternalWorkerLease]:
        return [KernelExternalWorkerLease.model_validate(row) for row in _jsonl_rows(self.lease_path)]

    def results(self) -> list[KernelExternalWorkerResult]:
        return [KernelExternalWorkerResult.model_validate(row) for row in _jsonl_rows(self.result_path)]

    def recoveries(self) -> list[KernelExternalWorkerRecovery]:
        return [KernelExternalWorkerRecovery.model_validate(row) for row in _jsonl_rows(self.recovery_path)]

    def latest_workers(self) -> dict[str, KernelExternalWorkerRecord]:
        latest: dict[str, KernelExternalWorkerRecord] = {}
        for record in self.workers():
            latest[record.worker_id] = record
        return latest

    def latest_heartbeats(self) -> dict[str, KernelExternalWorkerHeartbeat]:
        latest: dict[str, KernelExternalWorkerHeartbeat] = {}
        for heartbeat in self.heartbeats():
            latest[heartbeat.worker_id] = heartbeat
        return latest

    def worker_states(
        self,
        *,
        stale_after_seconds: int = 120,
        offline_after_seconds: int = 3600,
        now: str | None = None,
    ) -> list[KernelExternalWorkerState]:
        observed_at = now or utc_now()
        heartbeats = self.latest_heartbeats()
        states: list[KernelExternalWorkerState] = []
        for worker in self.latest_workers().values():
            heartbeat = heartbeats.get(worker.worker_id)
            if heartbeat is None:
                states.append(
                    KernelExternalWorkerState(
                        worker_id=worker.worker_id,
                        role=worker.role,
                        status="registered",
                        observed_at=observed_at,
                        registered_ref=_record_ref(self.registry_path, worker.record_hash),
                        message="Registered worker has not emitted a heartbeat.",
                    )
                )
                continue
            age = (_parse_utc(observed_at) - _parse_utc(heartbeat.observed_at)).total_seconds()
            if heartbeat.status == "offline" or age > max(1, int(offline_after_seconds)):
                status: KernelExternalWorkerStateValue = "offline"
                message = "Worker heartbeat is offline."
            elif age > max(1, int(stale_after_seconds)):
                status = "stale"
                message = "Worker heartbeat is stale."
            else:
                status = "online"
                message = "Worker heartbeat is fresh."
            states.append(
                KernelExternalWorkerState(
                    worker_id=worker.worker_id,
                    role=worker.role,
                    status=status,
                    observed_at=observed_at,
                    heartbeat_age_seconds=age,
                    registered_ref=_record_ref(self.registry_path, worker.record_hash),
                    heartbeat_ref=_record_ref(self.heartbeat_path, heartbeat.record_hash),
                    message=message,
                )
            )
        return sorted(states, key=lambda state: state.worker_id)

    def lease_worker_wake(
        self,
        worker_id: str,
        *,
        lease_seconds: int = 300,
        heartbeat_max_age_seconds: int = 120,
        now: str | None = None,
    ) -> KernelExternalWorkerLease:
        observed_at = now or utc_now()
        worker = self.latest_workers().get(worker_id)
        if worker is None:
            return self._append_lease(
                KernelExternalWorkerLease(
                    status="denied",
                    worker_id=worker_id,
                    reason="worker_not_registered",
                    created_at=observed_at,
                )
            )
        state = self._state_for_worker(worker_id, heartbeat_max_age_seconds=heartbeat_max_age_seconds, now=observed_at)
        if state is None or state.status != "online":
            if state is None or state.status == "registered":
                reason = "worker_heartbeat_missing_or_stale"
            else:
                reason = f"worker_{state.status}"
            return self._append_lease(
                KernelExternalWorkerLease(
                    status="denied",
                    worker_id=worker_id,
                    reason=reason,
                    created_at=observed_at,
                )
            )
        bounded_seconds = min(max(1, int(lease_seconds)), max(1, int(worker.max_lease_seconds)))
        wake = self.kernel_store.lease_next_wake(
            lease_owner=worker_id,
            lease_seconds=bounded_seconds,
            allowed_sources=worker.allowed_sources,
            now=observed_at,
        )
        if wake is None:
            return self._append_lease(
                KernelExternalWorkerLease(
                    status="idle",
                    worker_id=worker_id,
                    reason="no_eligible_queued_wake",
                    created_at=observed_at,
                )
            )
        return self._append_lease(
            KernelExternalWorkerLease(
                status="leased",
                worker_id=worker_id,
                wake_id=wake.wake_id,
                run_id=wake.run_id,
                lease_expires_at=wake.lease_expires_at,
                reason="external_worker_wake_leased",
                wake_record=wake,
                created_at=observed_at,
            )
        )

    def complete_worker_wake(
        self,
        worker_id: str,
        wake_id: str,
        *,
        status: KernelRunStatus,
        summary: str = "",
        result_ref: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> KernelExternalWorkerResult:
        observed_at = now or utc_now()
        wake = self.kernel_store.latest_wake_records().get(wake_id)
        if wake is None:
            raise ValueError(f"wake is not known: {wake_id}")
        if wake.status != "leased":
            raise ValueError(f"wake is not leased: {wake_id}")
        if wake.lease_owner != worker_id:
            raise PermissionError(f"wake is leased by {wake.lease_owner}, not {worker_id}")
        result = _append_hashed(
            self.result_path,
            KernelExternalWorkerResult(
                worker_id=worker_id,
                wake_id=wake_id,
                run_id=wake.run_id,
                status=status,
                summary=summary,
                result_ref=dict(result_ref or {}),
                completed_at=observed_at,
            ),
            KernelExternalWorkerResult,
        )
        self.kernel_store.complete_external_wake(
            wake,
            status=status,
            result_ref={
                "kind": "external_worker_result",
                "worker_id": worker_id,
                "wake_id": wake_id,
                "run_id": wake.run_id,
                "worker_result_hash": result.record_hash,
                "path": str(self.result_path),
                "payload_ref": dict(result.result_ref),
            },
            now=observed_at,
        )
        return result

    def recover_stale_worker_leases(
        self,
        *,
        stale_after_seconds: int = 120,
        offline_after_seconds: int = 3600,
        now: str | None = None,
    ) -> KernelExternalWorkerRecovery:
        observed_at = now or utc_now()
        states = self.worker_states(
            stale_after_seconds=stale_after_seconds,
            offline_after_seconds=offline_after_seconds,
            now=observed_at,
        )
        stale_worker_ids = [state.worker_id for state in states if state.status in {"stale", "offline"}]
        recovered = self.kernel_store.recover_expired_wakes(lease_owners=stale_worker_ids, now=observed_at)
        recovery = KernelExternalWorkerRecovery(
            observed_at=observed_at,
            stale_worker_ids=stale_worker_ids,
            recovered_wake_ids=[record.wake_id for record in recovered],
        )
        return _append_hashed(self.recovery_path, recovery, KernelExternalWorkerRecovery)

    def verify_worker_ledgers(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        for path in [
            self.registry_path,
            self.heartbeat_path,
            self.lease_path,
            self.result_path,
            self.recovery_path,
        ]:
            if not path.exists():
                continue
            ok, path_errors = _verify_hash_ledger(path)
            if not ok:
                errors.extend(f"{path.name}: {error}" for error in path_errors)
        return (len(errors) == 0, errors)

    def _state_for_worker(
        self,
        worker_id: str,
        *,
        heartbeat_max_age_seconds: int,
        now: str,
    ) -> KernelExternalWorkerState | None:
        for state in self.worker_states(
            stale_after_seconds=heartbeat_max_age_seconds,
            offline_after_seconds=heartbeat_max_age_seconds,
            now=now,
        ):
            if state.worker_id == worker_id:
                return state
        return None

    def _append_lease(self, lease: KernelExternalWorkerLease) -> KernelExternalWorkerLease:
        return _append_hashed(self.lease_path, lease, KernelExternalWorkerLease)


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _append_hashed(path: Path, model: BaseModel, model_type: type[Any]) -> Any:
    row = model.model_dump(mode="json")
    rows = _jsonl_rows(path)
    row["previous_record_hash"] = str(rows[-1].get("record_hash") or "") if rows else ""
    row["record_hash"] = ""
    row["record_hash"] = stable_payload_hash(row)
    _append_jsonl(path, row)
    return model_type.model_validate(row)


def _verify_hash_ledger(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    previous_hash = ""
    for index, row in enumerate(_jsonl_rows(path), start=1):
        if str(row.get("previous_record_hash") or "") != previous_hash:
            errors.append(f"line {index}: previous_record_hash mismatch")
        observed_hash = str(row.get("record_hash") or "")
        material = dict(row)
        material["record_hash"] = ""
        if observed_hash != stable_payload_hash(material):
            errors.append(f"line {index}: record_hash mismatch")
        previous_hash = observed_hash
    return (len(errors) == 0, errors)


def _parse_utc(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _required(value: str, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    return cleaned


def _sorted_unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _record_ref(path: Path, record_hash: str) -> dict[str, Any]:
    if not record_hash:
        return {}
    return {"kind": "kernel_external_worker_receipt", "path": str(path), "record_hash": record_hash}


__all__ = [
    "KernelExternalWorkerHeartbeat",
    "KernelExternalWorkerLease",
    "KernelExternalWorkerRecord",
    "KernelExternalWorkerRecovery",
    "KernelExternalWorkerResult",
    "KernelExternalWorkerState",
    "KernelExternalWorkerStore",
]
