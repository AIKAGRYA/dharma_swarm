"""Topology runtime helpers for orchestrator and lifecycle persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dharma_swarm.models import TaskDispatch, _new_id
from dharma_swarm.runtime_state import DelegationRun, RuntimeReceipt, TopologyStateRecord
from dharma_swarm.spine.identity import ExecutionIdentity


def string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value if str(item)]


def dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def handoff_map(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {str(key): string_list(targets) for key, targets in value.items()}


def topology_value(td: TaskDispatch, topology_state: dict[str, Any]) -> str:
    topology = str(topology_state.get("mode") or "").strip()
    if topology:
        return topology
    value = getattr(td.topology, "value", td.topology)
    return str(value or "").strip()


def resolve_swarm_handoff(
    *,
    active_before: str,
    known_agent_ids: set[str],
    allowed_before: list[str],
    requested_handoff: str,
    handoff_reason: str,
    checkpoint_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    requested = requested_handoff.strip()
    if not requested:
        return active_before, []
    status = "accepted" if requested in known_agent_ids and requested in allowed_before else "rejected"
    return (
        requested if status == "accepted" else active_before,
        [
            {
                "status": status,
                "from_agent": active_before,
                "to_agent": requested,
                "reason": handoff_reason,
                "checkpoint_id": checkpoint_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )


def swarm_dispatch_metadata(
    *,
    active_agent: str,
    active_before: str,
    allowed_before: list[str],
    allowed_targets: list[str],
    requested_handoff: str,
    handoff_receipts: list[dict[str, Any]],
    checkpoint_id: str,
    topology_mode: str,
) -> dict[str, Any]:
    allowed_handoffs = {active_before: allowed_before}
    allowed_handoffs[active_agent] = allowed_targets
    topology_state = {
        "mode": topology_mode,
        "active_agent": active_agent,
        "current_node": active_agent,
        "allowed_handoffs": allowed_handoffs,
        "handoff_receipts": handoff_receipts,
    }
    return {
        "active_agent": active_agent,
        "current_node": active_agent,
        "allowed_handoffs": allowed_handoffs,
        "requested_handoff": requested_handoff,
        "handoff_receipts": handoff_receipts,
        "checkpoint_id": checkpoint_id,
        "topology_state": topology_state,
    }


def subagent_tool_metadata(
    *,
    parent_agent_id: str,
    child_agent_ids: list[str],
    checkpoint_id: str,
    topology_mode: str,
) -> dict[str, Any]:
    tool_names = [f"call_{agent_id}" for agent_id in child_agent_ids]
    child_run_ids = [f"run_{_new_id()}" for _ in child_agent_ids]
    parent_graph_state = {
        "mode": topology_mode,
        "parent_agent_id": parent_agent_id,
        "child_agent_ids": child_agent_ids,
        "child_run_ids": child_run_ids,
    }
    return {
        "active_agent": parent_agent_id,
        "current_node": parent_agent_id,
        "child_agent_ids": child_agent_ids,
        "child_run_ids": child_run_ids,
        "child_run_map": dict(zip(child_agent_ids, child_run_ids, strict=False)),
        "subagent_tool_names": tool_names,
        "checkpoint_id": checkpoint_id,
        "parent_graph_state": parent_graph_state,
        "topology_state": {
            "mode": topology_mode,
            "active_agent": parent_agent_id,
            "child_run_ids": child_run_ids,
            "subagent_tool_names": tool_names,
        },
    }


def build_topology_state_record(
    *,
    identity: ExecutionIdentity,
    td: TaskDispatch,
    task_meta: dict[str, Any],
    session_id: str,
    status: str,
) -> TopologyStateRecord | None:
    raw_topology_state = td.metadata.get("topology_state")
    topology_state = dict(raw_topology_state) if isinstance(raw_topology_state, dict) else {}
    topology = topology_value(td, topology_state)
    if topology not in {"swarm", "supervisor", "subagents_as_tools"}:
        return None

    raw_parent_graph = td.metadata.get("parent_graph_state")
    parent_graph_state = dict(raw_parent_graph) if isinstance(raw_parent_graph, dict) else {}
    child_run_ids = string_list(
        td.metadata.get("child_run_ids")
        or parent_graph_state.get("child_run_ids")
        or topology_state.get("child_run_ids")
    )
    state = dict(topology_state)
    state["status"] = status
    if parent_graph_state:
        state["parent_graph_state"] = parent_graph_state
    active_agent = str(
        td.metadata.get("active_agent") or topology_state.get("active_agent") or td.agent_id
    )
    current_node = str(
        td.metadata.get("current_node") or topology_state.get("current_node") or active_agent
    )
    now = datetime.now(timezone.utc)
    return TopologyStateRecord(
        run_id=identity.run_id,
        session_id=session_id,
        task_id=td.task_id,
        topology=topology,
        active_agent=active_agent,
        current_node=current_node,
        checkpoint_id=str(td.metadata.get("checkpoint_id") or topology_state.get("checkpoint_id") or ""),
        parent_run_id=str(
            identity.parent_run_id
            or td.metadata.get("parent_run_id")
            or task_meta.get("parent_run_id")
            or ""
        ),
        child_run_ids=child_run_ids,
        allowed_handoffs=handoff_map(
            td.metadata.get("allowed_handoffs") or topology_state.get("allowed_handoffs")
        ),
        handoff_receipts=dict_list(
            td.metadata.get("handoff_receipts") or topology_state.get("handoff_receipts")
        ),
        state=state,
        created_at=now,
        updated_at=now,
    )


async def record_topology_state(
    *,
    store: Any,
    identity: ExecutionIdentity,
    td: TaskDispatch,
    task_meta: dict[str, Any],
    session_id: str,
    status: str,
) -> TopologyStateRecord | None:
    record = build_topology_state_record(
        identity=identity,
        td=td,
        task_meta=task_meta,
        session_id=session_id,
        status=status,
    )
    if record is None:
        return None
    await store.record_topology_state(record)
    await _record_topology_state_receipt(store, identity, record, status)
    for idx, handoff in enumerate(record.handoff_receipts):
        await _record_topology_handoff_receipt(store, identity, handoff, idx, status)
    return record


async def record_subagent_tool_children(
    *,
    store: Any,
    identity: ExecutionIdentity,
    td: TaskDispatch,
    session_id: str,
    status: str,
    started_at: datetime,
    mission: dict[str, Any],
    route_payload: dict[str, Any],
) -> None:
    raw_topology_state = td.metadata.get("topology_state")
    topology_state = dict(raw_topology_state) if isinstance(raw_topology_state, dict) else {}
    if topology_value(td, topology_state) != "subagents_as_tools" or status not in {"claimed", "running"}:
        return
    child_agent_ids = string_list(td.metadata.get("child_agent_ids"))
    if not child_agent_ids:
        return
    child_run_ids = _ensure_child_run_ids(td, child_agent_ids)
    child_status = "queued" if status == "claimed" else "running"
    for index, child_agent_id in enumerate(child_agent_ids):
        child_run_id = child_run_ids[index]
        await store.record_delegation_run(
            DelegationRun(
                run_id=child_run_id,
                task_id=td.task_id,
                assigned_to=child_agent_id,
                status=child_status,
                session_id=session_id,
                parent_run_id=identity.run_id,
                assigned_by=td.agent_id,
                started_at=started_at,
                metadata=_child_metadata(
                    identity=identity,
                    td=td,
                    child_agent_id=child_agent_id,
                    child_index=index,
                    mission=mission,
                    route_payload=route_payload,
                ),
            )
        )
        await _record_child_spawned_receipt(store, identity, td, child_run_id, child_agent_id, child_status)


def _ensure_child_run_ids(td: TaskDispatch, child_agent_ids: list[str]) -> list[str]:
    raw_parent_graph = td.metadata.get("parent_graph_state")
    parent_graph_state = dict(raw_parent_graph) if isinstance(raw_parent_graph, dict) else {}
    child_run_ids = string_list(td.metadata.get("child_run_ids") or parent_graph_state.get("child_run_ids"))
    while len(child_run_ids) < len(child_agent_ids):
        child_run_ids.append(f"run_{_new_id()}")
    td.metadata["child_run_ids"] = child_run_ids
    parent_graph_state["child_run_ids"] = child_run_ids
    td.metadata["parent_graph_state"] = parent_graph_state
    if isinstance(td.metadata.get("topology_state"), dict):
        td.metadata["topology_state"]["child_run_ids"] = child_run_ids
    return child_run_ids


def _child_metadata(
    *,
    identity: ExecutionIdentity,
    td: TaskDispatch,
    child_agent_id: str,
    child_index: int,
    mission: dict[str, Any],
    route_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "topology": "subagents_as_tools",
        "topology_role": "subagent_tool",
        "parent_run_id": identity.run_id,
        "parent_agent_id": td.agent_id,
        "parent_execution_identity": identity.to_dict(),
        "child_index": child_index,
        "subagent_tool_name": f"call_{child_agent_id}",
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
    } | route_payload | mission


async def _record_topology_state_receipt(
    store: Any,
    identity: ExecutionIdentity,
    record: TopologyStateRecord,
    status: str,
) -> None:
    await store.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id=f"rr_{identity.run_id}_{status}_topology_state",
            receipt_type="topology_state",
            status=status,
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=f"topology_state:{identity.run_id}:{status}",
            payload={
                "topology": record.topology,
                "active_agent": record.active_agent,
                "current_node": record.current_node,
                "checkpoint_id": record.checkpoint_id,
                "child_run_ids": record.child_run_ids,
                "allowed_handoffs": record.allowed_handoffs,
                "handoff_count": len(record.handoff_receipts),
                "state": record.state,
                "receipt_status": status,
            },
        )
    )


async def _record_topology_handoff_receipt(
    store: Any,
    identity: ExecutionIdentity,
    handoff: dict[str, Any],
    idx: int,
    status: str,
) -> None:
    await store.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id=f"rr_{identity.run_id}_{status}_topology_handoff_{idx}",
            receipt_type="topology_handoff",
            status=str(handoff.get("status") or status),
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=f"topology_handoff:{identity.run_id}:{idx}",
            payload=handoff,
        )
    )


async def _record_child_spawned_receipt(
    store: Any,
    identity: ExecutionIdentity,
    td: TaskDispatch,
    child_run_id: str,
    child_agent_id: str,
    child_status: str,
) -> None:
    await store.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id=f"rr_{identity.run_id}_{child_run_id}_{child_status}_child_spawned",
            receipt_type="child_spawned",
            status=child_status,
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            agent_id=td.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=f"child:{identity.run_id}:{child_run_id}",
            payload={
                "child_run_id": child_run_id,
                "parent_run_id": identity.run_id,
                "assigned_to": child_agent_id,
                "child_status": child_status,
                "topology": "subagents_as_tools",
            },
        )
    )
