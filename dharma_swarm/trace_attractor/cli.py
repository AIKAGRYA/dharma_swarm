"""CLI entry point for ``dgc trace-attractor``.

Reads raw data from ontology, runtime-state, and telemetry stores,
normalises each record into an AttractorEvent, then delegates to the
pure TraceAttractorProjector.build_packet() for deterministic projection.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any


def run_trace_attractor(
    *,
    trace_id: str,
    as_json: bool = False,
    registry_path: str | None = None,
    runtime_db: str | None = None,
    telemetry_db: str | None = None,
    board_db: str | None = None,
    sakshi_log: str | None = None,
) -> str:
    """Project a trace_id into an AttractorPacket and return formatted output."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _project(
                trace_id=trace_id,
                as_json=as_json,
                registry_path=registry_path,
                runtime_db=runtime_db,
                telemetry_db=telemetry_db,
                board_db=board_db,
                sakshi_log=sakshi_log,
            )
        )
    finally:
        loop.close()


async def _collect_events(
    trace_id: str,
    registry_path: str | None,
    runtime_db: str | None,
    telemetry_db: str | None,
    board_db: str | None,
    sakshi_log: str | None,
) -> list[dict[str, Any]]:
    """Gather raw records from available stores and normalise to event dicts."""
    registry = None
    try:
        from dharma_swarm.ontology_runtime import get_shared_registry

        registry = get_shared_registry(path=registry_path)
    except Exception:
        pass

    try:
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB as default_runtime_db
    except Exception:
        default_runtime_db = None

    try:
        from dharma_swarm.telemetry_plane import (
            DEFAULT_TELEMETRY_DB as default_telemetry_db,
        )
    except Exception:
        default_telemetry_db = None

    from dharma_swarm.trace_attractor.readers import TraceAttractorStoreReader

    runtime_db_path = (
        Path(runtime_db)
        if runtime_db
        else Path(default_runtime_db) if default_runtime_db else None
    )
    telemetry_db_path = (
        Path(telemetry_db)
        if telemetry_db
        else Path(default_telemetry_db) if default_telemetry_db else None
    )
    reader = TraceAttractorStoreReader(
        registry=registry,
        runtime_db_path=runtime_db_path,
        telemetry_db_path=telemetry_db_path,
        board_db_path=Path(board_db) if board_db else None,
        sakshi_log_path=Path(sakshi_log) if sakshi_log else None,
    )
    return [event.model_dump(mode="json") for event in reader.read_events(trace_id)]


async def _project(
    *,
    trace_id: str,
    as_json: bool,
    registry_path: str | None,
    runtime_db: str | None,
    telemetry_db: str | None,
    board_db: str | None,
    sakshi_log: str | None,
) -> str:
    from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

    events = await _collect_events(
        trace_id, registry_path, runtime_db, telemetry_db, board_db, sakshi_log,
    )

    projector = TraceAttractorProjector()
    packet = projector.build_packet(trace_id, events)

    if as_json:
        return packet.to_stable_json()

    lines = [
        f"Trace: {packet.trace_id}",
        f"  proposals: {len(packet.proposal_ids)}",
        f"  tasks: {len(packet.task_ids)}",
        f"  outcomes: {len(packet.outcome_ids)}",
        f"  value_events: {len(packet.value_event_ids)}",
        f"  economic_events: {len(packet.economic_event_ids)}",
        f"  warrant: {packet.fourfold_warrant.status}",
        f"  findings: {len(packet.lifecycle_findings)}",
    ]
    return "\n".join(lines)
