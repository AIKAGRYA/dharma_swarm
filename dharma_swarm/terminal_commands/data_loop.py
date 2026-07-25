"""Data loop commands (flywheel, reciprocity, ouroboros, value-events, ledger)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json


from dharma_swarm.terminal_commands._helpers import (
    _load_json_object,
    _normalize_optional_text,
    _run,
)

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
