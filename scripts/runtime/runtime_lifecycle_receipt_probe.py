#!/usr/bin/env python3
"""Write one bounded RuntimeLifecycle receipt proof and verify it by run_id."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.models import Task, TaskDispatch, TopologyType  # noqa: E402
from dharma_swarm.orchestrator import Orchestrator  # noqa: E402
from dharma_swarm.runtime_lifecycle import RuntimeLifecycle  # noqa: E402
from dharma_swarm.runtime_state import (  # noqa: E402
    ArtifactRecord,
    DelegationRun,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.session_ledger import SessionLedger  # noqa: E402
from dharma_swarm.spine.identity import ExecutionIdentity  # noqa: E402


DEFAULT_DB = Path(os.environ.get("DHARMA_RUNTIME_DB", "/Users/dhyana/.dharma/state/runtime.db"))
LIVE_RUNTIME_DB = Path("/Users/dhyana/.dharma/state/runtime.db")
DEFAULT_LEDGER_DIR = Path("/private/tmp/dharma_runtime_lifecycle_probe_ledgers")
DEFAULT_ARTIFACT_DIR = Path("/private/tmp/dharma_runtime_lifecycle_probe_artifacts")
DEFAULT_MISSION_ID = "runtime-spine-hardening-2026-06-14"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%SZ")


def _route_metadata(
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    no_provider_execution: bool = False,
    no_provider_model_reason: str = "",
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if no_provider_execution:
        metadata.update(
            provider_execution=False,
            provider_model_applicability="not_applicable",
            provider_model_truth_source="runtime_control.no_provider_execution",
            no_provider_model_reason=(
                str(no_provider_model_reason or "").strip()
                or "runtime_lifecycle_receipt_probe_no_provider_execution"
            ),
        )
        return metadata
    selected_provider_text = str(selected_provider or "").strip()
    selected_model_text = str(selected_model or "").strip()
    served_provider_text = str(actual_served_provider or "").strip()
    served_model_text = str(actual_served_model or "").strip()
    if served_provider_text:
        metadata["actual_served_provider"] = served_provider_text
        metadata["served_provider"] = served_provider_text
        metadata["provider_served"] = served_provider_text
        metadata["provider"] = served_provider_text
    if selected_provider_text:
        metadata["selected_provider"] = selected_provider_text
        metadata.setdefault("provider", selected_provider_text)
    if served_model_text:
        metadata["actual_served_model"] = served_model_text
        metadata["served_model"] = served_model_text
        metadata["model_served"] = served_model_text
        metadata["model"] = served_model_text
    if selected_model_text:
        metadata["selected_model"] = selected_model_text
        metadata["selected_model_hint"] = selected_model_text
        metadata.setdefault("model", selected_model_text)
    source = str(provider_model_truth_source or "").strip()
    if source:
        metadata["provider_model_truth_source"] = source
    elif selected_provider_text or selected_model_text:
        metadata["provider_model_truth_source"] = (
            "runtime_lifecycle_receipt_probe.selected_metadata"
        )
    return metadata


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_coverage_report():
    path = REPO_ROOT / "scripts" / "governance" / "runtime_receipt_coverage_report.py"
    spec = importlib.util.spec_from_file_location("runtime_receipt_coverage_report", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def _write_probe_artifact(
    artifact_dir: Path,
    *,
    artifact_id: str,
    mission_id: str,
    run_id: str,
    task_id: str,
    trace_id: str,
    correlation_id: str,
    purpose: str,
) -> tuple[Path, Path, str]:
    now = _utc_now()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload_path = artifact_dir / f"{artifact_id}.json"
    manifest_path = artifact_dir / f"{artifact_id}.manifest.json"
    payload = {
        "artifact_id": artifact_id,
        "mission_id": mission_id,
        "run_id": run_id,
        "task_id": task_id,
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "written_at": now.isoformat(),
        "purpose": purpose,
    }
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checksum = _sha256(payload_path)
    manifest_path.write_text(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "checksum_sha256": checksum,
                "payload_path": str(payload_path),
                "schema": "runtime_lifecycle_receipt_probe.v1",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return payload_path, manifest_path, checksum


async def run_probe(
    db_path: Path,
    *,
    ledger_dir: Path = DEFAULT_LEDGER_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    mission_id: str = DEFAULT_MISSION_ID,
    run_id: str = "",
    task_id: str = "",
    agent_id: str = "runtime-spine-hardening-probe",
    claim_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    session_id: str = "",
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    no_provider_execution: bool = False,
    no_provider_model_reason: str = "",
    latest_limit: int = 50,
) -> dict[str, Any]:
    now = _utc_now()
    stamp = _stamp()
    clean_run_id = run_id or f"run_runtime_spine_probe_{stamp}_{uuid4().hex[:8]}"
    clean_task_id = task_id or f"task_runtime_spine_probe_{uuid4().hex[:8]}"
    clean_claim_id = claim_id or f"claim_{clean_run_id}"
    clean_trace_id = trace_id or f"trace_{clean_run_id}"
    clean_correlation_id = correlation_id or clean_trace_id
    clean_session_id = session_id or f"sess_runtime_spine_probe_{stamp}"
    idempotency_key = f"idem_{clean_run_id}"
    artifact_id = f"artifact_{clean_run_id}"
    route_metadata = _route_metadata(
        selected_provider,
        selected_model,
        actual_served_provider,
        actual_served_model,
        provider_model_truth_source,
        no_provider_execution=no_provider_execution,
        no_provider_model_reason=no_provider_model_reason,
    )

    payload_path, manifest_path, checksum = _write_probe_artifact(
        artifact_dir,
        artifact_id=artifact_id,
        mission_id=mission_id,
        run_id=clean_run_id,
        task_id=clean_task_id,
        trace_id=clean_trace_id,
        correlation_id=clean_correlation_id,
        purpose="runtime spine receipt coverage proof",
    )

    identity_metadata = {
        "task_id": clean_task_id,
        "trace_id": clean_trace_id,
        "correlation_id": clean_correlation_id,
        "run_id": clean_run_id,
        "runtime_run_id": clean_run_id,
        "claim_id": clean_claim_id,
        "idempotency_key": idempotency_key,
        "mission_id": mission_id,
        **route_metadata,
    }
    task = Task(
        id=clean_task_id,
        title="Runtime spine receipt coverage probe",
        description="Bounded local proof that RuntimeLifecycle emits receipt, idempotency, mission, and artifact joins.",
        metadata={
            **identity_metadata,
            "active_claim": {
                "claimed_at": now.isoformat(),
                "claim_expires_at_epoch": int(now.timestamp()) + 3600,
            },
            "requested_output": ["runtime_spine_probe_receipt"],
            "current_artifact_id": artifact_id,
        },
    )
    dispatch = TaskDispatch(
        task_id=clean_task_id,
        agent_id=agent_id,
        topology=TopologyType.PIPELINE,
        timeout_seconds=60.0,
        metadata={
            **identity_metadata,
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
        },
    )

    ledger = SessionLedger(
        base_dir=ledger_dir,
        session_id=clean_session_id,
        runtime_db_path=db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(dispatch, task=task, status="running", require_identity=True)
    await lifecycle.record_artifact(
        task=task,
        artifact_id=artifact_id,
        artifact_kind="runtime_spine_probe_receipt",
        payload_path=payload_path,
        manifest_path=manifest_path,
        checksum=checksum,
        run_id=clean_run_id,
        metadata={
            "mission_id": mission_id,
            "probe": "runtime_lifecycle_receipt_probe",
        },
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result=f"runtime lifecycle receipt probe complete for {clean_run_id}",
        require_identity=True,
    )
    await lifecycle.record_task_claim(dispatch, task=task, status="completed", require_identity=True)

    coverage = _load_coverage_report().build_report(
        db_path,
        latest_limit=latest_limit,
        run_id=clean_run_id,
    )
    return {
        "probe": "runtime_lifecycle_receipt_probe",
        "db_path": str(db_path.expanduser()),
        "run_id": clean_run_id,
        "task_id": clean_task_id,
        "claim_id": clean_claim_id,
        "agent_id": agent_id,
        "session_id": clean_session_id,
        "mission_id": mission_id,
        "artifact_id": artifact_id,
        "selected_provider": route_metadata.get("selected_provider", ""),
        "selected_model": route_metadata.get("selected_model", ""),
        "actual_served_provider": route_metadata.get("actual_served_provider", ""),
        "actual_served_model": route_metadata.get("actual_served_model", ""),
        "provider_model_truth_source": route_metadata.get("provider_model_truth_source", ""),
        "provider_execution": route_metadata.get("provider_execution", ""),
        "no_provider_model_reason": route_metadata.get("no_provider_model_reason", ""),
        "payload_path": str(payload_path),
        "manifest_path": str(manifest_path),
        "checksum_sha256": checksum,
        "coverage": coverage,
    }


async def run_sync_store_probe(
    db_path: Path,
    *,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    mission_id: str = DEFAULT_MISSION_ID,
    run_id: str = "",
    task_id: str = "",
    agent_id: str = "runtime-spine-hardening-probe",
    claim_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    session_id: str = "",
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    topology: str = "pipeline",
    latest_limit: int = 50,
) -> dict[str, Any]:
    now = _utc_now()
    stamp = _stamp()
    clean_run_id = run_id or f"run_runtime_state_sync_probe_{stamp}_{uuid4().hex[:8]}"
    clean_task_id = task_id or f"task_runtime_state_sync_probe_{uuid4().hex[:8]}"
    clean_claim_id = claim_id or f"claim_{clean_run_id}"
    clean_trace_id = trace_id or f"trace_{clean_run_id}"
    clean_correlation_id = correlation_id or clean_trace_id
    clean_session_id = session_id or f"sess_runtime_state_sync_probe_{stamp}"
    artifact_id = f"artifact_{clean_run_id}"
    route_metadata = _route_metadata(
        selected_provider,
        selected_model,
        actual_served_provider,
        actual_served_model,
        provider_model_truth_source,
    )
    if not route_metadata:
        route_metadata = {
            "provider_execution": False,
            "provider_model_applicability": "not_applicable",
            "provider_model_truth_source": "runtime_control.no_provider_execution",
            "no_provider_model_reason": (
                "runtime_state_sync_receipt_probe_no_provider_execution"
            ),
        }
    identity = ExecutionIdentity.new(
        task_id=clean_task_id,
        run_id=clean_run_id,
        claim_id=clean_claim_id,
        trace_id=clean_trace_id,
        correlation_id=clean_correlation_id,
        idempotency_key=f"idem_{clean_run_id}",
        agent_id=agent_id,
        session_id=clean_session_id,
        artifact_id=artifact_id,
        metadata={"mission_id": mission_id, **route_metadata},
    )
    metadata = {
        **identity.to_metadata(),
        "mission_id": mission_id,
        "probe": "runtime_state_sync_receipt_probe",
        **route_metadata,
    }
    payload_path, manifest_path, checksum = _write_probe_artifact(
        artifact_dir,
        artifact_id=artifact_id,
        mission_id=mission_id,
        run_id=clean_run_id,
        task_id=clean_task_id,
        trace_id=clean_trace_id,
        correlation_id=clean_correlation_id,
        purpose="runtime state sync receipt coverage proof",
    )
    store = RuntimeStateStore(db_path)
    store.init_db_sync()
    store.record_execution_identity_sync(identity, source="runtime_state_sync_receipt_probe", metadata=metadata)
    store.create_task_claim_sync(
        TaskClaim(
            claim_id=clean_claim_id,
            task_id=clean_task_id,
            agent_id=agent_id,
            status="claimed",
            session_id=clean_session_id,
            claimed_at=now,
            acked_at=now,
            heartbeat_at=now,
            metadata=metadata,
        )
    )
    store.create_delegation_run_sync(
        DelegationRun(
            run_id=clean_run_id,
            task_id=clean_task_id,
            assigned_to=agent_id,
            status="running",
            session_id=clean_session_id,
            claim_id=clean_claim_id,
            assigned_by="runtime-state-sync-probe",
            requested_output=["runtime_state_sync_receipt"],
            current_artifact_id=artifact_id,
            started_at=now,
            metadata=metadata,
        )
    )
    await store.record_artifact(
        ArtifactRecord(
            artifact_id=artifact_id,
            artifact_kind="runtime_state_sync_receipt",
            session_id=clean_session_id,
            task_id=clean_task_id,
            run_id=clean_run_id,
            trace_id=clean_trace_id,
            manifest_path=str(manifest_path),
            payload_path=str(payload_path),
            checksum=checksum,
            promotion_state="ephemeral",
            metadata=metadata,
        )
    )
    store.create_delegation_run_sync(
        DelegationRun(
            run_id=clean_run_id,
            task_id=clean_task_id,
            assigned_to=agent_id,
            status="completed",
            session_id=clean_session_id,
            claim_id=clean_claim_id,
            assigned_by="runtime-state-sync-probe",
            requested_output=["runtime_state_sync_receipt"],
            current_artifact_id=artifact_id,
            started_at=now,
            completed_at=_utc_now(),
            metadata=metadata,
        )
    )
    store.create_task_claim_sync(
        TaskClaim(
            claim_id=clean_claim_id,
            task_id=clean_task_id,
            agent_id=agent_id,
            status="completed",
            session_id=clean_session_id,
            claimed_at=now,
            acked_at=now,
            heartbeat_at=_utc_now(),
            metadata=metadata,
        )
    )
    coverage = _load_coverage_report().build_report(
        db_path,
        latest_limit=latest_limit,
        run_id=clean_run_id,
    )
    return {
        "probe": "runtime_state_sync_receipt_probe",
        "db_path": str(db_path.expanduser()),
        "run_id": clean_run_id,
        "task_id": clean_task_id,
        "claim_id": clean_claim_id,
        "agent_id": agent_id,
        "session_id": clean_session_id,
        "mission_id": mission_id,
        "artifact_id": artifact_id,
        "selected_provider": route_metadata.get("selected_provider", ""),
        "selected_model": route_metadata.get("selected_model", ""),
        "actual_served_provider": route_metadata.get("actual_served_provider", ""),
        "actual_served_model": route_metadata.get("actual_served_model", ""),
        "provider_model_truth_source": route_metadata.get("provider_model_truth_source", ""),
        "payload_path": str(payload_path),
        "manifest_path": str(manifest_path),
        "checksum_sha256": checksum,
        "coverage": coverage,
    }


class _ProbeTaskBoard:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    async def update_task(self, task_id: str, **fields: Any) -> None:
        self.updates.append({"task_id": task_id, **fields})


class _ProbeAgentPool:
    def __init__(self) -> None:
        self.released: list[str] = []

    async def release(self, agent_id: str) -> None:
        self.released.append(agent_id)


class _ProbeRunner:
    def __init__(
        self,
        *,
        actual_served_provider: str = "",
        actual_served_model: str = "",
        provider_model_truth_source: str = "",
        no_provider_execution: bool = False,
        no_provider_model_reason: str = "",
        runner_error: str = "",
    ) -> None:
        self.actual_served_provider = str(actual_served_provider or "").strip()
        self.actual_served_model = str(actual_served_model or "").strip()
        if no_provider_execution:
            self.provider_execution = False
            self.provider_model_applicability = "not_applicable"
            self.provider_model_truth_source = str(
                provider_model_truth_source or "runtime_control.no_provider_execution"
            ).strip()
            self.no_provider_model_reason = str(
                no_provider_model_reason
                or "runtime_lifecycle_receipt_probe_no_provider_execution"
            ).strip()
        else:
            self.provider_model_truth_source = str(
                provider_model_truth_source or "runtime_lifecycle_receipt_probe.runner_actual_served"
            ).strip()
        self.runner_error = str(runner_error or "").strip()
        self.served_provider = self.actual_served_provider
        self.served_model = self.actual_served_model
        self.provider_served = self.actual_served_provider
        self.model_served = self.actual_served_model

    async def run_task(self, task: Task) -> str:
        if self.runner_error:
            raise RuntimeError(self.runner_error)
        return f"orchestrator spine dispatch probe complete for {task.id}"


async def run_orchestrator_spine_probe(
    db_path: Path,
    *,
    ledger_dir: Path = DEFAULT_LEDGER_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    mission_id: str = DEFAULT_MISSION_ID,
    run_id: str = "",
    task_id: str = "",
    agent_id: str = "runtime-spine-hardening-probe",
    claim_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    session_id: str = "",
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    no_provider_execution: bool = False,
    no_provider_model_reason: str = "runtime_lifecycle_receipt_probe_no_provider_execution",
    topology: str = "pipeline",
    runner_error: str = "",
    preseed_artifact: bool = True,
    latest_limit: int = 50,
) -> dict[str, Any]:
    now = _utc_now()
    stamp = _stamp()
    clean_run_id = run_id or f"run_orchestrator_spine_probe_{stamp}_{uuid4().hex[:8]}"
    clean_task_id = task_id or f"task_orchestrator_spine_probe_{uuid4().hex[:8]}"
    clean_claim_id = claim_id or f"claim_{clean_run_id}"
    clean_trace_id = trace_id or f"trace_{clean_run_id}"
    clean_correlation_id = correlation_id or clean_trace_id
    clean_session_id = session_id or f"sess_orchestrator_spine_probe_{stamp}"
    idempotency_key = f"idem_{clean_run_id}"
    artifact_id = f"artifact_{clean_run_id}"
    topology_text = str(topology or "pipeline").strip().lower().replace("-", "_")
    probe_topology = (
        TopologyType.FAN_OUT if topology_text == "fan_out" else TopologyType.PIPELINE
    )
    route_metadata = _route_metadata(
        selected_provider,
        selected_model,
        "",
        "",
        "",
        no_provider_execution=no_provider_execution,
        no_provider_model_reason=no_provider_model_reason,
    )
    runner = _ProbeRunner(
        actual_served_provider=actual_served_provider,
        actual_served_model=actual_served_model,
        provider_model_truth_source=provider_model_truth_source,
        no_provider_execution=no_provider_execution,
        no_provider_model_reason=no_provider_model_reason,
        runner_error=runner_error,
    )
    probe_max_retries = 1 if runner.runner_error else 0

    payload_path, manifest_path, checksum = _write_probe_artifact(
        artifact_dir,
        artifact_id=artifact_id,
        mission_id=mission_id,
        run_id=clean_run_id,
        task_id=clean_task_id,
        trace_id=clean_trace_id,
        correlation_id=clean_correlation_id,
        purpose="orchestrator spine dispatch receipt proof",
    )

    identity_metadata = {
        "task_id": clean_task_id,
        "trace_id": clean_trace_id,
        "correlation_id": clean_correlation_id,
        "run_id": clean_run_id,
        "runtime_run_id": clean_run_id,
        "claim_id": clean_claim_id,
        "idempotency_key": idempotency_key,
        "mission_id": mission_id,
        **route_metadata,
    }
    task = Task(
        id=clean_task_id,
        title=f"Orchestrator spine {probe_topology.value} dispatch coverage probe",
        description=(
            "Bounded local proof that orchestrator._execute_task routes through "
            "invoke_agent when DHARMA_SPINE_DISPATCH=1."
        ),
        metadata={
            **identity_metadata,
            "active_claim": {
                "claimed_at": now.isoformat(),
                "claim_expires_at_epoch": int(now.timestamp()) + 3600,
            },
            "requested_output": ["orchestrator_spine_dispatch_probe"],
            "retry_count": 0,
            "max_retries": probe_max_retries,
            **({"current_artifact_id": artifact_id} if preseed_artifact else {}),
        },
    )
    dispatch = TaskDispatch(
        task_id=clean_task_id,
        agent_id=agent_id,
        topology=probe_topology,
        timeout_seconds=20.0,
        metadata={
            **identity_metadata,
            "retry_count": 0,
            "max_retries": probe_max_retries,
            "claim_timeout_seconds": 300,
        },
    )

    board = _ProbeTaskBoard()
    pool = _ProbeAgentPool()
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=ledger_dir,
        runtime_db_path=db_path,
        session_id=clean_session_id,
        shared_dir=artifact_dir / "shared",
        stigmergy_dir=artifact_dir / "stigmergy",
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity(
        dispatch,
        task=task,
        require=True,
    )
    if preseed_artifact:
        await orchestrator._runtime_lifecycle.record_artifact(
            task=task,
            artifact_id=artifact_id,
            artifact_kind="orchestrator_spine_dispatch_probe",
            payload_path=payload_path,
            manifest_path=manifest_path,
            checksum=checksum,
            run_id=clean_run_id,
            metadata={
                "mission_id": mission_id,
                "probe": "orchestrator_spine_dispatch_probe",
            },
            require_identity=True,
        )

    previous = os.environ.get("DHARMA_SPINE_DISPATCH")
    os.environ["DHARMA_SPINE_DISPATCH"] = "1"
    try:
        await orchestrator._execute_task(runner, task, dispatch)
    finally:
        if previous is None:
            os.environ.pop("DHARMA_SPINE_DISPATCH", None)
        else:
            os.environ["DHARMA_SPINE_DISPATCH"] = previous

    coverage = _load_coverage_report().build_report(
        db_path,
        latest_limit=latest_limit,
        run_id=clean_run_id,
    )
    return {
        "probe": "orchestrator_spine_dispatch_probe",
        "db_path": str(db_path.expanduser()),
        "run_id": clean_run_id,
        "task_id": clean_task_id,
        "claim_id": clean_claim_id,
        "agent_id": agent_id,
        "session_id": clean_session_id,
        "mission_id": mission_id,
        "artifact_id": artifact_id,
        "task_result_artifact_id": f"artifact_task_result_{clean_task_id}",
        "preseed_artifact": preseed_artifact,
        "topology": probe_topology.value,
        "selected_provider": route_metadata.get("selected_provider", ""),
        "selected_model": route_metadata.get("selected_model", ""),
        "actual_served_provider": runner.actual_served_provider,
        "actual_served_model": runner.actual_served_model,
        "runner_error": runner.runner_error,
        "provider_model_truth_source": (
            runner.provider_model_truth_source
            if (
                (runner.actual_served_provider and runner.actual_served_model)
                or no_provider_execution
            )
            else route_metadata.get("provider_model_truth_source", "")
        ),
        "provider_execution": route_metadata.get("provider_execution", ""),
        "no_provider_model_reason": route_metadata.get("no_provider_model_reason", ""),
        "payload_path": str(payload_path),
        "manifest_path": str(manifest_path),
        "checksum_sha256": checksum,
        "board_updates": len(board.updates),
        "pool_releases": len(pool.released),
        "evidence_receipt_id": str(orchestrator._last_evidence_receipt.receipt_id),
        "coverage": coverage,
    }


async def run_runtime_lifecycle_dropoff_probe(
    db_path: Path,
    *,
    ledger_dir: Path = DEFAULT_LEDGER_DIR,
    mission_id: str = DEFAULT_MISSION_ID,
    run_id: str = "",
    task_id: str = "",
    agent_id: str = "runtime-spine-hardening-probe",
    claim_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    session_id: str = "",
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    no_provider_execution: bool = False,
    no_provider_model_reason: str = "runtime_lifecycle_receipt_probe_no_provider_execution",
    latest_limit: int = 50,
) -> dict[str, Any]:
    """Exercise the runtime-lifecycle dispatch-dropoff path with no artifact."""
    now = _utc_now()
    stamp = _stamp()
    clean_run_id = run_id or f"run_runtime_lifecycle_dropoff_probe_{stamp}_{uuid4().hex[:8]}"
    clean_task_id = task_id or f"task_runtime_lifecycle_dropoff_probe_{uuid4().hex[:8]}"
    clean_claim_id = claim_id or f"claim_{clean_run_id}"
    clean_trace_id = trace_id or f"trace_{clean_run_id}"
    clean_correlation_id = correlation_id or clean_trace_id
    clean_session_id = session_id or f"sess_runtime_lifecycle_dropoff_probe_{stamp}"
    idempotency_key = f"idem_{clean_run_id}"
    route_metadata = _route_metadata(
        selected_provider,
        selected_model,
        actual_served_provider,
        actual_served_model,
        provider_model_truth_source,
    )

    identity_metadata = {
        "task_id": clean_task_id,
        "trace_id": clean_trace_id,
        "correlation_id": clean_correlation_id,
        "run_id": clean_run_id,
        "runtime_run_id": clean_run_id,
        "claim_id": clean_claim_id,
        "idempotency_key": idempotency_key,
        "mission_id": mission_id,
        **route_metadata,
    }
    task = Task(
        id=clean_task_id,
        title="Runtime lifecycle dispatch-dropoff coverage probe",
        description=(
            "Bounded local proof that dispatch-dropoff receipts carry "
            "idempotency and explicit no-artifact truth."
        ),
        metadata={
            **identity_metadata,
            "active_claim": {
                "claimed_at": now.isoformat(),
                "claim_expires_at_epoch": int(now.timestamp()) + 3600,
            },
            "requested_output": [],
        },
    )
    dispatch = TaskDispatch(
        task_id=clean_task_id,
        agent_id=agent_id,
        topology=TopologyType.FAN_OUT,
        timeout_seconds=60.0,
        metadata={
            **identity_metadata,
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
        },
    )
    ledger = SessionLedger(
        base_dir=ledger_dir,
        session_id=clean_session_id,
        runtime_db_path=db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="dispatch_dropoff",
        error="Dispatch accepted but worker unavailable (probe)",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="dispatch_dropoff",
        error="Dispatch accepted but worker unavailable (probe)",
        require_identity=True,
    )

    coverage = _load_coverage_report().build_report(
        db_path,
        latest_limit=latest_limit,
        run_id=clean_run_id,
    )
    return {
        "probe": "runtime_lifecycle_dropoff_probe",
        "db_path": str(db_path.expanduser()),
        "run_id": clean_run_id,
        "task_id": clean_task_id,
        "claim_id": clean_claim_id,
        "agent_id": agent_id,
        "session_id": clean_session_id,
        "mission_id": mission_id,
        "artifact_id": "",
        "selected_provider": route_metadata.get("selected_provider", ""),
        "selected_model": route_metadata.get("selected_model", ""),
        "actual_served_provider": route_metadata.get("actual_served_provider", ""),
        "actual_served_model": route_metadata.get("actual_served_model", ""),
        "provider_model_truth_source": route_metadata.get("provider_model_truth_source", ""),
        "dropoff_failure_code": "dispatch_dropoff",
        "coverage": coverage,
    }


async def run_runtime_lifecycle_claim_timeout_probe(
    db_path: Path,
    *,
    ledger_dir: Path = DEFAULT_LEDGER_DIR,
    mission_id: str = DEFAULT_MISSION_ID,
    run_id: str = "",
    task_id: str = "",
    agent_id: str = "runtime-spine-hardening-probe",
    claim_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    session_id: str = "",
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    latest_limit: int = 50,
) -> dict[str, Any]:
    """Exercise the runtime-lifecycle claim-timeout path with no artifact."""
    now = _utc_now()
    stamp = _stamp()
    clean_run_id = run_id or f"run_runtime_lifecycle_claim_timeout_probe_{stamp}_{uuid4().hex[:8]}"
    clean_task_id = task_id or f"task_runtime_lifecycle_claim_timeout_probe_{uuid4().hex[:8]}"
    clean_claim_id = claim_id or f"claim_{clean_run_id}"
    clean_trace_id = trace_id or f"trace_{clean_run_id}"
    clean_correlation_id = correlation_id or clean_trace_id
    clean_session_id = session_id or f"sess_runtime_lifecycle_claim_timeout_probe_{stamp}"
    idempotency_key = f"idem_{clean_run_id}"
    route_metadata = _route_metadata(
        selected_provider,
        selected_model,
        actual_served_provider,
        actual_served_model,
        provider_model_truth_source,
    )

    identity_metadata = {
        "task_id": clean_task_id,
        "trace_id": clean_trace_id,
        "correlation_id": clean_correlation_id,
        "run_id": clean_run_id,
        "runtime_run_id": clean_run_id,
        "claim_id": clean_claim_id,
        "idempotency_key": idempotency_key,
        "mission_id": mission_id,
        **route_metadata,
    }
    task = Task(
        id=clean_task_id,
        title="Runtime lifecycle claim-timeout coverage probe",
        description=(
            "Bounded local proof that claim-timeout receipts carry "
            "idempotency and explicit no-provider truth."
        ),
        metadata={
            **identity_metadata,
            "active_claim": {
                "claimed_at": now.isoformat(),
                "claim_expires_at_epoch": int(now.timestamp()) + 1,
            },
            "requested_output": [],
        },
    )
    dispatch = TaskDispatch(
        task_id=clean_task_id,
        agent_id=agent_id,
        topology=TopologyType.FAN_OUT,
        timeout_seconds=60.0,
        metadata={
            **identity_metadata,
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 1,
        },
    )
    ledger = SessionLedger(
        base_dir=ledger_dir,
        session_id=clean_session_id,
        runtime_db_path=db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="claim_timeout",
        error="Task claim timed out before worker execution (probe)",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="claim_timeout",
        error="Task claim timed out before worker execution (probe)",
        require_identity=True,
    )

    coverage = _load_coverage_report().build_report(
        db_path,
        latest_limit=latest_limit,
        run_id=clean_run_id,
    )
    return {
        "probe": "runtime_lifecycle_claim_timeout_probe",
        "db_path": str(db_path.expanduser()),
        "run_id": clean_run_id,
        "task_id": clean_task_id,
        "claim_id": clean_claim_id,
        "agent_id": agent_id,
        "session_id": clean_session_id,
        "mission_id": mission_id,
        "artifact_id": "",
        "selected_provider": route_metadata.get("selected_provider", ""),
        "selected_model": route_metadata.get("selected_model", ""),
        "actual_served_provider": route_metadata.get("actual_served_provider", ""),
        "actual_served_model": route_metadata.get("actual_served_model", ""),
        "provider_model_truth_source": route_metadata.get("provider_model_truth_source", ""),
        "claim_timeout_failure_code": "claim_timeout",
        "coverage": coverage,
    }


async def run_runtime_lifecycle_long_timeout_probe(
    db_path: Path,
    *,
    ledger_dir: Path = DEFAULT_LEDGER_DIR,
    mission_id: str = DEFAULT_MISSION_ID,
    run_id: str = "",
    task_id: str = "",
    agent_id: str = "runtime-spine-hardening-probe",
    claim_id: str = "",
    trace_id: str = "",
    correlation_id: str = "",
    session_id: str = "",
    selected_provider: str = "",
    selected_model: str = "",
    actual_served_provider: str = "",
    actual_served_model: str = "",
    provider_model_truth_source: str = "",
    latest_limit: int = 50,
) -> dict[str, Any]:
    """Exercise the runtime-lifecycle long-timeout path with no artifact."""
    now = _utc_now()
    stamp = _stamp()
    clean_run_id = run_id or f"run_runtime_lifecycle_long_timeout_probe_{stamp}_{uuid4().hex[:8]}"
    clean_task_id = task_id or f"task_runtime_lifecycle_long_timeout_probe_{uuid4().hex[:8]}"
    clean_claim_id = claim_id or f"claim_{clean_run_id}"
    clean_trace_id = trace_id or f"trace_{clean_run_id}"
    clean_correlation_id = correlation_id or clean_trace_id
    clean_session_id = session_id or f"sess_runtime_lifecycle_long_timeout_probe_{stamp}"
    idempotency_key = f"idem_{clean_run_id}"
    route_metadata = _route_metadata(
        selected_provider,
        selected_model,
        actual_served_provider,
        actual_served_model,
        provider_model_truth_source,
    )

    identity_metadata = {
        "task_id": clean_task_id,
        "trace_id": clean_trace_id,
        "correlation_id": clean_correlation_id,
        "run_id": clean_run_id,
        "runtime_run_id": clean_run_id,
        "claim_id": clean_claim_id,
        "idempotency_key": idempotency_key,
        "mission_id": mission_id,
        **route_metadata,
    }
    task = Task(
        id=clean_task_id,
        title="Runtime lifecycle long-timeout coverage probe",
        description=(
            "Bounded local proof that long-timeout receipts carry idempotency, "
            "mission, and explicit no-artifact truth without pretending provider "
            "execution was impossible."
        ),
        metadata={
            **identity_metadata,
            "active_claim": {
                "claimed_at": now.isoformat(),
                "claim_expires_at_epoch": int(now.timestamp()) + 3600,
            },
            "requested_output": [],
            "timeout_seconds": 3600,
        },
    )
    dispatch = TaskDispatch(
        task_id=clean_task_id,
        agent_id=agent_id,
        topology=TopologyType.FAN_OUT,
        timeout_seconds=3600.0,
        metadata={
            **identity_metadata,
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 3660,
        },
    )
    ledger = SessionLedger(
        base_dir=ledger_dir,
        session_id=clean_session_id,
        runtime_db_path=db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(dispatch, task=task, status="running", require_identity=True)
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="long_timeout",
        error="Task execution exceeded long timeout before artifact completion (probe)",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="long_timeout",
        error="Task execution exceeded long timeout before artifact completion (probe)",
        require_identity=True,
    )

    coverage = _load_coverage_report().build_report(
        db_path,
        latest_limit=latest_limit,
        run_id=clean_run_id,
    )
    return {
        "probe": "runtime_lifecycle_long_timeout_probe",
        "db_path": str(db_path.expanduser()),
        "run_id": clean_run_id,
        "task_id": clean_task_id,
        "claim_id": clean_claim_id,
        "agent_id": agent_id,
        "session_id": clean_session_id,
        "mission_id": mission_id,
        "artifact_id": "",
        "selected_provider": route_metadata.get("selected_provider", ""),
        "selected_model": route_metadata.get("selected_model", ""),
        "actual_served_provider": route_metadata.get("actual_served_provider", ""),
        "actual_served_model": route_metadata.get("actual_served_model", ""),
        "provider_model_truth_source": route_metadata.get("provider_model_truth_source", ""),
        "long_timeout_failure_code": "long_timeout",
        "coverage": coverage,
    }


def _print_text(result: dict[str, Any]) -> None:
    coverage_summary = result["coverage"]["summary"]
    print(str(result.get("probe", "runtime_receipt_probe")).upper())
    print(f"DB:            {result['db_path']}")
    print(f"Run ID:        {result['run_id']}")
    print(f"Task ID:       {result['task_id']}")
    print(f"Mission ID:    {result['mission_id']}")
    if result.get("selected_provider"):
        print(f"Selected provider: {result['selected_provider']}")
    if result.get("selected_model"):
        print(f"Selected model:    {result['selected_model']}")
    if result.get("actual_served_provider"):
        print(f"Served provider:   {result['actual_served_provider']}")
    if result.get("actual_served_model"):
        print(f"Served model:      {result['actual_served_model']}")
    if result.get("provider_model_truth_source"):
        print(f"Provider/model source: {result['provider_model_truth_source']}")
    if result.get("topology"):
        print(f"Topology:      {result['topology']}")
    if result.get("runner_error"):
        print(f"Runner error:  {result['runner_error']}")
    print(f"Artifact:      {result['artifact_id']}")
    if result.get("payload_path"):
        print(f"Payload:       {result['payload_path']}")
    if result.get("manifest_path"):
        print(f"Manifest:      {result['manifest_path']}")
    print(f"70->75 gate:   {'PASS' if coverage_summary['score_gate_70_to_75'] else 'FAIL'}")
    terminal_total = coverage_summary.get("latest_terminal_major_task_receipts_total", 0)
    if terminal_total:
        print(
            "Terminal provider/model: "
            f"{coverage_summary['latest_terminal_major_task_receipts_provider_model_percent']}% "
            f"proof={coverage_summary['latest_terminal_major_task_receipts_provider_model_provenance_percent']}% "
            f"accounted={coverage_summary['latest_terminal_major_task_receipts_provider_model_accounted_percent']}% "
            f"terminal={terminal_total}"
        )
    pending_execution = coverage_summary.get("latest_major_task_receipts_pending_execution")
    if pending_execution is not None:
        print(f"Provider/model pending execution: {pending_execution}")
    if coverage_summary.get("blockers"):
        print("Blockers:")
        for blocker in coverage_summary["blockers"]:
            print(f"  - {blocker}")
    if coverage_summary.get("production_readiness_blockers"):
        print("Production-readiness blockers:")
        for blocker in coverage_summary["production_readiness_blockers"]:
            print(f"  - {blocker}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="runtime.db path to mutate")
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_LEDGER_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--mission-id", default=DEFAULT_MISSION_ID)
    parser.add_argument(
        "--producer",
        choices=(
            "runtime-lifecycle",
            "runtime-lifecycle-claim-timeout",
            "runtime-lifecycle-dropoff",
            "runtime-lifecycle-long-timeout",
            "runtime-state-sync",
            "orchestrator-spine",
        ),
        default="runtime-lifecycle",
        help="receipt producer path to exercise",
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--agent-id", default="runtime-spine-hardening-probe")
    parser.add_argument("--claim-id", default="")
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--selected-provider", default="")
    parser.add_argument("--selected-model", default="")
    parser.add_argument("--actual-served-provider", default="")
    parser.add_argument("--actual-served-model", default="")
    parser.add_argument("--provider-model-truth-source", default="")
    parser.add_argument(
        "--no-provider-execution",
        action="store_true",
        help="stamp explicit no-provider execution truth for a zero-cost control probe",
    )
    parser.add_argument(
        "--no-provider-model-reason",
        default="runtime_lifecycle_receipt_probe_no_provider_execution",
    )
    parser.add_argument(
        "--topology",
        choices=("pipeline", "fan-out", "fan_out"),
        default="pipeline",
        help="orchestrator-spine probe topology",
    )
    parser.add_argument(
        "--runner-error",
        default="",
        help="orchestrator-spine probe error to raise from the local runner",
    )
    parser.add_argument(
        "--no-preseed-artifact",
        action="store_true",
        help="orchestrator-spine probe should rely on the real success artifact path",
    )
    parser.add_argument("--latest-limit", type=int, default=50)
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="required when --db points at the default live runtime.db",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    db_path = args.db.expanduser()
    if _same_path(db_path, LIVE_RUNTIME_DB) and not args.allow_live:
        print(
            "refusing to write live runtime.db without --allow-live; pass --db for a temp DB or add --allow-live",
            file=sys.stderr,
        )
        return 2

    if args.producer == "runtime-state-sync":
        result = asyncio.run(
            run_sync_store_probe(
                db_path,
                artifact_dir=args.artifact_dir,
                mission_id=args.mission_id,
                run_id=args.run_id,
                task_id=args.task_id,
                agent_id=args.agent_id,
                claim_id=args.claim_id,
                trace_id=args.trace_id,
                correlation_id=args.correlation_id,
                session_id=args.session_id,
                selected_provider=args.selected_provider,
                selected_model=args.selected_model,
                actual_served_provider=args.actual_served_provider,
                actual_served_model=args.actual_served_model,
                provider_model_truth_source=args.provider_model_truth_source,
                latest_limit=args.latest_limit,
            )
        )
    elif args.producer == "runtime-lifecycle-dropoff":
        result = asyncio.run(
            run_runtime_lifecycle_dropoff_probe(
                db_path,
                ledger_dir=args.ledger_dir,
                mission_id=args.mission_id,
                run_id=args.run_id,
                task_id=args.task_id,
                agent_id=args.agent_id,
                claim_id=args.claim_id,
                trace_id=args.trace_id,
                correlation_id=args.correlation_id,
                session_id=args.session_id,
                selected_provider=args.selected_provider,
                selected_model=args.selected_model,
                actual_served_provider=args.actual_served_provider,
                actual_served_model=args.actual_served_model,
                provider_model_truth_source=args.provider_model_truth_source,
                no_provider_execution=args.no_provider_execution,
                no_provider_model_reason=args.no_provider_model_reason,
                latest_limit=args.latest_limit,
            )
        )
    elif args.producer == "runtime-lifecycle-claim-timeout":
        result = asyncio.run(
            run_runtime_lifecycle_claim_timeout_probe(
                db_path,
                ledger_dir=args.ledger_dir,
                mission_id=args.mission_id,
                run_id=args.run_id,
                task_id=args.task_id,
                agent_id=args.agent_id,
                claim_id=args.claim_id,
                trace_id=args.trace_id,
                correlation_id=args.correlation_id,
                session_id=args.session_id,
                selected_provider=args.selected_provider,
                selected_model=args.selected_model,
                actual_served_provider=args.actual_served_provider,
                actual_served_model=args.actual_served_model,
                provider_model_truth_source=args.provider_model_truth_source,
                latest_limit=args.latest_limit,
            )
        )
    elif args.producer == "runtime-lifecycle-long-timeout":
        result = asyncio.run(
            run_runtime_lifecycle_long_timeout_probe(
                db_path,
                ledger_dir=args.ledger_dir,
                mission_id=args.mission_id,
                run_id=args.run_id,
                task_id=args.task_id,
                agent_id=args.agent_id,
                claim_id=args.claim_id,
                trace_id=args.trace_id,
                correlation_id=args.correlation_id,
                session_id=args.session_id,
                selected_provider=args.selected_provider,
                selected_model=args.selected_model,
                actual_served_provider=args.actual_served_provider,
                actual_served_model=args.actual_served_model,
                provider_model_truth_source=args.provider_model_truth_source,
                latest_limit=args.latest_limit,
            )
        )
    elif args.producer == "orchestrator-spine":
        result = asyncio.run(
            run_orchestrator_spine_probe(
                db_path,
                ledger_dir=args.ledger_dir,
                artifact_dir=args.artifact_dir,
                mission_id=args.mission_id,
                run_id=args.run_id,
                task_id=args.task_id,
                agent_id=args.agent_id,
                claim_id=args.claim_id,
                trace_id=args.trace_id,
                correlation_id=args.correlation_id,
                session_id=args.session_id,
                selected_provider=args.selected_provider,
                selected_model=args.selected_model,
                actual_served_provider=args.actual_served_provider,
                actual_served_model=args.actual_served_model,
                provider_model_truth_source=args.provider_model_truth_source,
                no_provider_execution=args.no_provider_execution,
                no_provider_model_reason=args.no_provider_model_reason,
                topology=args.topology,
                runner_error=args.runner_error,
                preseed_artifact=not args.no_preseed_artifact,
                latest_limit=args.latest_limit,
            )
        )
    else:
        result = asyncio.run(
            run_probe(
                db_path,
                ledger_dir=args.ledger_dir,
                artifact_dir=args.artifact_dir,
                mission_id=args.mission_id,
                run_id=args.run_id,
                task_id=args.task_id,
                agent_id=args.agent_id,
                claim_id=args.claim_id,
                trace_id=args.trace_id,
                correlation_id=args.correlation_id,
                session_id=args.session_id,
                selected_provider=args.selected_provider,
                selected_model=args.selected_model,
                actual_served_provider=args.actual_served_provider,
                actual_served_model=args.actual_served_model,
                provider_model_truth_source=args.provider_model_truth_source,
                no_provider_execution=args.no_provider_execution,
                no_provider_model_reason=args.no_provider_model_reason,
                latest_limit=args.latest_limit,
            )
        )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_text(result)
    return 0 if result["coverage"]["summary"].get("score_gate_70_to_75", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
