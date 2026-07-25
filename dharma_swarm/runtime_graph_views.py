"""Runtime graph read model backed by the canonical RuntimeStateStore."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    TopologyStateRecord,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _dt_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


class RuntimeGraphViews:
    """Operator-facing graph projection over persisted runtime topology state."""

    def __init__(self, runtime_state: RuntimeStateStore) -> None:
        self.runtime_state = runtime_state

    async def runtime_graph(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        topology: str | None = None,
        limit: int = 20,
        receipt_limit: int = 50,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        await self.runtime_state.init_db()
        topology_states = await self.runtime_state.list_topology_states(
            session_id=session_id,
            task_id=task_id,
            topology=topology,
            limit=max_items,
        )
        runs = await self.runtime_state.list_delegation_runs(
            session_id=session_id,
            task_id=task_id,
            limit=max_items,
        )
        runs_by_id = {run.run_id: run for run in runs}
        for state in topology_states:
            await self._include_run(runs_by_id, state.run_id)
            await self._include_run(runs_by_id, state.parent_run_id)
            for child_run_id in state.child_run_ids:
                await self._include_run(runs_by_id, child_run_id)

        receipts = await self._collect_graph_receipts(
            sorted(runs_by_id),
            limit=receipt_limit,
        )
        nodes, edges = self._build_graph_nodes_edges(
            topology_states,
            runs_by_id,
            receipts,
        )
        active_agents = sorted(
            {state.active_agent for state in topology_states if state.active_agent}
        )
        checkpoints = [
            {
                "checkpoint_id": state.checkpoint_id,
                "run_id": state.run_id,
                "task_id": state.task_id,
                "topology": state.topology,
                "active_agent": state.active_agent,
                "current_node": state.current_node,
                "updated_at": _dt_iso(state.updated_at),
            }
            for state in topology_states
            if state.checkpoint_id
        ]
        run_views = [self._run_to_dict(run) for run in runs_by_id.values()]
        receipt_views = [self._receipt_to_dict(receipt) for receipt in receipts]
        topology_views = [self._topology_to_dict(state) for state in topology_states]
        return {
            "schema_version": "runtime_graph_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {
                "session_id": session_id,
                "task_id": task_id,
                "topology": topology,
                "limit": max_items,
                "receipt_limit": max(1, receipt_limit),
            },
            "summary": {
                "topology_state_count": len(topology_views),
                "run_count": len(run_views),
                "active_run_count": sum(
                    1
                    for run in run_views
                    if run["status"] not in {"completed", "failed", "stale_recovered"}
                ),
                "receipt_count": len(receipt_views),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "checkpoint_count": len(checkpoints),
                "active_agent_count": len(active_agents),
            },
            "active_agents": active_agents,
            "checkpoints": checkpoints,
            "topology_states": topology_views,
            "runs": run_views,
            "receipts": receipt_views,
            "nodes": nodes,
            "edges": edges,
        }

    async def _include_run(self, runs_by_id: dict[str, DelegationRun], run_id: str) -> None:
        if not run_id or run_id in runs_by_id:
            return
        run = await self.runtime_state.get_delegation_run(run_id)
        if run is not None:
            runs_by_id[run.run_id] = run

    async def _collect_graph_receipts(
        self,
        run_ids: list[str],
        *,
        limit: int,
    ) -> list[RuntimeReceipt]:
        remaining = max(1, limit)
        receipts: list[RuntimeReceipt] = []
        per_run_limit = max(1, min(20, remaining))
        for run_id in run_ids:
            if len(receipts) >= remaining:
                break
            receipts.extend(
                await self.runtime_state.list_runtime_receipts(
                    run_id=run_id,
                    limit=per_run_limit,
                )
            )
        return receipts[:remaining]

    @classmethod
    def _build_graph_nodes_edges(
        cls,
        topology_states: list[TopologyStateRecord],
        runs_by_id: dict[str, DelegationRun],
        receipts: list[RuntimeReceipt],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        def add_node(node_id: str, kind: str, label: str, **extra: Any) -> None:
            if not node_id:
                return
            node = nodes.setdefault(node_id, {"id": node_id, "kind": kind, "label": label})
            node.update(extra)

        def add_edge(
            edge_id: str,
            kind: str,
            source: str,
            target: str,
            label: str,
            **extra: Any,
        ) -> None:
            if not source or not target:
                return
            edges.setdefault(
                edge_id,
                {
                    "id": edge_id,
                    "kind": kind,
                    "source": source,
                    "target": target,
                    "label": label,
                    **extra,
                },
            )

        for run in runs_by_id.values():
            run_node = f"run:{run.run_id}"
            add_node(
                run_node,
                "run",
                run.run_id,
                run_id=run.run_id,
                task_id=run.task_id,
                session_id=run.session_id,
                status=run.status,
                agent_id=run.assigned_to,
                parent_run_id=run.parent_run_id,
            )
            if run.assigned_to:
                agent_node = f"agent:{run.assigned_to}"
                add_node(agent_node, "agent", run.assigned_to, agent_id=run.assigned_to)
                add_edge(
                    f"assigned:{run.run_id}:{run.assigned_to}",
                    "assigned_to",
                    run_node,
                    agent_node,
                    "assigned_to",
                    run_id=run.run_id,
                )
            if run.parent_run_id:
                parent_node = f"run:{run.parent_run_id}"
                add_node(parent_node, "run", run.parent_run_id, run_id=run.parent_run_id)
                add_edge(
                    f"parent:{run.parent_run_id}:{run.run_id}",
                    "parent_child",
                    parent_node,
                    run_node,
                    "child_run",
                    parent_run_id=run.parent_run_id,
                    child_run_id=run.run_id,
                )

        for state in topology_states:
            cls._add_topology_graph(state, add_node, add_edge)

        for receipt in receipts:
            receipt_node = f"receipt:{receipt.receipt_id}"
            add_node(
                receipt_node,
                "receipt",
                receipt.receipt_type,
                run_id=receipt.run_id,
                receipt_id=receipt.receipt_id,
                status=receipt.status,
            )
            add_edge(
                f"receipt:{receipt.run_id}:{receipt.receipt_id}",
                "receipt",
                f"run:{receipt.run_id}",
                receipt_node,
                receipt.receipt_type,
                run_id=receipt.run_id,
                receipt_id=receipt.receipt_id,
            )

        return list(nodes.values()), list(edges.values())

    @staticmethod
    def _add_topology_graph(
        state: TopologyStateRecord,
        add_node: Any,
        add_edge: Any,
    ) -> None:
        run_node = f"run:{state.run_id}"
        topology_node = f"topology:{state.run_id}"
        add_node(
            run_node,
            "run",
            state.run_id,
            run_id=state.run_id,
            task_id=state.task_id,
            session_id=state.session_id,
            topology=state.topology,
        )
        add_node(
            topology_node,
            "topology",
            state.topology,
            run_id=state.run_id,
            topology=state.topology,
            task_id=state.task_id,
        )
        add_edge(
            f"topology:{state.run_id}",
            "has_topology",
            run_node,
            topology_node,
            state.topology,
            run_id=state.run_id,
        )
        RuntimeGraphViews._add_topology_agent_edges(
            state,
            run_node,
            topology_node,
            add_node,
            add_edge,
        )
        RuntimeGraphViews._add_topology_child_edges(state, run_node, add_edge)
        RuntimeGraphViews._add_handoff_edges(state, add_node, add_edge)

    @staticmethod
    def _add_topology_agent_edges(
        state: TopologyStateRecord,
        run_node: str,
        topology_node: str,
        add_node: Any,
        add_edge: Any,
    ) -> None:
        if state.active_agent:
            active_agent_node = f"agent:{state.active_agent}"
            add_node(
                active_agent_node,
                "agent",
                state.active_agent,
                agent_id=state.active_agent,
                active=True,
            )
            add_edge(
                f"active_agent:{state.run_id}:{state.active_agent}",
                "active_agent",
                run_node,
                active_agent_node,
                "active_agent",
                run_id=state.run_id,
            )
        if state.current_node:
            current_node = f"node:{state.run_id}:{state.current_node}"
            add_node(
                current_node,
                "topology_node",
                state.current_node,
                run_id=state.run_id,
                current=True,
            )
            add_edge(
                f"current_node:{state.run_id}:{state.current_node}",
                "current_node",
                topology_node,
                current_node,
                "current_node",
                run_id=state.run_id,
            )
        if state.checkpoint_id:
            checkpoint_node = f"checkpoint:{state.checkpoint_id}"
            add_node(
                checkpoint_node,
                "checkpoint",
                state.checkpoint_id,
                run_id=state.run_id,
                task_id=state.task_id,
                checkpoint_id=state.checkpoint_id,
                updated_at=_dt_iso(state.updated_at),
            )
            add_edge(
                f"checkpoint:{state.run_id}:{state.checkpoint_id}",
                "checkpoint",
                run_node,
                checkpoint_node,
                "checkpoint",
                run_id=state.run_id,
            )

    @staticmethod
    def _add_topology_child_edges(
        state: TopologyStateRecord,
        run_node: str,
        add_edge: Any,
    ) -> None:
        for child_run_id in state.child_run_ids:
            add_edge(
                f"topology_child:{state.run_id}:{child_run_id}",
                "parent_child",
                run_node,
                f"run:{child_run_id}",
                "child_run",
                parent_run_id=state.run_id,
                child_run_id=child_run_id,
            )

    @staticmethod
    def _add_handoff_edges(state: TopologyStateRecord, add_node: Any, add_edge: Any) -> None:
        for from_agent, to_agents in state.allowed_handoffs.items():
            from_node = f"agent:{from_agent}"
            add_node(from_node, "agent", from_agent, agent_id=from_agent)
            for to_agent in to_agents:
                to_node = f"agent:{to_agent}"
                add_node(to_node, "agent", to_agent, agent_id=to_agent)
                add_edge(
                    f"allowed_handoff:{state.run_id}:{from_agent}:{to_agent}",
                    "allowed_handoff",
                    from_node,
                    to_node,
                    "allowed_handoff",
                    run_id=state.run_id,
                )
        for index, receipt in enumerate(state.handoff_receipts):
            from_agent = str(receipt.get("from_agent") or "")
            to_agent = str(receipt.get("to_agent") or "")
            if from_agent and to_agent:
                add_edge(
                    f"handoff:{state.run_id}:{index}:{from_agent}:{to_agent}",
                    "handoff",
                    f"agent:{from_agent}",
                    f"agent:{to_agent}",
                    str(receipt.get("status") or "handoff"),
                    run_id=state.run_id,
                    metadata=receipt,
                )

    @staticmethod
    def _run_to_dict(run: DelegationRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "session_id": run.session_id,
            "task_id": run.task_id,
            "claim_id": run.claim_id,
            "parent_run_id": run.parent_run_id,
            "assigned_by": run.assigned_by,
            "assigned_to": run.assigned_to,
            "requested_output": run.requested_output,
            "current_artifact_id": run.current_artifact_id,
            "status": run.status,
            "started_at": _dt_iso(run.started_at),
            "completed_at": _dt_iso(run.completed_at),
            "failure_code": run.failure_code,
            "metadata": run.metadata,
        }

    @staticmethod
    def _topology_to_dict(state: TopologyStateRecord) -> dict[str, Any]:
        return {
            "schema_version": state.schema_version,
            "run_id": state.run_id,
            "session_id": state.session_id,
            "task_id": state.task_id,
            "topology": state.topology,
            "active_agent": state.active_agent,
            "current_node": state.current_node,
            "checkpoint_id": state.checkpoint_id,
            "parent_run_id": state.parent_run_id,
            "child_run_ids": state.child_run_ids,
            "allowed_handoffs": state.allowed_handoffs,
            "handoff_receipts": state.handoff_receipts,
            "state": state.state,
            "created_at": _dt_iso(state.created_at),
            "updated_at": _dt_iso(state.updated_at),
        }

    @staticmethod
    def _receipt_to_dict(receipt: RuntimeReceipt) -> dict[str, Any]:
        return {
            "receipt_id": receipt.receipt_id,
            "receipt_type": receipt.receipt_type,
            "run_id": receipt.run_id,
            "task_id": receipt.task_id,
            "trace_id": receipt.trace_id,
            "correlation_id": receipt.correlation_id,
            "causation_id": receipt.causation_id,
            "parent_run_id": receipt.parent_run_id,
            "agent_id": receipt.agent_id,
            "idempotency_key": receipt.idempotency_key,
            "side_effect_key": receipt.side_effect_key,
            "status": receipt.status,
            "payload": receipt.payload,
            "created_at": _dt_iso(receipt.created_at),
        }
