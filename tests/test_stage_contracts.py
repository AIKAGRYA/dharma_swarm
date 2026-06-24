"""Tests for the Slice A CONTEXT.md stage-contract reader.

Correctness here is STRUCTURAL: does the folder become the right DAG, does a
stage route through spine.invoke_agent, does the receipt's routing carry the
stage provenance. None of that needs a live model — a fake AgentInvoker keeps
the test hermetic and fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.fs_substrate import (
    StageContract,
    WorkspaceError,
    load_workspace,
    parse_context_md,
    to_tasks,
)
from dharma_swarm.fs_substrate.stage_executor import (
    assemble_input_context,
    dispatch_stage,
)
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

WORKSPACE = Path(__file__).parent / "fixtures" / "fs_substrate" / "sample_workspace"


class _FakeInvoker:
    """A hermetic AgentInvoker that echoes the routing provenance into the receipt.

    Real invokers (orchestrator, A2A) build the receipt from the routing
    decision the same way; this fake demonstrates the join cheaply.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, task, agent_id, context_id, routing: RoutingDecision):
        self.calls.append(
            {"task": task, "agent_id": agent_id, "context_id": context_id, "routing": routing}
        )
        return EvidenceReceipt(
            agent_id=agent_id,
            context_id=context_id,
            task_id=routing.task_id,
            routing_decision_id=routing.decision_id,
            status="ok",
            attributes=dict(routing.attributes),
        )


def test_parse_minimal_stage_contract():
    contract = parse_context_md(
        (WORKSPACE / "stages" / "01-scope" / "CONTEXT.md").read_text(),
        str(WORKSPACE / "stages" / "01-scope" / "CONTEXT.md"),
    )
    assert isinstance(contract, StageContract)
    assert contract.stage_id == "01-scope"
    assert contract.order == 1
    assert contract.agent_role == "architect"
    assert contract.type == "stage"
    assert [i.source for i in contract.inputs] == ["operator ask"]
    assert len(contract.process) == 3
    assert contract.outputs[0].location == "./output/scope.md"
    assert len(contract.contract_sha256) == 64


def test_missing_section_fails_closed():
    with pytest.raises(WorkspaceError):
        parse_context_md("---\nstage: 99-broken\n---\n## Inputs\n", "/x/99-broken/CONTEXT.md")


def test_load_workspace_sorted_by_order():
    ws = load_workspace(WORKSPACE)
    assert [s.stage_id for s in ws.stages] == ["01-scope", "02-research", "03-synthesize"]


def test_to_tasks_derives_depends_on_dag():
    ws = load_workspace(WORKSPACE)
    tasks = to_tasks(ws)
    by_stage = {t.metadata["stage_id"]: t for t in tasks}

    # 01-scope has no inputs from a sibling -> no deps.
    assert by_stage["01-scope"].depends_on == []
    # 02-research reads ../01-scope/output/ -> explicit edge to 01-scope.
    assert by_stage["02-research"].depends_on == [by_stage["01-scope"].id]
    # 03-synthesize reads ../02-research/output/ -> explicit edge to 02-research.
    assert by_stage["03-synthesize"].depends_on == [by_stage["02-research"].id]
    # Provenance is stamped on every task.
    assert all(len(t.metadata["stage_contract_sha256"]) == 64 for t in tasks)


def test_cycle_is_rejected():
    a = StageContract(
        stage_id="01-a", order=1, path="/w/stages/01-a/CONTEXT.md",
        inputs=[], process=["x"], outputs=[],
    )
    from dharma_swarm.fs_substrate.stage_contracts import StageInput, StageWorkspace

    a.inputs = [StageInput(source="b", location="../02-b/output/")]
    b = StageContract(
        stage_id="02-b", order=2, path="/w/stages/02-b/CONTEXT.md",
        inputs=[StageInput(source="a", location="../01-a/output/")],
        process=["y"], outputs=[],
    )
    with pytest.raises(WorkspaceError):
        to_tasks(StageWorkspace(root="/w", stages=[a, b]))


def test_input_path_traversal_rejected():
    from dharma_swarm.fs_substrate.stage_contracts import StageInput, StageWorkspace

    evil = StageContract(
        stage_id="01-evil",
        order=1,
        path=str(WORKSPACE / "stages" / "01-evil" / "CONTEXT.md"),
        inputs=[StageInput(source="x", location="../../../../../../etc/passwd")],
        process=["x"],
        outputs=[],
    )
    with pytest.raises(WorkspaceError):
        to_tasks(StageWorkspace(root=str(WORKSPACE), stages=[evil]))


def test_assemble_input_context_is_bounded_to_inputs():
    ws = load_workspace(WORKSPACE)
    scope = next(s for s in ws.stages if s.stage_id == "01-scope")
    ctx = assemble_input_context(scope)
    # Only the declared input (brief.md) is present.
    assert "filesystem-native context helps the swarm" in ctx
    assert "Input: operator ask" in ctx


async def test_dispatch_stage_calls_invoke_agent():
    ws = load_workspace(WORKSPACE)
    scope = next(s for s in ws.stages if s.stage_id == "01-scope")
    invoker = _FakeInvoker()

    receipt = await dispatch_stage(scope, invoker=invoker, context_id="ctx-1")

    # It went through the spine path exactly once.
    assert len(invoker.calls) == 1
    call = invoker.calls[0]
    assert call["context_id"] == "ctx-1"
    # The routing decision carries stage provenance...
    assert call["routing"].attributes["stage_id"] == "01-scope"
    assert len(call["routing"].attributes["stage_contract_sha256"]) == 64
    # ...and the receipt joins back to that routing decision.
    assert receipt.routing_decision_id == call["routing"].decision_id
    assert receipt.attributes["stage_id"] == "01-scope"
    assert receipt.status == "ok"
