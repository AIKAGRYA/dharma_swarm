"""CLI entry point for ``dgc trace-attractor``.

Reads raw data from ontology, runtime-state, and telemetry stores,
normalises each record into an AttractorEvent, then delegates to the
pure TraceAttractorProjector.build_packet() for deterministic projection.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any


def run_trace_attractor(
    *,
    trace_id: str,
    as_json: bool = False,
    registry_path: str | None = None,
    runtime_db: str | None = None,
    telemetry_db: str | None = None,
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
            )
        )
    finally:
        loop.close()


async def _collect_events(
    trace_id: str,
    registry_path: str | None,
    runtime_db: str | None,
    telemetry_db: str | None,
) -> list[dict[str, Any]]:
    """Gather raw records from available stores and normalise to event dicts."""
    from dharma_swarm.trace_attractor.models import AttractorEvent

    events: list[dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # --- Ontology objects ---
    try:
        from dharma_swarm.ontology_runtime import get_shared_registry

        registry = get_shared_registry(path=registry_path)
        for type_name in (
            "ActionProposal", "GateDecision", "Outcome",
            "ValueEvent", "Contribution", "WitnessLog",
        ):
            for obj in registry.get_objects_by_type(type_name):
                props = getattr(obj, "properties", {}) or {}
                if props.get("trace_id") != trace_id:
                    meta = getattr(obj, "metadata", {}) or {}
                    if meta.get("trace_id") != trace_id:
                        continue
                created = getattr(obj, "created_at", None)
                events.append(
                    AttractorEvent(
                        event_id=f"onto_{obj.id}",
                        trace_id=trace_id,
                        proposal_id=props.get("proposal_id", ""),
                        session_id=props.get("session_id", ""),
                        source_store="ontology",
                        source_table_or_type=type_name,
                        source_object_id=obj.id,
                        event_type=type_name,
                        occurred_at=str(created) if created else now_iso,
                        attributes=dict(props),
                    ).model_dump(mode="json")
                )
    except Exception:
        pass

    # --- RuntimeState (task_claims, delegation_runs) ---
    try:
        import aiosqlite
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

        db = runtime_db or str(DEFAULT_RUNTIME_DB)
        async with aiosqlite.connect(db) as conn:
            conn.row_factory = aiosqlite.Row
            for table, id_col in [
                ("task_claims", "claim_id"),
                ("delegation_runs", "run_id"),
            ]:
                try:
                    cursor = await conn.execute(
                        f"SELECT * FROM {table} WHERE trace_id = ?",
                        (trace_id,),
                    )
                    for row in await cursor.fetchall():
                        row_d = dict(row)
                        events.append(
                            AttractorEvent(
                                event_id=f"rt_{row_d.get(id_col, '')}",
                                trace_id=trace_id,
                                session_id=row_d.get("session_id", ""),
                                source_store="runtime_state",
                                source_table_or_type=table,
                                source_object_id=row_d.get(id_col, ""),
                                event_type=table,
                                occurred_at=row_d.get(
                                    "started_at",
                                    row_d.get("claimed_at", now_iso),
                                ),
                                attributes=row_d,
                            ).model_dump(mode="json")
                        )
                except Exception:
                    pass
    except Exception:
        pass

    # --- TelemetryPlane (economic_events) ---
    try:
        import aiosqlite
        from dharma_swarm.telemetry_plane import DEFAULT_TELEMETRY_DB

        db = telemetry_db or str(DEFAULT_TELEMETRY_DB)
        async with aiosqlite.connect(db) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                cursor = await conn.execute(
                    "SELECT * FROM economic_events WHERE trace_id = ?",
                    (trace_id,),
                )
                for row in await cursor.fetchall():
                    row_d = dict(row)
                    events.append(
                        AttractorEvent(
                            event_id=f"tel_{row_d.get('event_id', '')}",
                            trace_id=trace_id,
                            session_id=row_d.get("session_id", ""),
                            source_store="telemetry_plane",
                            source_table_or_type="economic_events",
                            source_object_id=row_d.get("event_id", ""),
                            event_type="economic_event",
                            occurred_at=row_d.get("created_at", now_iso),
                            attributes=row_d,
                        ).model_dump(mode="json")
                    )
            except Exception:
                pass
    except Exception:
        pass

    return events


async def _project(
    *,
    trace_id: str,
    as_json: bool,
    registry_path: str | None,
    runtime_db: str | None,
    telemetry_db: str | None,
) -> str:
    from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

    events = await _collect_events(
        trace_id, registry_path, runtime_db, telemetry_db,
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
