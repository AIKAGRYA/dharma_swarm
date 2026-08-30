"""Operator-facing query helpers over the canonical runtime spine."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dharma_swarm.operator_bridge import OperatorBridge
from dharma_swarm.runtime_activity import (
    ACTIVITY_SEMANTICS,
    RuntimeActivitySnapshot,
    load_runtime_activity,
)
from dharma_swarm.runtime_agent_server_views import RuntimeAgentServerViews
from dharma_swarm.runtime_graph_views import RuntimeGraphViews
from dharma_swarm.runtime_platform_views import RuntimePlatformViews
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QueueTaskView:
    task_id: str
    status: str
    sender: str
    claimed_by: str | None
    retry_count: int
    has_claim_ack: bool
    has_response: bool
    overdue_response_ack: bool
    last_heartbeat_at: str | None
    current_artifact_id: str | None
    summary: str


@dataclass(frozen=True)
class RuntimeOverview:
    sessions: int
    claims: int
    active_claims: int
    acknowledged_claims: int
    runs: int
    active_runs: int
    artifacts: int
    promoted_facts: int
    context_bundles: int
    operator_actions: int
    active_sessions: int
    current_lease_claims: int
    observed_nonterminal_claims: int
    observed_nonterminal_runs: int
    expired_or_unproven_runs: int
    terminal_evidence_conflicts: int
    activity_observed_at: str
    activity_semantics: str = ACTIVITY_SEMANTICS
    proves_executor_liveness: bool = False


class OperatorViews:
    """Thin operator/cockpit read model built on canonical runtime state."""

    def __init__(
        self,
        runtime_state: RuntimeStateStore,
        *,
        bridge: OperatorBridge | None = None,
    ) -> None:
        self.runtime_state = runtime_state
        self.bridge = bridge

    async def runtime_overview(
        self,
        *,
        session_id: str | None = None,
        activity: RuntimeActivitySnapshot | None = None,
    ) -> RuntimeOverview:
        await self.runtime_state.init_db()
        activity = activity or load_runtime_activity(
            self.runtime_state.db_path, session_id=session_id
        )
        activity_summary = activity.summary()
        clauses: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        with sqlite3.connect(str(self.runtime_state.db_path)) as db:
            sessions = self._count(db, "sessions", where, params)
            claims = self._count(db, "task_claims", where, params)
            observed_nonterminal_claims = self._count(
                db,
                "task_claims",
                self._augment_where(
                    where,
                    "lower(status) NOT IN "
                    "('cancelled','canceled','completed','error','errored','failed',"
                    "'stale_recovered','succeeded','success') AND recovered_at IS NULL",
                ),
                params,
            )
            acknowledged_claims = self._count(
                db,
                "task_claims",
                self._augment_where(where, "acked_at IS NOT NULL"),
                params,
            )
            runs = self._count(db, "delegation_runs", where, params)
            artifacts = self._count(db, "artifact_records", where, params)
            promoted_facts = self._count(
                db,
                "memory_facts",
                self._augment_where(where, "truth_state = 'promoted'"),
                params,
            )
            context_bundles = self._count(db, "context_bundles", where, params)
            operator_actions = self._count(db, "operator_actions", where, params)
        return RuntimeOverview(
            sessions=sessions,
            claims=claims,
            active_claims=int(activity_summary["current_lease_claim_count"]),
            acknowledged_claims=acknowledged_claims,
            runs=runs,
            active_runs=int(activity_summary["current_lease_run_count"]),
            artifacts=artifacts,
            promoted_facts=promoted_facts,
            context_bundles=context_bundles,
            operator_actions=operator_actions,
            active_sessions=int(activity_summary["active_session_count"]),
            current_lease_claims=int(
                activity_summary["current_lease_claim_count"]
            ),
            observed_nonterminal_claims=observed_nonterminal_claims,
            observed_nonterminal_runs=int(
                activity_summary["observed_nonterminal_run_count"]
            ),
            expired_or_unproven_runs=int(
                activity_summary["expired_or_unproven_run_count"]
            ),
            terminal_evidence_conflicts=int(
                activity_summary["terminal_evidence_conflict_count"]
            ),
            activity_observed_at=str(activity_summary["activity_observed_at"]),
        )

    async def active_runs(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
        activity: RuntimeActivitySnapshot | None = None,
    ) -> list[DelegationRun]:
        await self.runtime_state.init_db()
        activity = activity or load_runtime_activity(
            self.runtime_state.db_path, session_id=session_id
        )
        return list(activity.current_runs[: max(1, limit)])

    async def operator_activity_snapshot(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> tuple[RuntimeOverview, list[DelegationRun]]:
        """Return counters and current-run rows from one activity observation."""

        await self.runtime_state.init_db()
        activity = load_runtime_activity(
            self.runtime_state.db_path, session_id=session_id
        )
        overview = await self.runtime_overview(
            session_id=session_id, activity=activity
        )
        runs = await self.active_runs(
            session_id=session_id,
            limit=limit,
            activity=activity,
        )
        return overview, runs

    async def runtime_graph(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        topology: str | None = None,
        limit: int = 20,
        receipt_limit: int = 50,
    ) -> dict[str, Any]:
        """Return an operator graph snapshot from canonical runtime state."""
        return await RuntimeGraphViews(self.runtime_state).runtime_graph(
            session_id=session_id,
            task_id=task_id,
            topology=topology,
            limit=limit,
            receipt_limit=receipt_limit,
        )

    async def runtime_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return persisted runtime session/thread state for operator APIs."""
        return await RuntimePlatformViews(self.runtime_state).runtime_sessions(
            status=status,
            limit=limit,
        )

    async def runtime_runs(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return persisted delegation runs for operator APIs."""
        return await RuntimePlatformViews(self.runtime_state).runtime_runs(
            session_id=session_id,
            task_id=task_id,
            status=status,
            limit=limit,
        )

    async def runtime_run_detail(self, run_id: str) -> dict[str, Any]:
        """Return the canonical ledger detail for a single runtime run."""
        return await RuntimePlatformViews(self.runtime_state).runtime_run_detail(run_id)

    async def runtime_checkpoints(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        topology: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return persisted checkpoint/topology snapshots for operator APIs."""
        return await RuntimePlatformViews(self.runtime_state).runtime_checkpoints(
            session_id=session_id,
            task_id=task_id,
            topology=topology,
            limit=limit,
        )

    async def runtime_events(
        self,
        *,
        session_id: str | None = None,
        ledger_kind: str | None = None,
        event_name: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return persisted session/runtime event history for operator APIs."""
        return await RuntimePlatformViews(self.runtime_state).runtime_events(
            session_id=session_id,
            ledger_kind=ledger_kind,
            event_name=event_name,
            limit=limit,
        )

    async def runtime_interrupts(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return interrupt/resume/human-approval state from runtime events."""
        return await RuntimePlatformViews(self.runtime_state).runtime_interrupts(
            session_id=session_id,
            status=status,
            limit=limit,
        )

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
        """Record an auditable approve/reject/resume runtime control action."""
        return await RuntimePlatformViews(self.runtime_state).runtime_control_action(
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

    async def runtime_assistants(self, *, limit: int = 50) -> dict[str, Any]:
        """Return assistants/configurations projected from runtime state."""
        return await RuntimeAgentServerViews(self.runtime_state).runtime_assistants(
            limit=limit,
        )

    async def runtime_background_jobs(self, *, limit: int = 50) -> dict[str, Any]:
        """Return background/cron job state projected from runtime and cron storage."""
        return await RuntimeAgentServerViews(self.runtime_state).runtime_background_jobs(
            limit=limit,
        )

    async def recent_operator_actions(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        actions = await self.runtime_state.list_operator_actions(
            session_id=session_id,
            task_id=task_id,
            limit=limit,
        )
        return [
            {
                "action_id": action.action_id,
                "action_name": action.action_name,
                "actor": action.actor,
                "task_id": action.task_id,
                "run_id": action.run_id,
                "reason": action.reason,
                "payload": action.payload,
                "created_at": action.created_at.isoformat(),
            }
            for action in actions
        ]

    async def bridge_queue(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        now: datetime | None = None,
    ) -> list[QueueTaskView]:
        if self.bridge is None:
            raise RuntimeError("bridge is required for bridge queue views")
        reference_now = now or _utc_now()
        tasks = await self.bridge.list_tasks(status=status, limit=limit)
        views: list[QueueTaskView] = []
        for task in tasks:
            last_heartbeat = task.metadata.get("last_heartbeat", {})
            delivery_ack = task.metadata.get("delivery_ack")
            deadline_raw = task.metadata.get("ack_deadline_at")
            deadline = None
            if isinstance(deadline_raw, str):
                try:
                    deadline = datetime.fromisoformat(deadline_raw)
                except ValueError:
                    deadline = None
            overdue_ack = (
                bool(task.response)
                and not bool(delivery_ack)
                and bool(task.metadata.get("require_delivery_ack", True))
                and deadline is not None
                and reference_now >= deadline
            )
            summary = task.response.summary if task.response is not None else task.task
            views.append(
                QueueTaskView(
                    task_id=task.id,
                    status=task.status,
                    sender=task.sender,
                    claimed_by=task.claimed_by,
                    retry_count=task.retry_count,
                    has_claim_ack=bool(task.metadata.get("claim_ack")),
                    has_response=task.response is not None,
                    overdue_response_ack=overdue_ack,
                    last_heartbeat_at=last_heartbeat.get("heartbeat_at") if isinstance(last_heartbeat, dict) else None,
                    current_artifact_id=str(task.metadata.get("current_artifact_id") or "") or None,
                    summary=summary,
                )
            )
        return views

    async def overdue_response_acks(
        self,
        *,
        limit: int = 50,
        now: datetime | None = None,
    ) -> list[QueueTaskView]:
        if self.bridge is None:
            raise RuntimeError("bridge is required for bridge queue views")
        pending = await self.bridge.list_unacknowledged_responses(
            limit=limit,
            now=now or _utc_now(),
        )
        by_id = {item.task_id: item for item in await self.bridge_queue(limit=max(100, limit), now=now)}
        return [by_id[item.id] for item in pending if item.id in by_id]

    @staticmethod
    def _count(
        db: sqlite3.Connection,
        table: str,
        where: str,
        params: list[Any],
    ) -> int:
        query = f"SELECT COUNT(*) FROM {table}{where}"
        return int(db.execute(query, params).fetchone()[0])

    @staticmethod
    def _augment_where(where: str, extra_clause: str) -> str:
        if where:
            return f"{where} AND {extra_clause}"
        return f" WHERE {extra_clause}"
