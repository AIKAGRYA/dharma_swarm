from __future__ import annotations

import pytest

from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    TopologyStateRecord,
)


async def _seed_runtime_graph(store: RuntimeStateStore) -> None:
    await store.record_delegation_run(
        DelegationRun(
            run_id="run-parent",
            session_id="sess-graph",
            task_id="task-graph",
            assigned_to="supervisor",
            assigned_by="operator",
            status="in_progress",
        )
    )
    await store.record_delegation_run(
        DelegationRun(
            run_id="run-child",
            session_id="sess-graph",
            task_id="task-graph",
            assigned_to="worker-a",
            assigned_by="supervisor",
            parent_run_id="run-parent",
            status="completed",
        )
    )
    await store.record_topology_state(
        TopologyStateRecord(
            run_id="run-parent",
            session_id="sess-graph",
            task_id="task-graph",
            topology="supervisor",
            active_agent="worker-a",
            current_node="worker-a",
            checkpoint_id="task-graph:supervisor:checkpoint-1",
            child_run_ids=["run-child"],
            allowed_handoffs={"supervisor": ["worker-a"]},
            handoff_receipts=[
                {
                    "status": "accepted",
                    "from_agent": "supervisor",
                    "to_agent": "worker-a",
                    "reason": "delegate scoped worker task",
                }
            ],
            state={"status": "in_progress", "visible_output_policy": "supervisor_final"},
        )
    )
    await store.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="receipt-topology",
            receipt_type="topology_state",
            run_id="run-parent",
            task_id="task-graph",
            agent_id="worker-a",
            status="persisted",
            payload={"checkpoint_id": "task-graph:supervisor:checkpoint-1"},
        )
    )


@pytest.mark.asyncio
async def test_operator_views_runtime_graph_surfaces_live_topology_state(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await _seed_runtime_graph(store)

    snapshot = await OperatorViews(store).runtime_graph(
        session_id="sess-graph",
        task_id="task-graph",
        limit=10,
        receipt_limit=10,
    )

    assert snapshot["schema_version"] == "runtime_graph_snapshot.v1"
    assert snapshot["summary"]["topology_state_count"] == 1
    assert snapshot["summary"]["run_count"] == 2
    assert snapshot["summary"]["active_run_count"] == 1
    assert snapshot["active_agents"] == ["worker-a"]
    assert snapshot["checkpoints"][0]["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"
    assert snapshot["topology_states"][0]["handoff_receipts"][0]["status"] == "accepted"
    assert snapshot["receipts"][0]["receipt_id"] == "receipt-topology"

    node_kinds = {node["kind"] for node in snapshot["nodes"]}
    edge_kinds = {edge["kind"] for edge in snapshot["edges"]}
    assert {"run", "agent", "topology", "checkpoint", "receipt"} <= node_kinds
    assert {"active_agent", "handoff", "parent_child", "checkpoint", "receipt"} <= edge_kinds


@pytest.mark.asyncio
async def test_runtime_graph_api_uses_configured_runtime_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    await _seed_runtime_graph(store)
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(db_path))

    from api.routers.runtime import runtime_graph

    response = await runtime_graph(
        session_id="sess-graph",
        task_id=None,
        topology=None,
        limit=10,
        receipt_limit=10,
    )

    assert response.status == "ok"
    assert response.error == ""
    assert response.data["runtime_db"] == str(db_path)
    assert response.data["topology_states"][0]["active_agent"] == "worker-a"


def test_runtime_graph_router_is_registered() -> None:
    from api.main import app

    paths = set(app.openapi().get("paths", {}))
    assert "/api/runtime/graph" in paths
