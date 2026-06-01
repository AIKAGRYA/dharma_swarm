from __future__ import annotations

import pytest

from contracts.typed_proposal_envelope import ProposalProvenance
from dharma_swarm.a2a.a2a_server import A2ATask
from dharma_swarm.evolution import Proposal
from dharma_swarm.models import Task, TaskDispatch
from dharma_swarm.runtime_state import ArtifactRecord, RuntimeReceipt
from dharma_swarm.spine.adapters import (
    adapt_execution_identity,
    identity_from_carrier,
    runtime_receipt_kwargs,
)
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


TRACE_ID = "trace-adapter-v2"
CORRELATION_ID = "corr-adapter-v2"
TASK_ID = "task-adapter-v2"
RUN_ID = "run-adapter-v2"
CLAIM_ID = "claim-adapter-v2"
IDEMPOTENCY_KEY = "idem-adapter-v2"
AGENT_ID = "agent-adapter-v2"
SESSION_ID = "session-adapter-v2"


def _identity(**overrides: str) -> ExecutionIdentity:
    payload = {
        "trace_id": TRACE_ID,
        "correlation_id": CORRELATION_ID,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "claim_id": CLAIM_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "agent_id": AGENT_ID,
        "session_id": SESSION_ID,
    }
    payload.update(overrides)
    return ExecutionIdentity.new(**payload)


def _assert_round_trip(carrier: object, surface: str, *, identity: ExecutionIdentity | None = None) -> object:
    expected = identity or _identity()
    _, adapted = adapt_execution_identity(carrier, surface=surface, task_id=expected.task_id)
    attached = identity_from_carrier(adapted, surface=surface, require_existing=True)
    assert attached.trace_id == expected.trace_id
    assert attached.correlation_id == expected.correlation_id
    assert attached.run_id == expected.run_id
    assert attached.claim_id == expected.claim_id
    assert attached.idempotency_key == expected.idempotency_key
    return adapted


def test_adapter_round_trips_taskboard_orchestrator_a2a_message_and_artifact_surfaces() -> None:
    identity = _identity(external_a2a_task_id="a2a-adapter-v2", message_id="msg-adapter-v2")

    task = Task(id=TASK_ID, title="adapter task", metadata=identity.to_metadata())
    _assert_round_trip(task, "taskboard", identity=identity)
    assert task.metadata["execution_identity"]["run_id"] == RUN_ID

    dispatch = TaskDispatch(task_id=TASK_ID, agent_id=AGENT_ID, metadata=identity.to_metadata())
    _assert_round_trip(dispatch, "orchestrator", identity=identity)
    assert dispatch.metadata["trace_id"] == TRACE_ID

    a2a_task = A2ATask(
        id="a2a-adapter-v2",
        to_agent=AGENT_ID,
        dharma_task_id=TASK_ID,
        metadata=identity.to_metadata(),
    )
    adapted_a2a = _assert_round_trip(a2a_task, "a2a", identity=identity)
    assert adapted_a2a.trace_id == TRACE_ID
    assert adapted_a2a.metadata["external_a2a_task_id"] == "a2a-adapter-v2"

    message_payload = {"event_id": "evt-adapter-v2", "metadata": identity.to_metadata()}
    adapted_message = _assert_round_trip(message_payload, "message_bus", identity=identity)
    assert adapted_message["metadata"]["run_id"] == RUN_ID

    artifact = ArtifactRecord(
        artifact_id="artifact-adapter-v2",
        artifact_kind="test",
        task_id=TASK_ID,
        metadata=identity.to_metadata(),
    )
    adapted_artifact = _assert_round_trip(artifact, "artifact", identity=identity)
    assert adapted_artifact.trace_id == TRACE_ID
    assert adapted_artifact.run_id == RUN_ID


def test_adapter_round_trips_tools_ontology_checkpoints_and_self_mod_proposals() -> None:
    identity = _identity(proposal_id="proposal-adapter-v2")

    tool_call = {
        "tool_call_id": "tool-call-adapter-v2",
        "tool_name": "safe_probe",
        "metadata": identity.to_metadata(),
    }
    adapted_tool = _assert_round_trip(tool_call, "tool", identity=identity)
    assert adapted_tool["metadata"]["execution_identity_surface"] == "tool"

    ontology_action = {
        "object_type": "ActionProposal",
        "object_id": "proposal-adapter-v2",
        "action_name": "Approve",
        "executed_by": AGENT_ID,
        "metadata": identity.to_metadata(),
    }
    adapted_action = _assert_round_trip(ontology_action, "ontology_action", identity=identity)
    assert adapted_action["metadata"]["proposal_id"] == "proposal-adapter-v2"

    checkpoint = {
        "checkpoint_id": "checkpoint-adapter-v2",
        "cycle_id": "cycle-adapter-v2",
        "metadata": identity.to_metadata(),
    }
    adapted_checkpoint = _assert_round_trip(checkpoint, "graph_checkpoint", identity=identity)
    assert adapted_checkpoint["metadata"]["trace_id"] == TRACE_ID

    proposal = Proposal(
        id="proposal-adapter-v2",
        component="dharma_swarm/orchestrator.py",
        change_type="mutation",
        description="adapter-ready proposal",
        metadata=identity.to_metadata(),
    )
    _assert_round_trip(proposal, "self_mod_proposal", identity=identity)
    assert proposal.metadata["proposal_id"] == "proposal-adapter-v2"

    provenance = ProposalProvenance(
        agent=AGENT_ID,
        callsign="adapter-v2",
        branch="codex/runtime-truth-spine-v2",
        rationale="adapter test",
    )
    provenance_payload = provenance.model_dump()
    provenance_payload["metadata"] = identity.to_metadata()
    adapted_provenance = _assert_round_trip(provenance_payload, "proposal", identity=identity)
    assert adapted_provenance["metadata"]["run_id"] == RUN_ID


def test_adapter_can_generate_identity_for_legacy_carriers_but_required_boundaries_fail() -> None:
    legacy_dispatch = TaskDispatch(task_id=TASK_ID, agent_id=AGENT_ID)
    identity, adapted = adapt_execution_identity(legacy_dispatch, surface="orchestrator")
    assert identity.task_id == TASK_ID
    assert identity.agent_id == AGENT_ID
    assert adapted.metadata["execution_identity"]["task_id"] == TASK_ID

    with pytest.raises(MissingExecutionIdentity):
        identity_from_carrier(Task(id=TASK_ID, title="missing"), surface="taskboard", require_existing=True)


def test_adapter_receipt_kwargs_are_runtime_receipt_compatible() -> None:
    identity = _identity()
    receipt = RuntimeReceipt(
        **runtime_receipt_kwargs(
            identity,
            receipt_type="side_effect_intent",
            status="started",
            side_effect_key="tool:safe_probe",
            payload={"surface": "tool"},
        )
    )
    assert receipt.run_id == RUN_ID
    assert receipt.trace_id == TRACE_ID
    assert receipt.correlation_id == CORRELATION_ID
    assert receipt.idempotency_key == IDEMPOTENCY_KEY
    assert receipt.side_effect_key == "tool:safe_probe"
