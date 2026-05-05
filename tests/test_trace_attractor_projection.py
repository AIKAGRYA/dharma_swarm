"""Tests for Trace Attractor Ledger projection.

Builds synthetic trace data across ontology, runtime state, and telemetry
stores, then verifies the projector assembles a stable AttractorPacket.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.trace_attractor.models import AttractorPacket, AttractorEvent
from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

TRACE_ID = "trc_test_projection_001"


class FakeOntologyObj:
    """Minimal stand-in for OntologyObj."""

    def __init__(self, *, obj_id: str, type_name: str, properties: dict, created_at=None):
        self.id = obj_id
        self.type_name = type_name
        self.properties = properties
        self.created_at = created_at or datetime.now(timezone.utc)


class FakeOntologyRegistry:
    """Minimal stand-in for OntologyRegistry."""

    def __init__(self, objects: list[FakeOntologyObj]):
        self._objects = objects

    def get_objects_by_type(self, type_name: str) -> list[FakeOntologyObj]:
        return [o for o in self._objects if o.type_name == type_name]


@pytest.fixture()
def ontology_with_trace():
    return FakeOntologyRegistry([
        FakeOntologyObj(
            obj_id="prop_001",
            type_name="ActionProposal",
            properties={"trace_id": TRACE_ID, "task_id": "task_a"},
        ),
        FakeOntologyObj(
            obj_id="gate_001",
            type_name="GateDecision",
            properties={"trace_id": TRACE_ID, "gate_name": "maheshwari_test", "decision": "pass"},
        ),
        FakeOntologyObj(
            obj_id="out_001",
            type_name="Outcome",
            properties={"trace_id": TRACE_ID, "proposal_id": "prop_001"},
        ),
        FakeOntologyObj(
            obj_id="ve_001",
            type_name="ValueEvent",
            properties={"trace_id": TRACE_ID, "outcome_id": "out_001", "task_type": "operator_brief"},
        ),
        FakeOntologyObj(
            obj_id="contrib_001",
            type_name="Contribution",
            properties={"trace_id": TRACE_ID, "agent_id": "agent_alpha"},
        ),
        # Object NOT in this trace — should be excluded
        FakeOntologyObj(
            obj_id="prop_other",
            type_name="ActionProposal",
            properties={"trace_id": "trc_OTHER"},
        ),
    ])


@pytest.fixture()
def runtime_db(tmp_path):
    """Create a temporary runtime_state DB with trace_id data."""
    import aiosqlite
    db_path = str(tmp_path / "runtime_state.db")

    async def _setup():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS task_claims ("
                " claim_id TEXT PRIMARY KEY, task_id TEXT, session_id TEXT,"
                " agent_id TEXT, status TEXT DEFAULT 'open', claimed_at TEXT,"
                " completed_at TEXT, retry_count INTEGER DEFAULT 0,"
                " metadata_json TEXT DEFAULT '{}', trace_id TEXT DEFAULT '')"
            )
            await db.execute(
                "INSERT INTO task_claims (claim_id, task_id, session_id, trace_id)"
                " VALUES (?, ?, ?, ?)",
                ("claim_001", "task_a", "sess_001", TRACE_ID),
            )
            await db.execute(
                "CREATE TABLE IF NOT EXISTS delegation_runs ("
                " run_id TEXT PRIMARY KEY, session_id TEXT, task_id TEXT,"
                " claim_id TEXT, parent_run_id TEXT, assigned_by TEXT,"
                " assigned_to TEXT, requested_output_json TEXT,"
                " current_artifact_id TEXT, status TEXT, started_at TEXT,"
                " completed_at TEXT, failure_code TEXT,"
                " metadata_json TEXT DEFAULT '{}', trace_id TEXT DEFAULT '')"
            )
            await db.execute(
                "INSERT INTO delegation_runs (run_id, session_id, task_id, trace_id, status, started_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                ("run_001", "sess_001", "task_a", TRACE_ID, "running", "2026-01-01T00:00:00Z"),
            )
            await db.execute(
                "CREATE TABLE IF NOT EXISTS artifact_records ("
                " artifact_id TEXT PRIMARY KEY, session_id TEXT, task_id TEXT,"
                " run_id TEXT, artifact_kind TEXT, manifest_path TEXT,"
                " payload_path TEXT, checksum TEXT, parent_artifact_id TEXT,"
                " promotion_state TEXT, created_at TEXT,"
                " metadata_json TEXT DEFAULT '{}')"
            )
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_setup())
    return db_path


@pytest.fixture()
def telemetry_db(tmp_path):
    """Create a temporary telemetry DB with trace_id data."""
    import aiosqlite
    db_path = str(tmp_path / "telemetry.db")

    async def _setup():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS economic_events ("
                " event_id TEXT PRIMARY KEY, session_id TEXT, task_id TEXT,"
                " run_id TEXT, event_kind TEXT, amount REAL, currency TEXT,"
                " counterparty TEXT, summary TEXT,"
                " metadata_json TEXT DEFAULT '{}', created_at TEXT,"
                " trace_id TEXT DEFAULT '')"
            )
            await db.execute(
                "INSERT INTO economic_events"
                " (event_id, session_id, task_id, amount, currency, created_at, trace_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("econ_001", "sess_001", "task_a", 42.50, "USD", "2026-01-01T00:00:00Z", TRACE_ID),
            )
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_setup())
    return db_path


class FakeRuntimeState:
    """Minimal stand-in for RuntimeStateStore."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        pass

    async def list_artifacts(self, limit: int = 500):
        return []


class FakeTelemetryPlane:
    """Minimal stand-in for TelemetryPlaneStore with _open()."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        pass

    def _open(self):
        import aiosqlite
        return aiosqlite.connect(self.db_path)


async def test_projection_assembles_complete_packet(ontology_with_trace, runtime_db, telemetry_db):
    projector = TraceAttractorProjector(
        ontology=ontology_with_trace,
        runtime_state=FakeRuntimeState(runtime_db),
        telemetry_plane=FakeTelemetryPlane(telemetry_db),
    )
    packet = await projector.project(TRACE_ID)

    assert packet.trace_id == TRACE_ID
    assert packet.schema_version == 1
    assert "prop_001" in packet.proposal_ids
    assert "gate_001" in packet.gate_decision_ids
    assert "out_001" in packet.outcome_ids
    assert "ve_001" in packet.value_event_ids
    assert "contrib_001" in packet.contribution_ids
    assert "claim_001" in packet.claim_ids
    assert "run_001" in packet.delegation_run_ids
    assert "econ_001" in packet.economic_event_ids
    # Excluded objects
    assert "prop_other" not in packet.proposal_ids


async def test_projection_json_is_stable(ontology_with_trace, runtime_db, telemetry_db):
    projector = TraceAttractorProjector(
        ontology=ontology_with_trace,
        runtime_state=FakeRuntimeState(runtime_db),
        telemetry_plane=FakeTelemetryPlane(telemetry_db),
    )

    packet1 = await projector.project(TRACE_ID)
    packet2 = await projector.project(TRACE_ID)

    d1 = packet1.to_dict()
    d2 = packet2.to_dict()

    # Remove generated_at (varies by call time)
    d1.pop("generated_at")
    d2.pop("generated_at")

    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


async def test_projection_empty_trace():
    projector = TraceAttractorProjector()
    packet = await projector.project("trc_nonexistent")

    assert packet.trace_id == "trc_nonexistent"
    assert len(packet.proposal_ids) == 0
    assert len(packet.events) == 0
    assert packet.fourfold_warrant.status == "unknown"


async def test_projection_value_summary(ontology_with_trace, runtime_db, telemetry_db):
    projector = TraceAttractorProjector(
        ontology=ontology_with_trace,
        runtime_state=FakeRuntimeState(runtime_db),
        telemetry_plane=FakeTelemetryPlane(telemetry_db),
    )
    packet = await projector.project(TRACE_ID)

    assert packet.value_summary.economic_amount == 42.50
    assert packet.value_summary.currency == "USD"
    assert packet.value_summary.task_count >= 1


async def test_projection_fourfold_warrant(ontology_with_trace, runtime_db, telemetry_db):
    projector = TraceAttractorProjector(
        ontology=ontology_with_trace,
        runtime_state=FakeRuntimeState(runtime_db),
        telemetry_plane=FakeTelemetryPlane(telemetry_db),
    )
    packet = await projector.project(TRACE_ID)

    assert packet.fourfold_warrant.maheshwari == "pass"
    assert "gate_001" in packet.fourfold_warrant.evidence_refs


async def test_projection_provenance_graph(ontology_with_trace, runtime_db, telemetry_db):
    projector = TraceAttractorProjector(
        ontology=ontology_with_trace,
        runtime_state=FakeRuntimeState(runtime_db),
        telemetry_plane=FakeTelemetryPlane(telemetry_db),
    )
    packet = await projector.project(TRACE_ID)

    graph = packet.provenance_graph
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0


async def test_human_summary():
    packet = AttractorPacket(
        trace_id="trc_test",
        proposal_ids=["p1"],
        task_ids=["t1", "t2"],
    )
    summary = packet.human_summary()
    assert "trc_test" in summary
    assert "proposals: 1" in summary
    assert "tasks: 2" in summary
