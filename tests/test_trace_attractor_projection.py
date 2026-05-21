"""Tests for pure Trace Attractor Ledger projection contracts."""

from __future__ import annotations

from dharma_swarm.trace_attractor import (
    AttractorEvent,
    FindingSeverity,
    TraceAttractorProjector,
)


FIXED_AT = "2026-05-05T00:00:00Z"


def _event(
    event_id: str,
    *,
    source_store: str,
    source_type: str,
    source_object_id: str,
    event_type: str,
    trace_id: str = "trc-main",
    proposal_id: str = "",
    session_id: str = "sess-main",
    occurred_at: str = FIXED_AT,
    **attributes: object,
) -> AttractorEvent:
    return AttractorEvent(
        event_id=event_id,
        trace_id=trace_id,
        proposal_id=proposal_id,
        session_id=session_id,
        source_store=source_store,
        source_table_or_type=source_type,
        source_object_id=source_object_id,
        event_type=event_type,
        subject=source_object_id,
        occurred_at=occurred_at,
        attributes=dict(attributes),
    )


def test_projector_builds_stable_packet_from_synthetic_cross_substrate_trace() -> None:
    events = [
        _event(
            "evt-econ",
            source_store="telemetry_plane",
            source_type="economic_events",
            source_object_id="econ-1",
            event_type="economic_event_recorded",
            task_id="task-1",
            run_id="run-1",
            value_event_id="ve-1",
            amount=1200.0,
            currency="USD",
            agent_id="agent-a",
        ),
        _event(
            "evt-value-signal",
            source_store="signal_bus",
            source_type="VALUE_EVENT_RECORDED",
            source_object_id="sig-ve-1",
            event_type="value_event_recorded",
            outcome_id="outcome-1",
            value_event_id="ve-1",
            composite_value=0.82,
            agent_id="agent-a",
        ),
        _event(
            "evt-claim",
            source_store="runtime_state",
            source_type="task_claims",
            source_object_id="claim-1",
            event_type="task_claim_recorded",
            task_id="task-1",
            claim_id="claim-1",
            agent_id="agent-a",
        ),
        _event(
            "evt-run",
            source_store="runtime_state",
            source_type="delegation_runs",
            source_object_id="run-1",
            event_type="delegation_run_recorded",
            task_id="task-1",
            claim_id="claim-1",
            run_id="run-1",
            agent_id="agent-a",
        ),
        _event(
            "evt-proposal",
            source_store="ontology",
            source_type="ActionProposal",
            source_object_id="proposal-1",
            event_type="action_proposal_recorded",
            proposal_id="proposal-1",
            task_id="task-1",
        ),
        _event(
            "evt-gate",
            source_store="ontology",
            source_type="GateDecisionRecord",
            source_object_id="gate-1",
            event_type="gate_decision_recorded",
            proposal_id="proposal-1",
            gate_decision_id="gate-1",
        ),
        _event(
            "evt-artifact",
            source_store="runtime_state",
            source_type="artifact_records",
            source_object_id="artifact-1",
            event_type="artifact_recorded",
            task_id="task-1",
            run_id="run-1",
            artifact_id="artifact-1",
            manifest_path="reports/witness/trace.md",
            checksum="sha256:abc",
        ),
        _event(
            "evt-outcome",
            source_store="ontology",
            source_type="Outcome",
            source_object_id="outcome-1",
            event_type="outcome_recorded",
            proposal_id="proposal-1",
            task_id="task-1",
            outcome_id="outcome-1",
            agent_id="agent-a",
        ),
        _event(
            "evt-contribution",
            source_store="ontology",
            source_type="Contribution",
            source_object_id="contrib-1",
            event_type="contribution_recorded",
            value_event_id="ve-1",
            contribution_id="contrib-1",
            agent_id="agent-a",
        ),
        _event(
            "evt-warrant",
            source_store="governance",
            source_type="FourfoldActionWarrant",
            source_object_id="warrant-1",
            event_type="fourfold_warrant_recorded",
            status="pass",
            maheshwari="pass",
            mahakali="hold",
            mahalakshmi="pass",
            mahasaraswati="pass",
        ),
        _event(
            "evt-other-trace",
            source_store="ontology",
            source_type="Outcome",
            source_object_id="outcome-other",
            event_type="outcome_recorded",
            trace_id="trc-other",
            outcome_id="outcome-other",
        ),
    ]

    projector = TraceAttractorProjector()
    packet = projector.build_packet("trc-main", reversed(events), generated_at=FIXED_AT)
    again = projector.build_packet("trc-main", events, generated_at=FIXED_AT)

    assert packet.to_stable_json() == again.to_stable_json()
    assert packet.trace_id == "trc-main"
    assert packet.proposal_ids == ["proposal-1"]
    assert packet.gate_decision_ids == ["gate-1"]
    assert packet.task_ids == ["task-1"]
    assert packet.claim_ids == ["claim-1"]
    assert packet.delegation_run_ids == ["run-1"]
    assert packet.artifact_ids == ["artifact-1"]
    assert packet.outcome_ids == ["outcome-1"]
    assert packet.value_event_ids == ["ve-1"]
    assert packet.contribution_ids == ["contrib-1"]
    assert packet.economic_event_ids == ["econ-1"]
    assert packet.signal_event_ids == ["evt-value-signal"]
    assert packet.value_summary.composite_value == 0.82
    assert packet.value_summary.economic_amount == 1200.0
    assert packet.value_summary.agent_count == 1
    assert packet.value_summary.artifact_count == 1
    assert packet.value_summary.task_count == 1
    assert packet.fourfold_warrant.status == "pass"
    assert "outcome-other" not in packet.to_stable_json()


def test_projector_emits_lifecycle_findings_from_normalized_events() -> None:
    events = [
        _event(
            "evt-orphan-outcome",
            source_store="ontology",
            source_type="Outcome",
            source_object_id="outcome-orphan",
            event_type="outcome_recorded",
            outcome_id="outcome-orphan",
        ),
        _event(
            "evt-orphan-ve",
            source_store="ontology",
            source_type="ValueEvent",
            source_object_id="ve-orphan",
            event_type="value_event_recorded",
            value_event_id="ve-orphan",
            composite_value=0.2,
        ),
        _event(
            "evt-bare-artifact",
            source_store="runtime_state",
            source_type="artifact_records",
            source_object_id="artifact-bare",
            event_type="artifact_recorded",
            artifact_id="artifact-bare",
        ),
        _event(
            "evt-econ-unlinked",
            source_store="telemetry_plane",
            source_type="economic_events",
            source_object_id="econ-unlinked",
            event_type="economic_event_recorded",
            amount=50.0,
            currency="USD",
        ),
    ]

    packet = TraceAttractorProjector().build_packet(
        "trc-main",
        events,
        generated_at=FIXED_AT,
    )

    findings = {finding.code: finding for finding in packet.lifecycle_findings}
    assert findings["orphan_outcome"].severity == FindingSeverity.DEGRADED.value
    assert findings["orphan_value_event"].severity == FindingSeverity.DEGRADED.value
    assert findings["artifact_without_manifest"].severity == FindingSeverity.DEGRADED.value
    assert findings["economic_without_value_event"].severity == FindingSeverity.BLOCKER.value
    assert findings["warrant_unknown"].severity == FindingSeverity.INFO.value


def test_attractor_event_maps_to_cloudevent_envelope() -> None:
    event = _event(
        "evt-signal",
        source_store="signal_bus",
        source_type="VALUE_EVENT_RECORDED",
        source_object_id="sig-1",
        event_type="value_event_recorded",
        proposal_id="proposal-1",
        value_event_id="ve-1",
    )

    envelope = event.to_cloudevent()

    assert envelope["specversion"] == "1.0"
    assert envelope["id"] == "evt-signal"
    assert envelope["source"] == "dharma://signal_bus/VALUE_EVENT_RECORDED"
    assert envelope["type"] == "dev.dharma.value_event_recorded"
    assert envelope["subject"] == "sig-1"
    assert envelope["data"]["trace_id"] == "trc-main"
    assert envelope["data"]["proposal_id"] == "proposal-1"
    assert envelope["data"]["value_event_id"] == "ve-1"


def test_packet_jsonld_stub_keeps_projection_data() -> None:
    packet = TraceAttractorProjector().build_packet(
        "trc-main",
        [_event(
            "evt-proposal",
            source_store="ontology",
            source_type="ActionProposal",
            source_object_id="proposal-1",
            event_type="action_proposal_recorded",
        )],
        generated_at=FIXED_AT,
    )

    jsonld = packet.to_jsonld_stub()

    assert jsonld["@id"] == "dharma:trace/trc-main"
    assert jsonld["@type"] == "dharma:AttractorPacket"
    assert jsonld["@context"]["prov"] == "http://www.w3.org/ns/prov#"
    assert jsonld["proposal_ids"] == ["proposal-1"]


def test_empty_trace_packet_is_stable_and_read_only() -> None:
    packet = TraceAttractorProjector().build_packet(
        "trc-empty",
        [],
        generated_at=FIXED_AT,
    )

    assert packet.to_dict()["trace_id"] == "trc-empty"
    assert packet.to_dict()["generated_at"] == FIXED_AT
    assert packet.value_summary.composite_value == 0.0
    assert packet.provenance_graph.nodes == []
    assert packet.provenance_graph.edges == []
    assert [finding.code for finding in packet.lifecycle_findings] == ["warrant_unknown"]
