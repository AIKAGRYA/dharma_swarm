"""Crash-resume projection for LivingAgentKernel stores.

This module reconstructs restart state from existing receipt ledgers. Snapshot
is read-only. Recovery is explicit and limited to already-expired wake leases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import DEFAULT_KERNEL_RUN_DIR, KernelRunStore
from dharma_swarm.operator_core.living_agent_kernel_activation import (
    KernelActivationStore,
    launch_artifact_status,
)
from dharma_swarm.operator_core.living_agent_kernel_supervisor import supervisor_status
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore
from dharma_swarm.operator_core.runtime_truth import utc_now

KernelCrashResumeStatus = Literal["ready", "needs_recovery", "blocked"]
KernelCrashRecoveryStatus = Literal["completed", "blocked"]


class KernelLedgerIntegrityRef(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_ledger_integrity_ref.v1"
    name: str
    path: str
    present: bool = False
    ok: bool = True
    errors: list[str] = Field(default_factory=list)


class KernelCrashResumeSnapshot(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_crash_resume_snapshot.v1"
    status: KernelCrashResumeStatus
    store_dir: str
    observed_at: str = Field(default_factory=utc_now)
    integrity_ok: bool = True
    integrity_refs: list[KernelLedgerIntegrityRef] = Field(default_factory=list)
    control_snapshot: dict[str, Any] = Field(default_factory=dict)
    supervisor_ref: dict[str, Any] = Field(default_factory=dict)
    worker_states: list[dict[str, Any]] = Field(default_factory=list)
    activation_refs: list[dict[str, Any]] = Field(default_factory=list)
    launch_status_refs: list[dict[str, Any]] = Field(default_factory=list)
    worker_result_refs: list[dict[str, Any]] = Field(default_factory=list)
    expired_worker_lease_wake_ids: list[str] = Field(default_factory=list)
    expired_kernel_lease_wake_ids: list[str] = Field(default_factory=list)
    queued_wake_ids: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    message: str = ""


class KernelCrashRecoveryRun(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_crash_recovery_run.v1"
    status: KernelCrashRecoveryStatus
    store_dir: str
    observed_at: str = Field(default_factory=utc_now)
    before: KernelCrashResumeSnapshot
    after: KernelCrashResumeSnapshot | None = None
    worker_recovery_ref: dict[str, Any] = Field(default_factory=dict)
    direct_recovered_wake_ids: list[str] = Field(default_factory=list)
    message: str = ""


def build_kernel_crash_resume_snapshot(
    *,
    store_dir: Path | str | None = None,
    daemon_id: str = "living-agent-kernel",
    now: str | None = None,
    latest_limit: int = 20,
    stale_after_seconds: int = 120,
    offline_after_seconds: int = 3600,
) -> KernelCrashResumeSnapshot:
    store = KernelRunStore(store_dir or DEFAULT_KERNEL_RUN_DIR)
    workers = KernelExternalWorkerStore(store.base_dir)
    activations = KernelActivationStore(store.base_dir)
    observed_at = now or utc_now()

    control = store.control_snapshot(now=observed_at, latest_limit=latest_limit)
    worker_states = workers.worker_states(
        stale_after_seconds=stale_after_seconds,
        offline_after_seconds=offline_after_seconds,
        now=observed_at,
    )
    latest_wakes = store.latest_wake_records()
    stale_or_offline_workers = {state.worker_id for state in worker_states if state.status in {"stale", "offline"}}
    registered_workers = {worker.worker_id for worker in workers.workers()}
    expired_worker_wakes: list[str] = []
    expired_kernel_wakes: list[str] = []
    for wake_id in control.expired_lease_wake_ids:
        record = latest_wakes.get(wake_id)
        if record is None:
            continue
        if record.lease_owner in stale_or_offline_workers:
            expired_worker_wakes.append(wake_id)
        elif record.lease_owner not in registered_workers:
            expired_kernel_wakes.append(wake_id)

    integrity_refs = _integrity_refs(store, workers, activations)
    integrity_ok = all(ref.ok for ref in integrity_refs)
    activation_refs = _activation_refs(activations, limit=latest_limit)
    launch_status_refs = _launch_status_refs(activations, observed_at=observed_at, limit=latest_limit)
    supervisor = supervisor_status(store_dir=store.base_dir, daemon_id=daemon_id, now=observed_at)
    next_actions = _next_actions(
        integrity_ok=integrity_ok,
        queued_wake_ids=control.queued_wake_ids,
        expired_worker_wake_ids=expired_worker_wakes,
        expired_kernel_wake_ids=expired_kernel_wakes,
        supervisor_status_value=supervisor.status,
    )
    if not integrity_ok:
        status: KernelCrashResumeStatus = "blocked"
        message = "Crash-resume is blocked until ledger integrity errors are resolved."
    elif expired_worker_wakes or expired_kernel_wakes:
        status = "needs_recovery"
        message = "Crash-resume found expired wake leases that can be recovered explicitly."
    else:
        status = "ready"
        message = "Crash-resume snapshot is ready for bounded daemon or worker continuation."

    return KernelCrashResumeSnapshot(
        status=status,
        store_dir=str(store.base_dir),
        observed_at=observed_at,
        integrity_ok=integrity_ok,
        integrity_refs=integrity_refs,
        control_snapshot=control.model_dump(mode="json"),
        supervisor_ref=supervisor.model_dump(mode="json"),
        worker_states=[state.model_dump(mode="json") for state in worker_states],
        activation_refs=activation_refs,
        launch_status_refs=launch_status_refs,
        worker_result_refs=_worker_result_refs(workers, limit=latest_limit),
        expired_worker_lease_wake_ids=sorted(expired_worker_wakes),
        expired_kernel_lease_wake_ids=sorted(expired_kernel_wakes),
        queued_wake_ids=list(control.queued_wake_ids),
        next_actions=next_actions,
        message=message,
    )


def recover_kernel_after_crash(
    *,
    store_dir: Path | str | None = None,
    daemon_id: str = "living-agent-kernel",
    now: str | None = None,
    latest_limit: int = 20,
    stale_after_seconds: int = 120,
    offline_after_seconds: int = 3600,
) -> KernelCrashRecoveryRun:
    observed_at = now or utc_now()
    before = build_kernel_crash_resume_snapshot(
        store_dir=store_dir,
        daemon_id=daemon_id,
        now=observed_at,
        latest_limit=latest_limit,
        stale_after_seconds=stale_after_seconds,
        offline_after_seconds=offline_after_seconds,
    )
    if not before.integrity_ok:
        return KernelCrashRecoveryRun(
            status="blocked",
            store_dir=before.store_dir,
            observed_at=observed_at,
            before=before,
            message="Recovery blocked because one or more ledgers failed integrity verification.",
        )

    workers = KernelExternalWorkerStore(before.store_dir)
    store = KernelRunStore(before.store_dir)
    worker_recovery = workers.recover_stale_worker_leases(
        stale_after_seconds=stale_after_seconds,
        offline_after_seconds=offline_after_seconds,
        now=observed_at,
    )
    latest_after_worker_recovery = store.latest_wake_records()
    kernel_owners = sorted(
        {
            latest_after_worker_recovery[wake_id].lease_owner
            for wake_id in before.expired_kernel_lease_wake_ids
            if wake_id in latest_after_worker_recovery
            and latest_after_worker_recovery[wake_id].status == "leased"
            and latest_after_worker_recovery[wake_id].lease_owner
        }
    )
    direct_recovered = store.recover_expired_wakes(lease_owners=kernel_owners, now=observed_at) if kernel_owners else []
    after = build_kernel_crash_resume_snapshot(
        store_dir=before.store_dir,
        daemon_id=daemon_id,
        now=observed_at,
        latest_limit=latest_limit,
        stale_after_seconds=stale_after_seconds,
        offline_after_seconds=offline_after_seconds,
    )
    return KernelCrashRecoveryRun(
        status="completed",
        store_dir=before.store_dir,
        observed_at=observed_at,
        before=before,
        after=after,
        worker_recovery_ref={
            "kind": "kernel_external_worker_recovery",
            "path": str(workers.recovery_path),
            "record_hash": worker_recovery.record_hash,
            "recovered_wake_ids": list(worker_recovery.recovered_wake_ids),
        },
        direct_recovered_wake_ids=[record.wake_id for record in direct_recovered],
        message="Crash recovery completed bounded expired-lease recovery.",
    )


def _integrity_refs(
    store: KernelRunStore,
    workers: KernelExternalWorkerStore,
    activations: KernelActivationStore,
) -> list[KernelLedgerIntegrityRef]:
    return [
        _integrity_ref("wake_ledger", store.wake_ledger_path, store.verify_wake_ledger),
        _integrity_ref("proof_ledger", store.proof_ledger_path, store.verify_proof_ledger),
        _integrity_ref("daemon_control", store.daemon_control_path, store.verify_daemon_control_ledger),
        _integrity_ref("daemon_cycles", store.daemon_cycles_path, store.verify_daemon_cycle_ledger),
        _integrity_ref("worker_ledgers", workers.base_dir, workers.verify_worker_ledgers),
        _integrity_ref("activation_receipts", activations.activation_path, activations.verify_activation_ledger),
    ]


def _integrity_ref(name: str, path: Path, verifier: Any) -> KernelLedgerIntegrityRef:
    present = path.exists()
    if not present:
        return KernelLedgerIntegrityRef(name=name, path=str(path), present=False, ok=True)
    ok, errors = verifier()
    return KernelLedgerIntegrityRef(name=name, path=str(path), present=True, ok=ok, errors=list(errors))


def _activation_refs(store: KernelActivationStore, *, limit: int) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for receipt in store.activations()[-max(1, int(limit)) :]:
        refs.append(
            {
                "target_kind": receipt.target_kind,
                "status": receipt.status,
                "record_hash": receipt.record_hash,
                "command_hash": receipt.command_hash,
                "created_at": receipt.created_at,
                "install_ref": dict(receipt.install_ref),
                "process_ref": dict(receipt.process_ref),
            }
        )
    return refs


def _launch_status_refs(store: KernelActivationStore, *, observed_at: str, limit: int) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    installs = [
        receipt
        for receipt in store.activations()
        if receipt.target_kind == "launch_artifact" and receipt.status == "installed" and receipt.record_hash
    ]
    for receipt in installs[-max(1, int(limit)) :]:
        status = launch_artifact_status(
            store_dir=store.base_dir,
            install_receipt_hash=receipt.record_hash,
            now=observed_at,
        )
        refs.append(status.model_dump(mode="json"))
    return refs


def _worker_result_refs(store: KernelExternalWorkerStore, *, limit: int) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for result in store.results()[-max(1, int(limit)) :]:
        refs.append(
            {
                "worker_id": result.worker_id,
                "wake_id": result.wake_id,
                "run_id": result.run_id,
                "status": result.status,
                "record_hash": result.record_hash,
                "completed_at": result.completed_at,
                "result_ref": dict(result.result_ref),
            }
        )
    return refs


def _next_actions(
    *,
    integrity_ok: bool,
    queued_wake_ids: list[str],
    expired_worker_wake_ids: list[str],
    expired_kernel_wake_ids: list[str],
    supervisor_status_value: str,
) -> list[str]:
    if not integrity_ok:
        return ["repair_ledger_integrity_before_resume"]
    actions: list[str] = []
    if expired_worker_wake_ids:
        actions.append("recover_stale_worker_leases")
    if expired_kernel_wake_ids:
        actions.append("recover_expired_kernel_leases")
    if queued_wake_ids or expired_worker_wake_ids or expired_kernel_wake_ids:
        actions.append("run_bounded_daemon_cycle_or_worker_execute")
    if supervisor_status_value in {"never_ran", "stale"}:
        actions.append("review_supervisor_launch_or_restart_status")
    return actions or ["continue_monitoring_receipts"]


__all__ = [
    "KernelCrashRecoveryRun",
    "KernelCrashRecoveryStatus",
    "KernelCrashResumeSnapshot",
    "KernelCrashResumeStatus",
    "KernelLedgerIntegrityRef",
    "build_kernel_crash_resume_snapshot",
    "recover_kernel_after_crash",
]
