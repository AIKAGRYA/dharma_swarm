"""CLI entry point for ``dgc trace-attractor``."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def run_trace_attractor(
    *,
    trace_id: str,
    as_json: bool = False,
    registry_path: str | None = None,
    runtime_db: str | None = None,
    telemetry_db: str | None = None,
) -> str:
    """Project a trace_id into an AttractorPacket and return formatted output."""
    return asyncio.get_event_loop().run_until_complete(
        _project(
            trace_id=trace_id,
            as_json=as_json,
            registry_path=registry_path,
            runtime_db=runtime_db,
            telemetry_db=telemetry_db,
        )
    )


async def _project(
    *,
    trace_id: str,
    as_json: bool,
    registry_path: str | None,
    runtime_db: str | None,
    telemetry_db: str | None,
) -> str:
    from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

    # Build store handles
    ontology = None
    runtime_state = None
    telemetry_plane = None
    lineage_graph = None

    try:
        from dharma_swarm.ontology_runtime import get_shared_registry

        ontology = get_shared_registry(path=registry_path)
    except Exception:
        pass

    try:
        from dharma_swarm.runtime_state import RuntimeStateStore
        from dharma_swarm.daemon_config import dharma_state_dir

        db_path = runtime_db or str(dharma_state_dir() / "runtime_state.db")
        runtime_state = RuntimeStateStore(db_path=db_path)
    except Exception:
        pass

    try:
        from dharma_swarm.telemetry_plane import TelemetryPlaneStore
        from dharma_swarm.daemon_config import dharma_state_dir

        tp_path = telemetry_db or str(dharma_state_dir() / "telemetry.db")
        telemetry_plane = TelemetryPlaneStore(db_path=tp_path)
    except Exception:
        pass

    try:
        from dharma_swarm.lineage import LineageGraph

        lineage_graph = LineageGraph()
    except Exception:
        pass

    projector = TraceAttractorProjector(
        ontology=ontology,
        runtime_state=runtime_state,
        telemetry_plane=telemetry_plane,
        lineage_graph=lineage_graph,
    )

    packet = await projector.project(trace_id)

    if as_json:
        return json.dumps(packet.to_dict(), indent=2, default=str)
    return packet.human_summary()
