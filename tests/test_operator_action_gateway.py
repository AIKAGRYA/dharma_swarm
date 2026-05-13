from __future__ import annotations

import pytest

from dharma_swarm.operator_action_gateway import ACTION_GATEWAY_VERSION, OperatorActionGateway
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import RuntimeStateStore


@pytest.mark.asyncio
async def test_submit_proposal_issues_warrant_and_session_event(tmp_path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    gateway = OperatorActionGateway(runtime)

    result = await gateway.submit_proposal(
        action_name="mcp.create_task",
        actor="mcp",
        reason="Create a governed task",
        payload={"title": "Ship the operator bus"},
        session_id="sess-action",
        source="mcp_server",
        target="swarm.create_task",
        risk="medium",
        approval_required=False,
    )

    action = await runtime.get_operator_action(result.action.action_id)
    events = await runtime.list_session_events(session_id="sess-action", limit=10)

    assert action is not None
    assert action.payload["version"] == ACTION_GATEWAY_VERSION
    assert action.payload["lifecycle"]["status"] == "warrant_issued"
    assert action.payload["lifecycle"]["executable"] is True
    assert action.payload["warrant"]["state"] == "issued"
    assert action.payload["request"]["title"] == "Ship the operator bus"
    assert events[0].event_name == "operator_action.warrant_issued"
    assert events[0].payload["runtime_action_id"] == action.action_id


@pytest.mark.asyncio
async def test_submit_proposal_requires_approval_for_high_risk(tmp_path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    gateway = OperatorActionGateway(runtime)

    result = await gateway.submit_proposal(
        action_name="external.email_send",
        actor="agent",
        reason="Send outbound customer email",
        payload={"to": "founder@example.com"},
        session_id="sess-review",
        source="revenue_spine",
        target="gmail.send",
        risk="high",
    )
    views = OperatorViews(runtime)
    pending = await views.pending_operator_actions(session_id="sess-review", limit=5)

    assert result.action.payload["lifecycle"]["status"] == "waiting_approval"
    assert result.action.payload["warrant"]["state"] == "pending_approval"
    assert pending[0]["action_id"] == result.action.action_id
    assert pending[0]["risk"] == "high"


@pytest.mark.asyncio
async def test_record_approval_resolution_updates_target_and_records_resolution(tmp_path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    gateway = OperatorActionGateway(runtime)
    proposal = await gateway.submit_proposal(
        action_name="publish.substack",
        actor="agent",
        reason="Publish a reviewed post",
        payload={"slug": "operator-brief"},
        session_id="sess-approval",
        source="ginko",
        target="substack",
        risk="high",
    )

    result = await gateway.record_approval_resolution(
        proposal.action.action_id,
        resolution="approved",
        actor="operator",
        summary="approved publish.substack",
        session_id="sess-approval",
    )
    target = await runtime.get_operator_action(proposal.action.action_id)
    approval = await runtime.get_operator_action(result["runtime_action_id"])
    events = await runtime.list_session_events(session_id="sess-approval", limit=10)

    assert result["outcome"] == "runtime_applied"
    assert result["target_found"] is True
    assert target is not None
    assert target.payload["lifecycle"]["status"] == "approved"
    assert target.payload["warrant"]["state"] == "issued"
    assert approval is not None
    assert approval.action_name == "approval.resolve"
    assert any(event.event_name == "approval.resolve.runtime_applied" for event in events)


@pytest.mark.asyncio
async def test_record_outcome_consumes_warrant(tmp_path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    gateway = OperatorActionGateway(runtime)
    proposal = await gateway.submit_proposal(
        action_name="mcp.spawn_agent",
        actor="mcp",
        reason="Spawn reviewer",
        payload={"name": "reviewer"},
        source="mcp_server",
        target="swarm.spawn_agent",
        approval_required=False,
    )

    outcome = await gateway.record_outcome(
        proposal.action.action_id,
        status="executed",
        outcome={"agent_id": "agent-1"},
    )

    assert outcome.action.payload["lifecycle"]["status"] == "executed"
    assert outcome.action.payload["warrant"]["state"] == "consumed"
    assert outcome.event.event_name == "operator_action.executed"
