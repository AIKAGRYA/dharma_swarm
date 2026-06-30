"""Runtime platform read surfaces backed by the canonical RuntimeStateStore."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeStateStore,
    SessionEventRecord,
    SessionState,
    TopologyStateRecord,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _serialize_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


class RuntimePlatformViews:
    """LangGraph-style control-plane projections over persisted runtime state."""

    def __init__(self, runtime_state: RuntimeStateStore) -> None:
        self.runtime_state = runtime_state

    async def runtime_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        sessions = await asyncio.to_thread(
            self.runtime_state.list_sessions_sync,
            status=status,
            limit=max_items,
        )
        session_views = [self._session_to_dict(session) for session in sessions]
        return {
            "schema_version": "runtime_sessions_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {"status": status, "limit": max_items},
            "summary": {
                "session_count": len(session_views),
                "active_session_count": sum(
                    1 for session in session_views if session["status"] == "active"
                ),
            },
            "sessions": session_views,
        }

    async def runtime_runs(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        runs = await self.runtime_state.list_delegation_runs(
            session_id=session_id,
            task_id=task_id,
            status=status,
            limit=max_items,
        )
        run_views = [await self._run_summary(run) for run in runs]
        return {
            "schema_version": "runtime_runs_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {
                "session_id": session_id,
                "task_id": task_id,
                "status": status,
                "limit": max_items,
            },
            "summary": {
                "run_count": len(run_views),
                "active_run_count": sum(
                    1
                    for run in run_views
                    if run["status"] not in {"completed", "failed", "stale_recovered"}
                ),
            },
            "runs": run_views,
        }

    async def runtime_run_detail(self, run_id: str) -> dict[str, Any]:
        detail = await self.runtime_state.describe_run(run_id)
        found = detail.get("run") is not None
        serialized = _serialize_value(detail)
        return {
            "schema_version": "runtime_run_detail.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "run_id": run_id,
            "found": found,
            "summary": {
                "artifact_count": len(serialized.get("artifacts") or []),
                "receipt_count": len(serialized.get("receipts") or []),
                "mapping_count": len(serialized.get("mappings") or []),
                "child_run_count": len(serialized.get("children") or []),
                "idempotency_record_count": len(
                    serialized.get("idempotency_records") or []
                ),
                "has_topology_state": serialized.get("topology_state") is not None,
                "has_identity": serialized.get("identity") is not None,
            },
            "detail": serialized,
        }

    async def runtime_checkpoints(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        topology: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        states = await self.runtime_state.list_topology_states(
            session_id=session_id,
            task_id=task_id,
            topology=topology,
            limit=max_items,
        )
        checkpoints = [
            self._checkpoint_to_dict(state)
            for state in states
            if state.checkpoint_id
        ]
        return {
            "schema_version": "runtime_checkpoint_history.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {
                "session_id": session_id,
                "task_id": task_id,
                "topology": topology,
                "limit": max_items,
            },
            "summary": {
                "topology_state_count": len(states),
                "checkpoint_count": len(checkpoints),
            },
            "checkpoints": checkpoints,
        }

    async def runtime_events(
        self,
        *,
        session_id: str | None = None,
        ledger_kind: str | None = None,
        event_name: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        events = await self.runtime_state.list_session_events(
            session_id=session_id,
            ledger_kind=ledger_kind,
            event_name=event_name,
            limit=max_items,
        )
        event_views = [self._event_to_dict(event) for event in events]
        return {
            "schema_version": "runtime_events_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {
                "session_id": session_id,
                "ledger_kind": ledger_kind,
                "event_name": event_name,
                "limit": max_items,
            },
            "summary": {"event_count": len(event_views)},
            "events": event_views,
        }

    async def _run_summary(self, run: DelegationRun) -> dict[str, Any]:
        run_view = _serialize_value(run)
        topology_state = await self.runtime_state.get_topology_state(run.run_id)
        if topology_state is not None:
            run_view["topology"] = topology_state.topology
            run_view["active_agent"] = topology_state.active_agent
            run_view["current_node"] = topology_state.current_node
            run_view["checkpoint_id"] = topology_state.checkpoint_id
            run_view["child_run_ids"] = list(topology_state.child_run_ids)
            run_view["topology_updated_at"] = topology_state.updated_at.isoformat()
        return run_view

    @staticmethod
    def _session_to_dict(session: SessionState) -> dict[str, Any]:
        return _serialize_value(session)

    @staticmethod
    def _event_to_dict(event: SessionEventRecord) -> dict[str, Any]:
        return _serialize_value(event)

    @staticmethod
    def _checkpoint_to_dict(state: TopologyStateRecord) -> dict[str, Any]:
        return {
            "checkpoint_id": state.checkpoint_id,
            "run_id": state.run_id,
            "session_id": state.session_id,
            "task_id": state.task_id,
            "topology": state.topology,
            "active_agent": state.active_agent,
            "current_node": state.current_node,
            "parent_run_id": state.parent_run_id,
            "child_run_ids": list(state.child_run_ids),
            "allowed_handoffs": _serialize_value(state.allowed_handoffs),
            "handoff_receipts": _serialize_value(state.handoff_receipts),
            "state": _serialize_value(state.state),
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
        }
