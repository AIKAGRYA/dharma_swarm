"""Tests for read-only Trace Attractor Ledger store readers."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.board.event_log import BoardEvent, BoardEventLog
from dharma_swarm.board.models import CardId
from dharma_swarm.correlation_context import correlation_scope
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    DelegationRun,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.sakshi.provenance_log import ProvenanceEntry, ProvenanceLog
from dharma_swarm.telemetry_plane import EconomicEventRecord, TelemetryPlaneStore
from dharma_swarm.trace_attractor import (
    TraceAttractorProjector,
    TraceAttractorStoreReader,
    read_board_events,
    read_ontology_events,
    read_runtime_events,
    read_sakshi_events,
    read_telemetry_events,
)


TRACE_ID = "trc_reader_main"
OTHER_TRACE_ID = "trc_reader_other"


def _registry_with_trace_objects() -> OntologyRegistry:
    registry = OntologyRegistry.create_dharma_registry()
    proposal, errors = registry.create_object(
        "ActionProposal",
        properties={
            "task_id": "task-reader",
            "agent_id": "agent-reader",
            "action_type": "dispatch",
            "title": "Reader proposal",
            "status": "proposed",
            "priority": "high",
            "trace_id": TRACE_ID,
            "session_id": "sess-reader",
        },
    )
    assert proposal is not None, errors
    gate, errors = registry.create_object(
        "GateDecisionRecord",
        properties={
            "proposal_id": proposal.id,
            "decision": "allow",
            "reason": "reader test",
            "trace_id": TRACE_ID,
        },
    )
    assert gate is not None, errors
    value_event, errors = registry.create_object(
        "ValueEvent",
        properties={
            "outcome_id": "outcome-reader",
            "agent_id": "agent-reader",
            "task_id": "task-reader",
            "task_type": "operator_brief",
            "composite_value": 0.75,
            "trace_id": TRACE_ID,
        },
    )
    assert value_event is not None, errors
    other, errors = registry.create_object(
        "Outcome",
        properties={
            "proposal_id": "proposal-other",
            "task_id": "task-other",
            "agent_id": "agent-other",
            "success": True,
            "trace_id": OTHER_TRACE_ID,
        },
    )
    assert other is not None, errors
    return registry


def test_ontology_reader_filters_objects_by_trace_metadata() -> None:
    registry = _registry_with_trace_objects()

    events = read_ontology_events(registry, TRACE_ID)
    packet = TraceAttractorProjector().build_packet(
        TRACE_ID,
        events,
        generated_at="2026-05-05T00:00:00Z",
    )

    assert {event.source_table_or_type for event in events} == {
        "ActionProposal",
        "GateDecisionRecord",
        "ValueEvent",
    }
    assert packet.task_ids == ["task-reader"]
    assert len(packet.proposal_ids) == 1
    assert len(packet.gate_decision_ids) == 1
    assert len(packet.value_event_ids) == 1
    assert "task-other" not in packet.to_stable_json()


@pytest.mark.asyncio
async def test_runtime_reader_reads_trace_columns_and_artifact_metadata(
    tmp_path: Path,
) -> None:
    runtime_db = tmp_path / "runtime.db"
    store = RuntimeStateStore(runtime_db)

    async with correlation_scope(trace_id=TRACE_ID):
        await store.record_task_claim(
            TaskClaim(
                claim_id="claim-reader",
                task_id="task-reader",
                agent_id="agent-reader",
                session_id="sess-reader",
                metadata={"proposal_id": "proposal-reader"},
            )
        )
        await store.record_delegation_run(
            DelegationRun(
                run_id="run-reader",
                task_id="task-reader",
                claim_id="claim-reader",
                assigned_to="agent-reader",
                session_id="sess-reader",
                metadata={"proposal_id": "proposal-reader"},
            )
        )

    await store.record_artifact(
        ArtifactRecord(
            artifact_id="artifact-reader",
            artifact_kind="operator_brief",
            session_id="sess-reader",
            task_id="task-reader",
            run_id="run-reader",
            manifest_path="reports/witness/trace-reader.md",
            checksum="sha256:reader",
            metadata={"trace_id": TRACE_ID, "proposal_id": "proposal-reader"},
        )
    )

    events = read_runtime_events(runtime_db, TRACE_ID)
    packet = TraceAttractorProjector().build_packet(
        TRACE_ID,
        events,
        generated_at="2026-05-05T00:00:00Z",
    )

    assert {event.source_table_or_type for event in events} == {
        "task_claims",
        "delegation_runs",
        "artifact_records",
    }
    assert packet.claim_ids == ["claim-reader"]
    assert packet.delegation_run_ids == ["run-reader"]
    assert packet.artifact_ids == ["artifact-reader"]
    assert packet.proposal_ids == ["proposal-reader"]


@pytest.mark.asyncio
async def test_telemetry_reader_reads_trace_column_and_metadata_fallback(
    tmp_path: Path,
) -> None:
    telemetry_db = tmp_path / "telemetry.db"
    store = TelemetryPlaneStore(telemetry_db)

    async with correlation_scope(trace_id=TRACE_ID):
        await store.record_economic_event(
            EconomicEventRecord(
                event_id="econ-trace-column",
                event_kind="revenue",
                amount=1200.0,
                currency="USD",
                session_id="sess-reader",
                task_id="task-reader",
                run_id="run-reader",
                metadata={"value_event_id": "value-reader"},
            )
        )

    store.record_economic_event_sync(
        event_kind="revenue",
        amount=50.0,
        currency="USD",
        session_id="sess-reader",
        task_id="task-reader",
        run_id="run-reader",
        metadata={
            "trace_id": TRACE_ID,
            "value_event_id": "value-reader",
            "agent_id": "agent-reader",
        },
    )
    other_event = store.record_economic_event_sync(
        event_kind="revenue",
        amount=999.0,
        metadata={"trace_id": OTHER_TRACE_ID},
    )

    events = read_telemetry_events(telemetry_db, TRACE_ID)
    packet = TraceAttractorProjector().build_packet(
        TRACE_ID,
        events,
        generated_at="2026-05-05T00:00:00Z",
    )

    assert len(events) == 2
    assert packet.value_summary.economic_amount == 1250.0
    assert packet.economic_event_ids == sorted(packet.economic_event_ids)
    assert other_event.event_id not in packet.economic_event_ids
    assert OTHER_TRACE_ID not in packet.to_stable_json()


@pytest.mark.asyncio
async def test_store_reader_facade_feeds_projector_across_stores(
    tmp_path: Path,
) -> None:
    registry = _registry_with_trace_objects()
    runtime_db = tmp_path / "runtime.db"
    telemetry_db = tmp_path / "telemetry.db"
    runtime = RuntimeStateStore(runtime_db)
    telemetry = TelemetryPlaneStore(telemetry_db)

    async with correlation_scope(trace_id=TRACE_ID):
        await runtime.record_task_claim(
            TaskClaim(
                claim_id="claim-reader",
                task_id="task-reader",
                agent_id="agent-reader",
                session_id="sess-reader",
            )
        )
        await telemetry.record_economic_event(
            EconomicEventRecord(
                event_id="econ-reader",
                event_kind="revenue",
                amount=1200.0,
                currency="USD",
                task_id="task-reader",
                metadata={"value_event_id": "value-reader"},
            )
        )

    reader = TraceAttractorStoreReader(
        registry=registry,
        runtime_db_path=runtime_db,
        telemetry_db_path=telemetry_db,
    )
    events = reader.read_events(TRACE_ID)
    packet = TraceAttractorProjector().build_packet(
        TRACE_ID,
        events,
        generated_at="2026-05-05T00:00:00Z",
    )

    assert packet.task_ids == ["task-reader"]
    assert packet.claim_ids == ["claim-reader"]
    assert packet.value_summary.economic_amount == 1200.0
    assert packet.value_event_ids
    assert packet.proposal_ids


def test_readers_return_empty_for_missing_databases(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"

    assert read_runtime_events(missing, TRACE_ID) == []
    assert read_telemetry_events(missing, TRACE_ID) == []
    assert not missing.exists()


def test_board_reader_reads_trace_metadata(tmp_path: Path) -> None:
    board_db = tmp_path / "board.sqlite3"
    log = BoardEventLog(path=board_db)
    log.append(BoardEvent(
        kind="card_created",
        card_id=CardId("card-reader"),
        trace_id=TRACE_ID,
        trace_id_source="operator_supplied",
        detail={"task_id": "task-reader"},
    ))
    log.append(BoardEvent(
        kind="card_created",
        card_id=CardId("card-other"),
        trace_id=OTHER_TRACE_ID,
    ))

    events = read_board_events(board_db, TRACE_ID)
    packet = TraceAttractorProjector().build_packet(
        TRACE_ID,
        events,
        generated_at="2026-05-05T00:00:00Z",
    )

    assert len(events) == 1
    assert events[0].source_store == "boardstore"
    assert packet.trace_id_source == "operator_supplied"


def test_sakshi_reader_reads_trace_metadata(tmp_path: Path) -> None:
    sakshi_log = tmp_path / "sakshi.jsonl"
    log = ProvenanceLog(path=sakshi_log)
    log.append(ProvenanceEntry(
        actor_id="codex",
        actor_kind="codex",
        action="track_opened",
        target_ref="trace-attractor-causal-spine-2026-05",
        trace_id=TRACE_ID,
        trace_id_source="operator_supplied",
        track_id="trace-attractor-causal-spine-2026-05",
    ))
    log.append(ProvenanceEntry(
        actor_id="codex",
        actor_kind="codex",
        action="track_closed",
        trace_id=OTHER_TRACE_ID,
    ))

    events = read_sakshi_events(sakshi_log, TRACE_ID)
    packet = TraceAttractorProjector().build_packet(
        TRACE_ID,
        events,
        generated_at="2026-05-05T00:00:00Z",
    )

    assert len(events) == 1
    assert events[0].source_store == "sakshi"
    assert packet.lineage_edge_ids == [events[0].source_object_id]
