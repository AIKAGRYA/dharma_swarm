from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.audit_queries import (
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


def _outcome(registry, proposal_id: str) -> OntologyObj:
    obj, errors = registry.create_object(
        "Outcome",
        {
            "proposal_id": proposal_id,
            "task_id": "task-chain",
            "agent_id": "agent-audit",
            "success": True,
            "result_summary": "done",
            "error": "",
            "duration_ms": 10.0,
            "fitness_score": 0.8,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def _value_event(registry, outcome_id: str) -> OntologyObj:
    obj, errors = registry.create_object(
        "ValueEvent",
        {
            "outcome_id": outcome_id,
            "agent_id": "agent-audit",
            "cell_id": "",
            "task_id": "task-chain",
            "task_type": "general",
            "behavioral_signal": 0.5,
            "success_value": 1.0,
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
