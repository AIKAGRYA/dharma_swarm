"""CLI commands for flywheel, reciprocity, and ouroboros integrations.

Extracted from dgc_cli.py for module budget compliance.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.cli._helpers import _run, _load_json_object, _normalize_optional_text, DHARMA_STATE, DHARMA_SWARM

def cmd_flywheel_jobs() -> None:
    """List Data Flywheel jobs."""

    async def _jobs():
        from dharma_swarm.integrations import DataFlywheelClient

        client = DataFlywheelClient()
        payload = await client.list_jobs()
        print(json.dumps(payload, indent=2))

    _run(_jobs())


async def _flywheel_export_payload(
    *,
    run_id: str,
    workload_id: str,
    client_id: str,
    trace_id: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    export_root: str | None = None,
    data_split_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from dharma_swarm.flywheel_exporter import FlywheelExporter
    from dharma_swarm.memory_lattice import MemoryLattice
    from dharma_swarm.runtime_state import RuntimeStateStore

    runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
    memory_lattice = MemoryLattice(
        db_path=runtime_state.db_path,
        event_log_dir=Path(event_log_dir) if event_log_dir else None,
    )
    exporter = FlywheelExporter(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        export_root=Path(export_root) if export_root else None,
    )
    try:
        result = await exporter.export_run(
            run_id=run_id,
            workload_id=workload_id,
            client_id=client_id,
            trace_id=trace_id,
            created_by="dgc_cli",
            data_split_config=data_split_config,
        )
    finally:
        await memory_lattice.close()
    return {
        "export_id": result.record.export_id,
        "artifact_id": result.artifact.artifact_id,
        "run_id": result.record.run_id,
        "task_id": result.record.task_id,
        "session_id": result.record.session_id,
        "trace_id": result.record.trace_id,
        "workload_id": result.record.workload_id,
        "client_id": result.record.client_id,
        "status": result.record.status,
        "metrics": dict(result.record.metrics),
        "job_request": dict(result.record.job_request),
        "export_path": str(result.export_path),
        "manifest_path": str(result.manifest_path),
        "receipt_event_id": str(result.receipt.get("event_id", "")),
    }


def cmd_flywheel_export(
    *,
    run_id: str,
    workload_id: str,
    client_id: str,
    trace_id: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    export_root: str | None = None,
) -> None:
    """Materialize a local canonical flywheel export artifact."""

    payload = _run(
        _flywheel_export_payload(
            run_id=run_id,
            workload_id=workload_id,
            client_id=client_id,
            trace_id=trace_id,
            db_path=db_path,
            event_log_dir=event_log_dir,
            export_root=export_root,
        )
    )
    print(json.dumps(payload, indent=2))


async def _flywheel_record_payload(
    *,
    job_id: str,
    workload_id: str | None = None,
    client_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> dict[str, Any]:
    from dharma_swarm.evaluation_registry import EvaluationRegistry
    from dharma_swarm.integrations import DataFlywheelClient
    from dharma_swarm.memory_lattice import MemoryLattice
    from dharma_swarm.runtime_state import RuntimeStateStore

    client = DataFlywheelClient()
    job = await client.get_job(job_id)
    runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
    memory_lattice = MemoryLattice(
        db_path=runtime_state.db_path,
        event_log_dir=Path(event_log_dir) if event_log_dir else None,
    )
    registry = EvaluationRegistry(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        workspace_root=Path(workspace_root) if workspace_root else None,
        provenance_root=Path(provenance_root) if provenance_root else None,
    )
    try:
        result = await registry.record_flywheel_job(
            job,
            job_id=job_id,
            workload_id=workload_id,
            client_id=client_id,
            run_id=run_id or "",
            session_id=session_id or "",
            task_id=task_id or "",
            trace_id=trace_id,
            created_by="dgc_cli",
        )
    finally:
        await memory_lattice.close()
    return {
        "job": job,
        "registry": {
            "artifact_id": result.artifact.artifact_id,
            "manifest_path": str(result.manifest_path),
            "summary": dict(result.summary),
            "fact_ids": [fact.fact_id for fact in result.facts],
            "receipt_event_id": str(result.receipt.get("event_id", "")),
        },
    }


def cmd_flywheel_record(
    *,
    job_id: str,
    workload_id: str | None = None,
    client_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> None:
    """Record a remote Flywheel job result into canonical DGC truth."""

    payload = _run(
        _flywheel_record_payload(
            job_id=job_id,
            workload_id=workload_id,
            client_id=client_id,
            run_id=run_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            db_path=db_path,
            event_log_dir=event_log_dir,
            workspace_root=workspace_root,
            provenance_root=provenance_root,
        )
    )
    print(json.dumps(payload, indent=2))


def cmd_flywheel_start(
    workload_id: str,
    client_id: str,
    eval_size: int,
    val_ratio: float,
    min_total_records: int,
    limit: int,
    run_id: str | None = None,
    trace_id: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    export_root: str | None = None,
) -> None:
    """Start a Data Flywheel job."""

    async def _start():
        from dharma_swarm.integrations import DataFlywheelClient

        local_export: dict[str, Any] | None = None
        data_split_config = {
            "eval_size": eval_size,
            "val_ratio": val_ratio,
            "min_total_records": min_total_records,
            "limit": limit,
        }
        if run_id:
            local_export = await _flywheel_export_payload(
                run_id=run_id,
                workload_id=workload_id,
                client_id=client_id,
                trace_id=trace_id,
                db_path=db_path,
                event_log_dir=event_log_dir,
                export_root=export_root,
                data_split_config=data_split_config,
            )
        client = DataFlywheelClient()
        payload = await client.create_job(
            workload_id=workload_id,
            client_id=client_id,
            data_split_config=data_split_config,
        )
        if local_export is not None:
            payload = {
                "local_export": local_export,
                "job": payload,
            }
        print(json.dumps(payload, indent=2))

    _run(_start())


def cmd_flywheel_get(job_id: str) -> None:
    """Get Data Flywheel job details."""

    async def _get():
        from dharma_swarm.integrations import DataFlywheelClient

        client = DataFlywheelClient()
        payload = await client.get_job(job_id)
        print(json.dumps(payload, indent=2))

    _run(_get())


def cmd_flywheel_cancel(job_id: str) -> None:
    """Cancel Data Flywheel job."""

    async def _cancel():
        from dharma_swarm.integrations import DataFlywheelClient

        client = DataFlywheelClient()
        payload = await client.cancel_job(job_id)
        print(json.dumps(payload, indent=2))

    _run(_cancel())


def cmd_flywheel_delete(job_id: str) -> None:
    """Delete Data Flywheel job."""

    async def _delete():
        from dharma_swarm.integrations import DataFlywheelClient

        client = DataFlywheelClient()
        payload = await client.delete_job(job_id)
        print(json.dumps(payload, indent=2))

    _run(_delete())


def cmd_flywheel_watch(job_id: str, poll_sec: float, timeout_sec: float) -> None:
    """Wait until a Data Flywheel job reaches terminal state."""

    async def _watch():
        from dharma_swarm.integrations import DataFlywheelClient

        client = DataFlywheelClient()
        payload = await client.wait_for_terminal(
            job_id,
            poll_sec=poll_sec,
            timeout_sec=timeout_sec,
        )
        print(json.dumps(payload, indent=2))

    _run(_watch())


def cmd_reciprocity_health() -> None:
    """Check Planetary Reciprocity Commons service health."""

    async def _health():
        from dharma_swarm.integrations import ReciprocityCommonsClient

        client = ReciprocityCommonsClient()
        payload = await client.health()
        print(json.dumps(payload, indent=2))

    _run(_health())


def cmd_reciprocity_summary() -> None:
    """Fetch the current reciprocity ledger summary."""

    async def _summary():
        from dharma_swarm.integrations import ReciprocityCommonsClient

        client = ReciprocityCommonsClient()
        payload = await client.ledger_summary()
        print(json.dumps(payload, indent=2))

    _run(_summary())


async def _reciprocity_publish_payload(
    *,
    record_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from dharma_swarm.integrations import ReciprocityCommonsClient

    client = ReciprocityCommonsClient()
    publishers = {
        "activity": client.publish_activity,
        "obligation": client.publish_obligation,
        "project": client.publish_project,
        "outcome": client.publish_outcome,
    }
    try:
        publish = publishers[record_type]
    except KeyError as exc:
        raise ValueError(f"unsupported reciprocity record type: {record_type}") from exc

    response = await publish(payload)
    return {
        "record_type": record_type,
        "record": payload,
        "response": response,
    }


def cmd_reciprocity_publish(
    *,
    record_type: str,
    json_payload: str | None = None,
    file_path: str | None = None,
) -> None:
    """Publish a reciprocity activity, obligation, project, or outcome."""

    payload = _load_json_object(
        json_payload=json_payload,
        file_path=file_path,
        label="reciprocity publish payload",
    )
    result = _run(
        _reciprocity_publish_payload(
            record_type=record_type,
            payload=payload,
        )
    )
    print(json.dumps(result, indent=2))


async def _reciprocity_record_payload(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    summary_type: str = "ledger_summary",
    json_payload: str | None = None,
    file_path: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> dict[str, Any]:
    from dharma_swarm.evaluation_registry import EvaluationRegistry
    from dharma_swarm.integrations import ReciprocityCommonsClient
    from dharma_swarm.memory_lattice import MemoryLattice
    from dharma_swarm.runtime_state import RuntimeStateStore

    normalized_run_id = _normalize_optional_text(run_id)
    normalized_session_id = _normalize_optional_text(session_id)
    normalized_task_id = _normalize_optional_text(task_id)
    normalized_trace_id = _normalize_optional_text(trace_id) or None
    normalized_summary_type = _normalize_optional_text(
        summary_type,
        default="ledger_summary",
    )
    if not normalized_run_id and not normalized_session_id:
        raise ValueError("session_id or run_id is required to record evaluation outputs canonically")

    provided_payload = (
        _load_json_object(
            json_payload=json_payload,
            file_path=file_path,
            label="reciprocity summary payload",
        )
        if json_payload is not None or file_path is not None
        else None
    )
    if provided_payload is not None:
        summary_payload = dict(provided_payload)
    else:
        client = ReciprocityCommonsClient()
        summary_payload = dict(await client.ledger_summary())
    summary_payload.setdefault("service", "reciprocity_commons")
    summary_payload.setdefault("source", "reciprocity_commons")
    summary_payload.setdefault("summary_type", normalized_summary_type)

    runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
    memory_lattice = MemoryLattice(
        db_path=runtime_state.db_path,
        event_log_dir=Path(event_log_dir) if event_log_dir else None,
    )
    registry = EvaluationRegistry(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        workspace_root=Path(workspace_root) if workspace_root else None,
        provenance_root=Path(provenance_root) if provenance_root else None,
    )
    try:
        result = await registry.record_reciprocity_summary(
            summary_payload,
            run_id=normalized_run_id,
            session_id=normalized_session_id,
            task_id=normalized_task_id,
            trace_id=normalized_trace_id,
            created_by="dgc_cli",
        )
    finally:
        await memory_lattice.close()

    return {
        "summary": summary_payload,
        "registry": {
            "artifact_id": result.artifact.artifact_id,
            "manifest_path": str(result.manifest_path),
            "summary": dict(result.summary),
            "fact_ids": [fact.fact_id for fact in result.facts],
            "receipt_event_id": str(result.receipt.get("event_id", "")),
        },
    }


def cmd_reciprocity_record(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    summary_type: str = "ledger_summary",
    json_payload: str | None = None,
    file_path: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> None:
    """Record the current reciprocity ledger summary into canonical DGC truth."""

    payload = _run(
        _reciprocity_record_payload(
            run_id=run_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            summary_type=summary_type,
            json_payload=json_payload,
            file_path=file_path,
            db_path=db_path,
            event_log_dir=event_log_dir,
            workspace_root=workspace_root,
            provenance_root=provenance_root,
        )
    )
    print(json.dumps(payload, indent=2))


def cmd_ouroboros_connections(
    *,
    package_dir: str | None = None,
    threshold: float = 0.08,
    disagreement_threshold: float = 0.1,
    min_text_length: int = 50,
    limit: int = 15,
    as_json: bool = False,
) -> None:
    """Profile module docstrings and report behavioral affinities/disagreements."""
    from dharma_swarm.ouroboros import profile_python_modules

    if limit < 0:
        raise ValueError("limit must be >= 0")
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    if disagreement_threshold < 0:
        raise ValueError("disagreement_threshold must be >= 0")

    target_dir = Path(package_dir) if package_dir else DHARMA_SWARM / "dharma_swarm"
    finder, profiles = profile_python_modules(
        target_dir,
        min_text_length=min_text_length,
    )
    connections = finder.find_connections(threshold=threshold)
    disagreements = finder.find_h1_disagreements(threshold=disagreement_threshold)
    payload = {
        "package_dir": str(target_dir),
        "profiles": profiles,
        "connections": connections,
        "disagreements": disagreements,
        "summary": {
            "modules_profiled": len(profiles),
            "connections": len(connections),
            "disagreements": len(disagreements),
            "threshold": threshold,
            "disagreement_threshold": disagreement_threshold,
            "min_text_length": min_text_length,
        },
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"Profiling {len(profiles)} modules from {target_dir}...\n")
    for row in profiles[:limit]:
        print(
            f"  {row['module']:<30} "
            f"entropy={row['entropy']:.3f}  "
            f"self_ref={row['self_reference_density']:.4f}  "
            f"swabhaav={row['swabhaav_ratio']:.3f}  "
            f"recog={row['recognition_type']}"
        )
    if len(profiles) > limit:
        print(f"  ... {len(profiles) - limit} more module profiles")

    print("\n" + "=" * 80)
    print("H0: STRUCTURAL CONNECTIONS (similar behavioral profiles)")
    print("=" * 80)
    if connections:
        for conn in connections[:limit]:
            print(
                f"  {conn['module_a']:<25} <-> {conn['module_b']:<25} "
                f"d={conn['distance']:.4f}  type={conn['connection_type']}"
            )
        if len(connections) > limit:
            print(f"  ... {len(connections) - limit} more H0 connections")
    else:
        print(f"  No close connections found (threshold={threshold:.3f})")

    print("\n" + "=" * 80)
    print("H1: PRODUCTIVE DISAGREEMENTS (divergent profiles)")
    print("=" * 80)
    if disagreements:
        for dis in disagreements[:limit]:
            print(
                f"  {dis['module_a']:<25} =/= {dis['module_b']:<25} "
                f"d={dis['distance']:.4f}  "
                f"type={dis['disagreement_type']}  "
                f"({dis['recognition_a']} vs {dis['recognition_b']})"
            )
        if len(disagreements) > limit:
            print(f"  ... {len(disagreements) - limit} more H1 disagreements")
    else:
        print(f"  No H1 disagreements found (threshold={disagreement_threshold:.3f})")

    print("\n" + "=" * 80)
    print("SYNTHESIS")
    print("=" * 80)
    print(f"\n  Modules profiled: {len(profiles)}")
    print(f"  H0 connections:   {len(connections)}")
    print(f"  H1 disagreements: {len(disagreements)}")


async def _ouroboros_record_payload(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    log_path: str | None = None,
    cycle_id: str | None = None,
    json_payload: str | None = None,
    file_path: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> dict[str, Any]:
    from dharma_swarm.evaluation_registry import EvaluationRegistry
    from dharma_swarm.memory_lattice import MemoryLattice
    from dharma_swarm.runtime_state import RuntimeStateStore

    normalized_run_id = _normalize_optional_text(run_id)
    normalized_session_id = _normalize_optional_text(session_id)
    normalized_task_id = _normalize_optional_text(task_id)
    normalized_trace_id = _normalize_optional_text(trace_id) or None
    normalized_cycle_id = _normalize_optional_text(cycle_id) or None
    if not normalized_run_id and not normalized_session_id:
        raise ValueError("session_id or run_id is required to record evaluation outputs canonically")

    inline_payload_requested = json_payload is not None or file_path is not None
    if inline_payload_requested and (log_path is not None or normalized_cycle_id is not None):
        raise ValueError(
            "ouroboros record accepts either --json/--file or --log-path/--cycle-id, not both"
        )

    resolved_log_path: Path | None
    if inline_payload_requested:
        observation_payload = _load_json_object(
            json_payload=json_payload,
            file_path=file_path,
            label="ouroboros observation payload",
        )
        resolved_log_path = None
    else:
        resolved_log_path = Path(log_path) if log_path else _default_ouroboros_log_path()
        observation_payload = _load_ouroboros_observation(
            log_path=resolved_log_path,
            cycle_id=normalized_cycle_id,
        )

    runtime_state = RuntimeStateStore(Path(db_path) if db_path else None)
    memory_lattice = MemoryLattice(
        db_path=runtime_state.db_path,
        event_log_dir=Path(event_log_dir) if event_log_dir else None,
    )
    registry = EvaluationRegistry(
        runtime_state=runtime_state,
        memory_lattice=memory_lattice,
        workspace_root=Path(workspace_root) if workspace_root else None,
        provenance_root=Path(provenance_root) if provenance_root else None,
    )
    try:
        result = await registry.record_ouroboros_observation(
            observation_payload,
            run_id=normalized_run_id,
            session_id=normalized_session_id,
            task_id=normalized_task_id,
            trace_id=normalized_trace_id,
            created_by="dgc_cli",
        )
    finally:
        await memory_lattice.close()

    return {
        "observation": observation_payload,
        "log_path": str(resolved_log_path) if resolved_log_path is not None else None,
        "registry": {
            "artifact_id": result.artifact.artifact_id,
            "manifest_path": str(result.manifest_path),
            "summary": dict(result.summary),
            "fact_ids": [fact.fact_id for fact in result.facts],
            "receipt_event_id": str(result.receipt.get("event_id", "")),
        },
    }


def cmd_ouroboros_record(
    *,
    run_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    log_path: str | None = None,
    cycle_id: str | None = None,
    json_payload: str | None = None,
    file_path: str | None = None,
    db_path: str | None = None,
    event_log_dir: str | None = None,
    workspace_root: str | None = None,
    provenance_root: str | None = None,
) -> None:
    """Record an ouroboros observation into canonical runtime truth."""

    payload = _run(
        _ouroboros_record_payload(
            run_id=run_id,
            session_id=session_id,
            task_id=task_id,
            trace_id=trace_id,
            log_path=log_path,
            cycle_id=cycle_id,
            json_payload=json_payload,
            file_path=file_path,
            db_path=db_path,
            event_log_dir=event_log_dir,
            workspace_root=workspace_root,
            provenance_root=provenance_root,
        )
    )
    print(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# v0.4.0: Oz-inspired commands
# ---------------------------------------------------------------------------
