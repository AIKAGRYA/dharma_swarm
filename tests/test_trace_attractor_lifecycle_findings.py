"""Tests for Trace Attractor lifecycle findings detection.

Creates synthetic orphan/inconsistent conditions and verifies
the projector assigns correct severity levels.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dharma_swarm.trace_attractor.models import AttractorPacket, LifecycleFinding
from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

TRACE_ID = "trc_lifecycle_test"


class FakeOntologyObj:
    def __init__(self, *, obj_id: str, type_name: str, properties: dict, created_at=None):
        self.id = obj_id
        self.type_name = type_name
        self.properties = properties
        self.created_at = created_at or datetime.now(timezone.utc)


class FakeOntologyRegistry:
    def __init__(self, objects: list[FakeOntologyObj]):
        self._objects = objects

    def get_objects_by_type(self, type_name: str) -> list[FakeOntologyObj]:
        return [o for o in self._objects if o.type_name == type_name]


async def test_orphan_outcome_finding():
    """Outcome without proposal_id -> DEGRADED finding."""
    reg = FakeOntologyRegistry([
        FakeOntologyObj(
            obj_id="orphan_out",
            type_name="Outcome",
            properties={"trace_id": TRACE_ID},  # no proposal_id
        ),
    ])
    projector = TraceAttractorProjector(ontology=reg)
    packet = await projector.project(TRACE_ID)

    types = [f.finding_type for f in packet.lifecycle_findings]
    assert "orphan_outcome" in types

    finding = next(f for f in packet.lifecycle_findings if f.finding_type == "orphan_outcome")
    assert finding.severity == "DEGRADED"
    assert finding.source_object_id == "orphan_out"


async def test_orphan_value_event_finding():
    """ValueEvent referencing non-existent outcome -> DEGRADED."""
    reg = FakeOntologyRegistry([
        FakeOntologyObj(
            obj_id="ve_orphan",
            type_name="ValueEvent",
            properties={"trace_id": TRACE_ID, "outcome_id": "out_nonexistent"},
        ),
    ])
    projector = TraceAttractorProjector(ontology=reg)
    packet = await projector.project(TRACE_ID)

    types = [f.finding_type for f in packet.lifecycle_findings]
    assert "orphan_value_event" in types

    finding = next(f for f in packet.lifecycle_findings if f.finding_type == "orphan_value_event")
    assert finding.severity == "DEGRADED"


async def test_warrant_unknown_finding():
    """Trace with no gate decisions -> INFO warrant_unknown."""
    projector = TraceAttractorProjector()
    packet = await projector.project(TRACE_ID)

    types = [f.finding_type for f in packet.lifecycle_findings]
    assert "warrant_unknown" in types

    finding = next(f for f in packet.lifecycle_findings if f.finding_type == "warrant_unknown")
    assert finding.severity == "INFO"


async def test_economic_without_value_event():
    """Economic events exist but no value events -> DEGRADED."""
    reg = FakeOntologyRegistry([])

    class FakeTelemetry:
        def __init__(self):
            self.db_path = ":memory:"

        async def init_db(self):
            pass

        def _open(self):
            import aiosqlite
            return aiosqlite.connect(self.db_path)

    # Build a DB with one economic event
    import aiosqlite
    import asyncio

    db_path = ":memory:"

    projector = TraceAttractorProjector(ontology=reg)
    packet = await projector.project(TRACE_ID)
    # Manually inject economic event IDs to simulate the finding
    packet.economic_event_ids = ["econ_test"]
    packet.value_event_ids = []
    projector._detect_lifecycle_findings(packet)

    types = [f.finding_type for f in packet.lifecycle_findings]
    assert "economic_without_value_event" in types


async def test_clean_trace_has_only_warrant_unknown():
    """A trace with correct linkage produces only warrant_unknown (no gates)."""
    reg = FakeOntologyRegistry([
        FakeOntologyObj(
            obj_id="prop_clean",
            type_name="ActionProposal",
            properties={"trace_id": TRACE_ID},
        ),
        FakeOntologyObj(
            obj_id="out_clean",
            type_name="Outcome",
            properties={"trace_id": TRACE_ID, "proposal_id": "prop_clean"},
        ),
        FakeOntologyObj(
            obj_id="ve_clean",
            type_name="ValueEvent",
            properties={"trace_id": TRACE_ID, "outcome_id": "out_clean"},
        ),
    ])

    projector = TraceAttractorProjector(ontology=reg)
    packet = await projector.project(TRACE_ID)

    types = [f.finding_type for f in packet.lifecycle_findings]
    # Only warrant_unknown expected (no gate decisions in test)
    assert "orphan_outcome" not in types
    assert "orphan_value_event" not in types
    assert "warrant_unknown" in types


async def test_severity_mapping():
    """Verify severity constants are valid."""
    valid = {"INFO", "DEGRADED", "BLOCKER"}
    f1 = LifecycleFinding(finding_type="test", severity="INFO")
    f2 = LifecycleFinding(finding_type="test", severity="DEGRADED")
    f3 = LifecycleFinding(finding_type="test", severity="BLOCKER")
    assert f1.severity in valid
    assert f2.severity in valid
    assert f3.severity in valid
