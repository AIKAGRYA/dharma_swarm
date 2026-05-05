from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.audit_queries import (
    blocked_action_audits,
    lifecycle_audit_report,
    lifecycle_chain_audit,
    lifecycle_chain_audits,
    lifecycle_link_gaps,
    proposal_to_outcome_chain,
    recent_blocks,
    unrecorded_actions,
)
from dharma_swarm.ontology import OntologyObj
from dharma_swarm.ontology_runtime import (
    get_shared_registry,
    persist_shared_registry,
    reset_shared_registry,
)


@pytest.fixture(autouse=True)
def isolated_ontology(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_ONTOLOGY_PATH", str(tmp_path / "ontology.db"))
    reset_shared_registry()
    yield
    reset_shared_registry()


def test_recent_blocks_filters_gate_decision_records_by_window() -> None:
    registry = get_shared_registry()
    recent = _gate(registry, decision="block", reason="AHIMSA blocked")
    _gate(registry, decision="allow", reason="ok")
    old = _gate(registry, decision="block", reason="old block")
    old.created_at = datetime.now(timezone.utc) - timedelta(days=9)
    old.updated_at = old.created_at
    persist_shared_registry(registry)

    rows = recent_blocks(days=7)

    assert [row["id"] for row in rows] == [recent.id]
    assert rows[0]["properties"]["decision"] == "block"


def test_unrecorded_actions_returns_proposals_without_gate_link() -> None:
    registry = get_shared_registry()
    gap = _proposal(registry, title="Needs gate")
    linked = _proposal(registry, title="Has gate")
    gate = _gate(registry, proposal_id=linked.id, decision="allow")
    link, errors = registry.create_link(
        "has_gate_decision",
        source_id=linked.id,
        target_id=gate.id,
    )
    assert link is not None, errors
    persist_shared_registry(registry)

    rows = unrecorded_actions(days=7)

    assert [row["id"] for row in rows] == [gap.id]
    assert rows[0]["properties"]["title"] == "Needs gate"


def test_proposal_to_outcome_chain_walks_metabolic_links() -> None:
    registry = get_shared_registry()
    proposal = _proposal(registry, title="Full chain")
    gate = _gate(registry, proposal_id=proposal.id, decision="allow")
    lease = _lease(registry, proposal.id)
    outcome = _outcome(registry, proposal.id)
    value = _value_event(registry, outcome.id)
    contribution = _contribution(registry, value.id)
    for link_name, source, target in (
        ("has_gate_decision", proposal, gate),
        ("has_execution_lease", proposal, lease),
        ("has_outcome", proposal, outcome),
        ("has_value_event", outcome, value),
        ("has_contribution", value, contribution),
    ):
        link, errors = registry.create_link(link_name, source.id, target.id)
        assert link is not None, errors
    persist_shared_registry(registry)

    chain = proposal_to_outcome_chain(proposal.id)

    assert chain["proposal"]["id"] == proposal.id
    assert chain["gate_decision"]["id"] == gate.id
    assert chain["execution_lease"]["id"] == lease.id
    assert chain["outcome"]["id"] == outcome.id
    assert chain["value_event"]["id"] == value.id
    assert [row["id"] for row in chain["contributions"]] == [contribution.id]


def test_lifecycle_chain_audit_marks_complete_chain() -> None:
    registry = get_shared_registry()
    proposal = _proposal(registry, title="Complete chain")
    gate = _gate(registry, proposal_id=proposal.id, decision="allow")
    outcome = _outcome(registry, proposal.id)
    value = _value_event(registry, outcome.id)
    contribution = _contribution(registry, value.id)
    for link_name, source, target in (
        ("has_gate_decision", proposal, gate),
        ("has_outcome", proposal, outcome),
        ("has_value_event", outcome, value),
        ("has_contribution", value, contribution),
    ):
        link, errors = registry.create_link(link_name, source.id, target.id)
        assert link is not None, errors
    persist_shared_registry(registry)

    row = lifecycle_chain_audit(proposal.id)

    assert row["status"] == "complete"
    assert row["decision"] == "allow"
    assert row["missing"] == []
    assert row["action_type"] == "dispatch"
    assert row["task_id"] == "task-Complete chain"
    assert row["agent_id"] == "agent-audit"
    assert row["title"] == "Complete chain"
    assert row["has_execution_lease"] is False
    assert row["refs"]["proposal"] == f"ActionProposal/{proposal.id}"
    assert row["refs"]["outcome"] == f"Outcome/{outcome.id}"
    assert row["refs"]["contributions"] == [f"Contribution/{contribution.id}"]
    assert row["brief"]["section"] == "Lifecycle Signals"
    assert row["brief"]["outcome_id"] == outcome.id


def test_lifecycle_audit_report_counts_missing_stages_and_blocks() -> None:
    registry = get_shared_registry()

    complete = _proposal(registry, title="Complete")
    complete_gate = _gate(registry, proposal_id=complete.id, decision="allow")
    complete_outcome = _outcome(registry, complete.id)
    complete_value = _value_event(registry, complete_outcome.id)
    complete_contribution = _contribution(registry, complete_value.id)

    missing_contribution = _proposal(registry, title="Missing contribution")
    missing_contribution_gate = _gate(
        registry,
        proposal_id=missing_contribution.id,
        decision="allow",
    )
    missing_contribution_outcome = _outcome(registry, missing_contribution.id)
    missing_contribution_value = _value_event(
        registry,
        missing_contribution_outcome.id,
    )

    blocked_without_outcome = _proposal(registry, title="Blocked")
    blocked_gate = _gate(
        registry,
        proposal_id=blocked_without_outcome.id,
        decision="block",
        reason="blocked by test",
    )

    for link_name, source, target in (
        ("has_gate_decision", complete, complete_gate),
        ("has_outcome", complete, complete_outcome),
        ("has_value_event", complete_outcome, complete_value),
        ("has_contribution", complete_value, complete_contribution),
        ("has_gate_decision", missing_contribution, missing_contribution_gate),
        ("has_outcome", missing_contribution, missing_contribution_outcome),
        ("has_value_event", missing_contribution_outcome, missing_contribution_value),
        ("has_gate_decision", blocked_without_outcome, blocked_gate),
    ):
        link, errors = registry.create_link(link_name, source.id, target.id)
        assert link is not None, errors
    persist_shared_registry(registry)

    report = lifecycle_audit_report(days=7, limit=2)

    assert report["schema_version"] == "telic_lifecycle_audit.v1"
    assert report["generated_at"]
    assert report["cutoff_at"]
    assert report["total_proposals"] == 3
    assert report["complete_chains"] == 1
    assert report["incomplete_chains"] == 2
    assert report["blocked_chains"] == 1
    assert report["missing_gate_decision"] == 0
    assert report["missing_outcome"] == 1
    assert report["missing_value_event"] == 1
    assert report["missing_contribution"] == 2
    assert report["with_execution_lease"] == 0
    assert report["link_gaps"] == 0
    assert report["by_action_type"] == {"dispatch": 3}
    assert len(report["chains"]) == 2

    blocked_rows = [
        row for row in lifecycle_chain_audits(days=7) if row["decision"] == "block"
    ]
    assert len(blocked_rows) == 1
    assert blocked_rows[0]["status"] == "incomplete"
    assert blocked_rows[0]["missing"] == [
        "outcome",
        "value_event",
        "contribution",
    ]
    assert blocked_rows[0]["brief"]["section"] == "Gate Blocks"


def test_lifecycle_link_gaps_reports_property_only_missing_edges() -> None:
    registry = get_shared_registry()
    proposal = _proposal(registry, title="Property-only complete")
    gate = _gate(registry, proposal_id=proposal.id, decision="allow")
    outcome = _outcome(registry, proposal.id)
    value = _value_event(registry, outcome.id)
    contribution = _contribution(registry, value.id)
    persist_shared_registry(registry)

    chain = proposal_to_outcome_chain(proposal.id)
    audit = lifecycle_chain_audit(proposal.id)
    gaps = lifecycle_link_gaps(days=7)

    assert chain["gate_decision"]["id"] == gate.id
    assert chain["outcome"]["id"] == outcome.id
    assert chain["value_event"]["id"] == value.id
    assert [row["id"] for row in chain["contributions"]] == [contribution.id]
    assert audit["status"] == "complete"
    assert audit["missing"] == []
    assert {
        (row["link_name"], row["source_id"], row["target_id"])
        for row in gaps
    } == {
        ("has_gate_decision", proposal.id, gate.id),
        ("has_outcome", proposal.id, outcome.id),
        ("has_value_event", outcome.id, value.id),
        ("has_contribution", value.id, contribution.id),
    }


def test_unrecorded_actions_ignores_property_resolved_gate_records() -> None:
    registry = get_shared_registry()
    proposal = _proposal(registry, title="Gate without link")
    gate = _gate(registry, proposal_id=proposal.id, decision="allow")
    persist_shared_registry(registry)

    rows = unrecorded_actions(days=7)
    gaps = lifecycle_link_gaps(days=7)

    assert proposal.id not in [row["id"] for row in rows]
    assert gaps == [
        {
            "proposal_id": proposal.id,
            "link_name": "has_gate_decision",
            "source_id": proposal.id,
            "source_type": "ActionProposal",
            "target_id": gate.id,
            "target_type": "GateDecisionRecord",
        }
    ]


def test_blocked_action_audits_returns_complete_failed_chain() -> None:
    registry = get_shared_registry()
    proposal = _proposal(registry, title="Blocked but recorded")
    gate = _gate(
        registry,
        proposal_id=proposal.id,
        decision="block",
        reason="Telos block: blocked for audit test",
    )
    outcome = _outcome(
        registry,
        proposal.id,
        success=False,
        error="Telos block: blocked for audit test",
    )
    value = _value_event(registry, outcome.id, success=False)
    contribution = _contribution(registry, value.id)
    for link_name, source, target in (
        ("has_gate_decision", proposal, gate),
        ("has_outcome", proposal, outcome),
        ("has_value_event", outcome, value),
        ("has_contribution", value, contribution),
    ):
        link, errors = registry.create_link(link_name, source.id, target.id)
        assert link is not None, errors
    persist_shared_registry(registry)

    rows = blocked_action_audits(days=7)

    assert len(rows) == 1
    assert rows[0]["proposal_id"] == proposal.id
    assert rows[0]["decision"] == "block"
    assert rows[0]["status"] == "complete"
    assert rows[0]["missing"] == []
    assert rows[0]["refs"]["outcome"] == f"Outcome/{outcome.id}"
    assert rows[0]["brief"]["section"] == "Gate Blocks"
    assert rows[0]["brief"]["outcome_id"] == outcome.id


def test_dgc_audit_gates_dispatches_through_main(capsys) -> None:
    registry = get_shared_registry()
    _proposal(registry, title="Ungated CLI proposal")
    _gate(registry, decision="block", reason="CLI block")
    persist_shared_registry(registry)

    from dharma_swarm.dgc_cli import main

    assert main(["audit", "gates", "--days", "7"]) == 0
    output = capsys.readouterr().out
    assert "Governance gate audit (7d)" in output
    assert "Recent blocks: 1" in output
    assert "Ungated proposals: 1" in output
    assert "Lifecycle chains:" in output
    assert "Ontology link gaps:" in output
    assert "Ungated CLI proposal" in output


def _proposal(registry, *, title: str = "Proposal") -> OntologyObj:
    obj, errors = registry.create_object(
        "ActionProposal",
        {
            "task_id": f"task-{title}",
            "agent_id": "agent-audit",
            "action_type": "dispatch",
            "title": title,
            "description": "audit fixture",
            "status": "proposed",
            "priority": "normal",
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _gate(
    registry,
    *,
    proposal_id: str = "proposal-test",
    decision: str = "block",
    reason: str = "blocked",
) -> OntologyObj:
    obj, errors = registry.create_object(
        "GateDecisionRecord",
        {
            "proposal_id": proposal_id,
            "decision": decision,
            "reason": reason,
            "gate_results": {"AHIMSA": {"result": "FAIL", "reason": reason}},
            "witness_reroutes": 0,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _lease(registry, proposal_id: str) -> OntologyObj:
    obj, errors = registry.create_object(
        "ExecutionLease",
        {
            "proposal_id": proposal_id,
            "claim_id": "claim-1",
            "agent_id": "agent-audit",
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "claim_timeout_seconds": 30.0,
            "claim_expires_at_epoch": 0.0,
            "dispatch_timeout_seconds": 60.0,
            "dispatch_attempt": 1,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _outcome(
    registry,
    proposal_id: str,
    *,
    success: bool = True,
    error: str = "",
) -> OntologyObj:
    obj, errors = registry.create_object(
        "Outcome",
        {
            "proposal_id": proposal_id,
            "task_id": "task-chain",
            "agent_id": "agent-audit",
            "success": success,
            "result_summary": "done",
            "error": error,
            "duration_ms": 10.0,
            "fitness_score": 0.8,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _value_event(registry, outcome_id: str, *, success: bool = True) -> OntologyObj:
    obj, errors = registry.create_object(
        "ValueEvent",
        {
            "outcome_id": outcome_id,
            "agent_id": "agent-audit",
            "cell_id": "",
            "task_id": "task-chain",
            "task_type": "general",
            "behavioral_signal": 0.5,
            "success_value": 1.0 if success else 0.0,
            "duration_efficiency": 1.0,
            "composite_value": 0.8,
            "scoring_method": "test",
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _contribution(registry, value_event_id: str) -> OntologyObj:
    obj, errors = registry.create_object(
        "Contribution",
        {
            "value_event_id": value_event_id,
            "agent_id": "agent-audit",
            "cell_id": "",
            "task_type": "general",
            "credit_share": 1.0,
            "attributed_value": 0.8,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj
