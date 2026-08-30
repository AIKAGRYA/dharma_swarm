"""Runtime platform read surfaces backed by the canonical RuntimeStateStore."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.runtime_activity import load_runtime_activity
from dharma_swarm.runtime_control_actions import RuntimeControlActions
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


def _event_payload(event: SessionEventRecord) -> dict[str, Any]:
    return dict(event.payload) if isinstance(event.payload, dict) else {}


def _is_control_event(event: SessionEventRecord) -> bool:
    name = event.event_name.lower()
    payload = _event_payload(event)
    keys = {str(key).lower() for key in payload}
    control_keys = {
        "approval_id",
        "approval_status",
        "human_approval_required",
        "interrupt_id",
        "requires_human",
        "resume_token",
    }
    return (
        "interrupt" in name
        or "resume" in name
        or "approval" in name
        or bool(keys & control_keys)
    )


def _control_type(event: SessionEventRecord) -> str:
    name = event.event_name.lower()
    payload = _event_payload(event)
    if "interrupt" in name:
        return "interrupt"
    if "resume" in name:
        return "resume"
    if "approval" in name or payload.get("approval_id") or payload.get("approval_status"):
        return "human_approval"
    if payload.get("resume_token"):
        return "resume"
    return "interrupt"


def _control_status(event: SessionEventRecord) -> str:
    payload = _event_payload(event)
    explicit = payload.get("approval_status") or payload.get("status") or payload.get("decision")
    if explicit:
        return str(explicit)
    name = event.event_name.lower()
    if "reject" in name or "denied" in name:
        return "rejected"
    if "grant" in name or "approve" in name:
        return "approved"
    if "resume" in name:
        return "resumed"
    if "resolve" in name:
        return "resolved"
    if "request" in name or "required" in name:
        return "pending"
    return "unknown"


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
        activity = load_runtime_activity(self.runtime_state.db_path)
        current_session_ids = activity.current_session_ids
        session_views = []
        for session in sessions:
            session_view = self._session_to_dict(session)
            session_view["activity"] = {
                "semantics": activity.semantics,
                "current_lease": session.session_id in current_session_ids,
                "stored_status": session.status,
                "proves_executor_liveness": False,
            }
            session_views.append(session_view)
        return {
            "schema_version": "runtime_sessions_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {"status": status, "limit": max_items},
            "summary": {
                "session_count": len(session_views),
                "active_session_count": sum(
                    1
                    for session in session_views
                    if session["activity"]["current_lease"]
                ),
                "stored_active_session_count": sum(
                    1 for session in session_views if session["status"] == "active"
                ),
                "activity_semantics": activity.semantics,
                "proves_executor_liveness": False,
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
        activity = load_runtime_activity(
            self.runtime_state.db_path,
            run_ids=tuple(run.run_id for run in runs),
        )
        activity_by_run = activity.by_run_id
        activity_summary = activity.summary()
        run_views = []
        for run in runs:
            observation = activity_by_run.get(run.run_id)
            observed_run = observation.run_record if observation is not None else run
            run_views.append(await self._run_summary(observed_run, observation))
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
                "active_run_count": activity_summary["current_lease_run_count"],
                "current_lease_run_count": activity_summary[
                    "current_lease_run_count"
                ],
                "observed_nonterminal_run_count": activity_summary[
                    "observed_nonterminal_run_count"
                ],
                "expired_or_unproven_run_count": activity_summary[
                    "expired_or_unproven_run_count"
                ],
                "terminal_evidence_conflict_count": activity_summary[
                    "terminal_evidence_conflict_count"
                ],
                "activity_semantics": activity.semantics,
                "proves_executor_liveness": False,
            },
            "runs": run_views,
        }

    async def runtime_run_detail(self, run_id: str) -> dict[str, Any]:
        detail = await self.runtime_state.describe_run(run_id)
        found = detail.get("run") is not None
        serialized = _serialize_value(detail)
        activity = load_runtime_activity(
            self.runtime_state.db_path,
            run_ids=(run_id,),
        )
        observation = activity.by_run_id.get(run_id)
        if observation is not None:
            serialized["activity"] = observation.to_dict()
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
                "activity_state": (
                    observation.state.value if observation is not None else "not_found"
                ),
                "proves_executor_liveness": False,
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

    async def runtime_interrupts(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        scan_limit = min(max_items * 20, 1000)
        events = await self.runtime_state.list_session_events(
            session_id=session_id,
            limit=scan_limit,
        )
        controls = [
            self._control_event_to_dict(event)
            for event in events
            if _is_control_event(event)
        ]
        if status is not None:
            controls = [event for event in controls if event["status"] == status]
        controls = controls[:max_items]
        return {
            "schema_version": "runtime_interrupts_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {"session_id": session_id, "status": status, "limit": max_items},
            "summary": {
                "control_event_count": len(controls),
                "pending_interrupt_count": sum(
                    1
                    for event in controls
                    if event["control_type"] == "interrupt" and event["status"] == "pending"
                ),
                "human_approval_required_count": sum(
                    1 for event in controls if event["requires_human"]
                ),
                "approved_count": sum(1 for event in controls if event["status"] == "approved"),
                "resumed_count": sum(1 for event in controls if event["status"] == "resumed"),
            },
            "control_events": controls,
        }

    async def runtime_control_action(
        self,
        *,
        action: str,
        session_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        approval_id: str | None = None,
        interrupt_id: str | None = None,
        resume_token: str | None = None,
        actor: str = "operator",
        reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an operator control action and its resulting runtime event."""
        return await RuntimeControlActions(self.runtime_state).runtime_control_action(
            action=action,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            approval_id=approval_id,
            interrupt_id=interrupt_id,
            resume_token=resume_token,
            actor=actor,
            reason=reason,
            payload=payload,
        )

    async def _run_summary(
        self,
        run: DelegationRun,
        activity: Any | None = None,
    ) -> dict[str, Any]:
        run_view = _serialize_value(run)
        run_view["activity"] = (
            activity.to_dict()
            if activity is not None
            else {
                "semantics": "runtime_activity.v1",
                "state": "expired_or_unproven",
                "reason_codes": ["activity_observation_missing"],
                "proves_executor_liveness": False,
            }
        )
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
    def _control_event_to_dict(event: SessionEventRecord) -> dict[str, Any]:
        event_view = _serialize_value(event)
        payload = event_view.get("payload") or {}
        control_type = _control_type(event)
        status = _control_status(event)
        requires_human = bool(
            payload.get("requires_human")
            or payload.get("human_approval_required")
            or (control_type == "human_approval" and status == "pending")
        )
        return {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "task_id": event.task_id,
            "run_id": event.run_id,
            "agent_id": event.agent_id,
            "event_name": event.event_name,
            "control_type": control_type,
            "status": status,
            "requires_human": requires_human,
            "interrupt_id": str(payload.get("interrupt_id") or ""),
            "approval_id": str(payload.get("approval_id") or ""),
            "resume_token": str(payload.get("resume_token") or ""),
            "checkpoint_id": str(payload.get("checkpoint_id") or ""),
            "summary": event.summary,
            "created_at": event.created_at.isoformat(),
            "event": event_view,
        }

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
