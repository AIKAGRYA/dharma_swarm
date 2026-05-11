"""Tests for Trace Attractor lifecycle findings detection.

Creates synthetic events representing orphan/inconsistent conditions and
verifies the pure projector assigns correct severity levels.
"""

from __future__ import annotations

import pytest

from dharma_swarm.trace_attractor.models import (
    AttractorEvent,
    FindingSeverity,
    LifecycleFinding,
)
from dharma_swarm.trace_attractor.projector import TraceAttractorProjector

TRACE_ID = "trc_lifecycle_test"
NOW = "2026-01-01T00:00:00Z"


def _event(
    *,
    event_id: str,
    source_type: str,
    event_type: str = "",
    attrs: dict | None = None,
) -> dict:
    return AttractorEvent(
        event_id=event_id,
        trace_id=TRACE_ID,
        source_store="test",
        source_table_or_type=source_type,
        source_object_id=event_id,
        event_type=event_type or source_type,
        occurred_at=NOW,
        attributes=attrs or {},
    ).model_dump(mode="json")


def test_orphan_outcome_finding():
    """Outcome without proposal_id -> finding."""
    events = [
        _event(event_id="orphan_out", source_type="Outcome"),
    ]
    projector = TraceAttractorProjector()
    packet = projector.build_packet(TRACE_ID, events)

    codes = [f.code for f in packet.lifecycle_findings]
    assert "orphan_outcome" in codes

    finding = next(f for f in packet.lifecycle_findings if f.code == "orphan_outcome")
    assert finding.severity == FindingSeverity.DEGRADED


def test_warrant_unknown_finding():
    """Trace with no gate decisions -> INFO warrant_unknown."""
    projector = TraceAttractorProjector()
    packet = projector.build_packet(TRACE_ID, [])

    codes = [f.code for f in packet.lifecycle_findings]
    assert "warrant_unknown" in codes

    finding = next(f for f in packet.lifecycle_findings if f.code == "warrant_unknown")
    assert finding.severity == FindingSeverity.INFO


def test_clean_gate_removes_warrant_unknown():
    """Trace with warrant evidence should not have warrant_unknown."""
    events = [
        _event(
            event_id="gate_001",
            source_type="GateDecisionRecord",
            attrs={"maheshwari": "pass"},
        ),
    ]
    projector = TraceAttractorProjector()
    packet = projector.build_packet(TRACE_ID, events)

    codes = [f.code for f in packet.lifecycle_findings]
    assert "warrant_unknown" not in codes
    assert packet.fourfold_warrant.maheshwari == "pass"


def test_severity_mapping():
    """Verify severity enum values."""
    assert FindingSeverity.INFO.value == "INFO"
    assert FindingSeverity.DEGRADED.value == "DEGRADED"
    assert FindingSeverity.BLOCKER.value == "BLOCKER"
