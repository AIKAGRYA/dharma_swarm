"""Async task management with CRUD, dependency tracking, and status FSM.

Persistence via aiosqlite. Status transitions validated against an explicit
finite-state machine so illegal moves (e.g. COMPLETED -> PENDING) raise.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Literal

import aiosqlite

from dharma_swarm.correlation_context import get_correlation
from dharma_swarm.models import Task, TaskPriority, TaskStatus, _new_id, _utc_now
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.adapters import (
    identity_from_carrier,
    identity_metadata,
)
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.task_board_campaign_guard import (
    CampaignTaskMutationError,
    compare_and_swap_terminal_projection as _cas_terminal_projection,
    validate_generic_campaign_mutation,
)
from dharma_swarm import task_board_effect_commit as _effect_commit
from dharma_swarm.telos_gates import check_with_reflective_reroute

_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.ASSIGNED, TaskStatus.CANCELLED, TaskStatus.FAILED},
    TaskStatus.ASSIGNED: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.PENDING},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.PENDING},
    TaskStatus.CANCELLED: {TaskStatus.PENDING},
    TaskStatus.QUARANTINED_FAKE_RESULT: set(),
}

_CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending', priority TEXT NOT NULL DEFAULT 'normal',
    assigned_to TEXT, created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    result TEXT, metadata TEXT NOT NULL DEFAULT '{}',
    trace_id TEXT NOT NULL DEFAULT '')"""

_MIGRATE_TRACE_ID = "ALTER TABLE tasks ADD COLUMN trace_id TEXT NOT NULL DEFAULT ''"
_CREATE_DEPS = """
CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id TEXT NOT NULL, depends_on_id TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (depends_on_id) REFERENCES tasks(id))"""

_READY_QUERY = """
SELECT t.* FROM tasks t
WHERE t.status = ?
  AND NOT EXISTS (
      SELECT 1 FROM task_dependencies d
      LEFT JOIN tasks dep ON dep.id = d.depends_on_id
      WHERE d.task_id = t.id
        AND (dep.id IS NULL OR dep.status != ?)
  )
ORDER BY CASE t.priority
    WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
    WHEN 'normal' THEN 2 WHEN 'low' THEN 3 END,
  t.created_at ASC"""

class TaskBoardError(Exception):
    """Raised on invalid task operations."""


class TaskBoard:
    """Async task board backed by SQLite."""

    _BUSY_TIMEOUT_S = 30  # seconds — must survive contention with daemon + SwarmLens
    projection_commit_mode = _effect_commit.AUTHORITATIVE_PROJECTION_COMMIT_MODE

    def __init__(
        self,
        db_path: Path,
        *,
        runtime_state: RuntimeStateStore | None = None,
        require_identity: bool = False,
    ) -> None:
        self._db_path = db_path
        self._runtime_state = runtime_state
        self._require_identity = require_identity

    @asynccontextmanager
    async def _open(self) -> AsyncIterator[aiosqlite.Connection]:
        """Open a connection with contention and referential-integrity guards."""
        db = await aiosqlite.connect(self._db_path, timeout=self._BUSY_TIMEOUT_S)
        try:
            await db.execute("PRAGMA foreign_keys=ON")
            yield db
        finally:
            await db.close()

    @staticmethod
    async def _require_existing_task_ids(
        db: aiosqlite.Connection,
        task_ids: list[str],
        *,
        label: str,
    ) -> None:
        """Raise a stable TaskBoardError when referenced task IDs do not exist."""
        requested = sorted(set(task_ids))
        if not requested:
            return
        placeholders = ",".join("?" for _ in requested)
        cur = await db.execute(
            f"SELECT id FROM tasks WHERE id IN ({placeholders})",
            requested,
        )
        found = {str(row[0]) for row in await cur.fetchall()}
        missing = [task_id for task_id in requested if task_id not in found]
        if missing:
            raise TaskBoardError(f"missing {label}: {', '.join(missing)}")

    async def init_db(self) -> None:
        """Create tasks and task_dependencies tables.  Enables WAL for concurrency."""
        async with self._open() as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=30000")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute(_CREATE_TASKS)
            await db.execute(_CREATE_DEPS)
            await _effect_commit.ensure_effect_commit_ledger(db)
            # Migrate: add trace_id column if missing (existing databases)
            try:
                await db.execute(_MIGRATE_TRACE_ID)
            except Exception:
                pass  # column already exists
            await db.commit()

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _row_to_task(row: aiosqlite.Row, deps: list[str]) -> Task:
        """Convert a database row + dependency list into a Task."""
        return Task(
            id=row[0], title=row[1], description=row[2],
            status=TaskStatus(row[3]), priority=TaskPriority(row[4]),
            assigned_to=row[5], created_by=row[6],
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
            result=row[9], metadata=json.loads(row[10]), depends_on=deps,
        )

    @staticmethod
    async def _fetch_deps(db: aiosqlite.Connection, task_id: str) -> list[str]:
        cur = await db.execute(
            "SELECT depends_on_id FROM task_dependencies WHERE task_id = ?",
            (task_id,),
        )
        return [r[0] for r in await cur.fetchall()]

    _ALLOWED_COLUMNS = frozenset({
        "title", "description", "priority", "assigned_to",
        "created_by", "result", "metadata",
    })

    @staticmethod
    def _coerce_db_value(col: str, val: Any) -> Any:
        """Normalize Python values for SQLite writes."""
        if col != "metadata":
            return val
        if val is None:
            return json.dumps({}, ensure_ascii=True)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=True)

    async def _set_status(self, task_id: str, new: TaskStatus, **fields: Any) -> Task:
        """Validate and apply a status transition with optional field updates."""
        async with self._open() as db:
            await db.execute("BEGIN IMMEDIATE")
            cur = await db.execute(
                "SELECT status, metadata FROM tasks WHERE id = ?", (task_id,)
            )
            row = await cur.fetchone()
            if row is None:
                await db.rollback()
                raise TaskBoardError(f"Task {task_id!r} not found")
            current = TaskStatus(row[0])
            if new not in _TRANSITIONS.get(current, set()):
                await db.rollback()
                raise TaskBoardError(
                    f"Invalid transition: {current.value} -> {new.value}"
                )
            try:
                validate_generic_campaign_mutation(
                    row[1], task_id=task_id, new_status=new.value,
                    replacement_raw=fields.get("metadata"),
                    replacement_provided="metadata" in fields,
                    assigned_to_provided="assigned_to" in fields, result_provided="result" in fields,
                )
            except CampaignTaskMutationError as exc:
                await db.rollback()
                raise TaskBoardError(str(exc)) from exc
            now = _utc_now().isoformat()
            sets = ["status = ?", "updated_at = ?"]
            params: list[Any] = [new.value, now]
            for col, val in fields.items():
                if col not in self._ALLOWED_COLUMNS:
                    raise TaskBoardError(f"Invalid column: {col!r}")
                sets.append(f"{col} = ?")
                params.append(self._coerce_db_value(col, val))
            params.append(task_id)
            await db.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params,
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            updated = await cur.fetchone()
            deps = await self._fetch_deps(db, task_id)
            return self._row_to_task(updated, deps)  # type: ignore[arg-type]

    async def _load_rows(self, db: aiosqlite.Connection, rows: list[Any]) -> list[Task]:
        tasks: list[Task] = []
        for row in rows:
            deps = await self._fetch_deps(db, row[0])
            tasks.append(self._row_to_task(row, deps))
        return tasks

    async def _witness_transition(
        self,
        *,
        task_id: str,
        action: str,
        think_phase: str,
        reflection: str,
    ) -> None:
        """Apply bounded reflective checkpoint to task status transitions."""
        gate = check_with_reflective_reroute(
            action=action,
            think_phase=think_phase,
            reflection=reflection,
            max_reroutes=1,
            requirement_refs=[f"task:{task_id}"],
        )
        if gate.result.decision.value == "block":
            raise TaskBoardError(
                f"Telos blocked transition ({think_phase}): {gate.result.reason}"
            )

    def _resolve_identity(
        self,
        *,
        task_id: str,
        created_by: str,
        metadata: dict[str, Any],
        require_identity: bool,
        execution_identity: ExecutionIdentity | None,
    ) -> ExecutionIdentity | None:
        if require_identity and self._runtime_state is None:
            raise MissingExecutionIdentity("RuntimeStateStore is required when TaskBoard requires ExecutionIdentity")
        if execution_identity is not None:
            identity = execution_identity.with_updates(task_id=task_id, agent_id=created_by)
            return identity.require_for_dispatch()
        if require_identity:
            return identity_from_carrier(
                {"id": task_id, "created_by": created_by, "metadata": metadata},
                surface="task_board",
                task_id=task_id,
                agent_id=created_by,
                require_existing=True,
            ).with_updates(task_id=task_id, agent_id=created_by).require_for_dispatch()
        existing = ExecutionIdentity.from_metadata(metadata, require=False)
        if existing is not None:
            return existing.with_updates(task_id=task_id, agent_id=created_by).require_for_dispatch()
        if self._runtime_state is not None:
            return identity_from_carrier(
                {"id": task_id, "created_by": created_by, "metadata": metadata},
                surface="task_board",
                task_id=task_id,
                agent_id=created_by,
            )
        return None

    async def _record_taskboard_intent(
        self,
        identity: ExecutionIdentity,
        *,
        source: str,
        title: str,
    ) -> None:
        if self._runtime_state is None:
            return
        await self._runtime_state.record_execution_identity(
            identity,
            source=source,
            metadata={"surface": "task_board", "title": title},
        )
        await self._runtime_state.record_side_effect_intent(
            identity,
            f"task_board:{identity.task_id}",
            payload={"surface": "task_board", "title": title},
        )

    async def _record_taskboard_receipt(
        self,
        identity: ExecutionIdentity,
        *,
        title: str,
    ) -> None:
        if self._runtime_state is None:
            return
        await self._runtime_state.record_receipt_for_identity(
            identity,
            receipt_type="task_created",
            status="created",
            side_effect_key=f"task_board:{identity.task_id}",
            payload={"surface": "task_board", "title": title},
        )
        await self._runtime_state.record_side_effect_complete(
            identity,
            f"task_board:{identity.task_id}",
            result_receipt_id=identity.task_id,
            payload={"surface": "task_board", "title": title},
        )

    # -- CRUD ---------------------------------------------------------------

    async def create(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        created_by: str = "system",
        depends_on: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        execution_identity: ExecutionIdentity | None = None,
        require_identity: bool | None = None,
    ) -> Task:
        """Create a new task and persist it."""
        task_id = _new_id()
        now = _utc_now()
        dep_ids: list[str] = list(depends_on or [])
        if dep_ids:
            async with self._open() as db:
                await self._require_existing_task_ids(
                    db,
                    dep_ids,
                    label="dependency",
                )
        meta = dict(metadata or {})
        effective_require = self._require_identity if require_identity is None else require_identity
        identity = self._resolve_identity(
            task_id=task_id,
            created_by=created_by,
            metadata=meta,
            require_identity=effective_require,
            execution_identity=execution_identity,
        )
        if identity is not None:
            meta.update(identity_metadata(identity, surface="task_board"))
        corr = get_correlation()
        trace_id = corr.trace_id
        if trace_id:
            meta.setdefault("trace_id", trace_id)
        elif identity is not None:
            trace_id = identity.trace_id
        if corr.cell_id:
            meta.setdefault("cell_id", corr.cell_id)
        trace_id = str(meta.get("trace_id") or trace_id)
        if identity is not None:
            await self._record_taskboard_intent(
                identity,
                source="task_board.create",
                title=title,
            )
        async with self._open() as db:
            await db.execute(
                "INSERT INTO tasks"
                " (id, title, description, status, priority, assigned_to,"
                "  created_by, created_at, updated_at, result, metadata, trace_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, title, description, TaskStatus.PENDING.value,
                 priority.value, None, created_by, now.isoformat(),
                 now.isoformat(), None, json.dumps(meta, ensure_ascii=True),
                 trace_id),
            )
            for dep_id in dep_ids:
                await db.execute(
                    "INSERT INTO task_dependencies VALUES (?,?)", (task_id, dep_id),
                )
            await db.commit()
        if identity is not None:
            await self._record_taskboard_receipt(
                identity,
                title=title,
            )
        return Task(
            id=task_id, title=title, description=description,
            priority=priority, created_by=created_by,
            created_at=now, updated_at=now, depends_on=dep_ids,
            metadata=meta,
        )

    async def create_batch(
        self,
        tasks: list[dict[str, Any]],
        *,
        require_identity: bool | None = None,
    ) -> list[Task]:
        """Create multiple tasks in a single transaction.

        JIKOKU-optimized: Batches all inserts into one transaction,
        eliminating SQLite write lock contention.

        Args:
            tasks: List of task specs, each dict with keys:
                   {title, description?, priority?, created_by?, depends_on?}

        Returns:
            List of created Task objects.
        """
        if not tasks:
            return []

        dependency_ids = [
            str(dep_id)
            for spec in tasks
            for dep_id in (spec.get("depends_on") or [])
        ]
        if dependency_ids:
            async with self._open() as db:
                await self._require_existing_task_ids(
                    db,
                    dependency_ids,
                    label="dependency",
                )

        now = _utc_now()
        created_tasks: list[Task] = []

        corr = get_correlation()
        trace_id = corr.trace_id
        effective_require = self._require_identity if require_identity is None else require_identity
        prepared: list[tuple[str, dict[str, Any], list[str], str, ExecutionIdentity | None]] = []
        for spec in tasks:
            task_id = _new_id()
            created_by = spec.get("created_by", "system")
            metadata = dict(spec.get("metadata") or {})
            identity = self._resolve_identity(
                task_id=task_id,
                created_by=created_by,
                metadata=metadata,
                require_identity=effective_require,
                execution_identity=spec.get("execution_identity"),
            )
            if identity is not None:
                metadata.update(identity_metadata(identity, surface="task_board"))
            if trace_id:
                metadata.setdefault("trace_id", trace_id)
            elif identity is not None:
                metadata.setdefault("trace_id", identity.trace_id)
            if corr.cell_id:
                metadata.setdefault("cell_id", corr.cell_id)
            row_trace_id = str(metadata.get("trace_id") or trace_id or "")
            prepared.append((task_id, metadata, spec.get("depends_on") or [], row_trace_id, identity))

        for spec, (_, _, _, _, identity) in zip(tasks, prepared):
            if identity is not None:
                await self._record_taskboard_intent(
                    identity,
                    source="task_board.create_batch",
                    title=spec["title"],
                )

        async with self._open() as db:
            # Single transaction for all tasks
            for spec, (task_id, metadata, dep_ids, row_trace_id, identity) in zip(tasks, prepared):
                title = spec["title"]
                description = spec.get("description", "")
                priority = spec.get("priority", TaskPriority.NORMAL)
                created_by = spec.get("created_by", "system")

                await db.execute(
                    "INSERT INTO tasks"
                    " (id, title, description, status, priority, assigned_to,"
                    "  created_by, created_at, updated_at, result, metadata, trace_id)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (task_id, title, description, TaskStatus.PENDING.value,
                     priority.value, None, created_by, now.isoformat(),
                     now.isoformat(), None, json.dumps(metadata, ensure_ascii=True),
                     row_trace_id),
                )

                for dep_id in dep_ids:
                    await db.execute(
                        "INSERT INTO task_dependencies VALUES (?,?)",
                        (task_id, dep_id),
                    )

                created_tasks.append(Task(
                    id=task_id, title=title, description=description,
                    priority=priority, created_by=created_by,
                    created_at=now, updated_at=now, depends_on=dep_ids,
                    metadata=metadata,
                ))

            # Single commit for entire batch
            await db.commit()

        for task, (_, _, _, _, identity) in zip(created_tasks, prepared):
            if identity is not None:
                await self._record_taskboard_receipt(
                    identity,
                    title=task.title,
                )

        return created_tasks

    async def get(self, task_id: str) -> Task | None:
        """Retrieve a single task by ID, or None if missing."""
        async with self._open() as db:
            cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cur.fetchone()
            if row is None:
                return None
            deps = await self._fetch_deps(db, task_id)
            return self._row_to_task(row, deps)

    async def get_by_title(self, title: str) -> Task | None:
        """Retrieve the first task matching *title*, or ``None``."""
        async with self._open() as db:
            cur = await db.execute(
                "SELECT * FROM tasks WHERE title = ? LIMIT 1", (title,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            deps = await self._fetch_deps(db, row[0])
            return self._row_to_task(row, deps)

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        assigned_to: str | None = None,
        limit: int = 50,
    ) -> list[Task]:
        """List tasks with optional status/assignee filters."""
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if assigned_to is not None:
            clauses.append("assigned_to = ?")
            params.append(assigned_to)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        async with self._open() as db:
            cur = await db.execute(
                f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ?",
                params,
            )
            return await self._load_rows(db, await cur.fetchall())

    async def update_task(self, task_id: str, **fields: Any) -> None:
        """Generic update (orchestrator interface).

        Routes to the appropriate specific method based on the ``status``
        field, or does a raw column update for non-status fields.
        """
        status = fields.pop("status", None)
        if status is not None:
            try:
                status = TaskStatus(status)
            except (TypeError, ValueError) as exc:
                raise TaskBoardError(f"Invalid task status: {status!r}") from exc
            if status == TaskStatus.ASSIGNED:
                await self.assign(
                    task_id,
                    fields.get("assigned_to", ""),
                    metadata=fields.get("metadata"),
                )
            elif status == TaskStatus.RUNNING:
                await self.start(task_id, metadata=fields.get("metadata"))
            elif status == TaskStatus.COMPLETED:
                await self.complete(
                    task_id,
                    fields.get("result", ""),
                    metadata=fields.get("metadata"),
                )
            elif status == TaskStatus.FAILED:
                await self.fail(
                    task_id,
                    fields.get("result", ""),
                    metadata=fields.get("metadata"),
                )
            elif status == TaskStatus.CANCELLED:
                await self.cancel(task_id, metadata=fields.get("metadata"))
            elif status == TaskStatus.PENDING:
                await self.requeue(
                    task_id,
                    reason=fields.get("result", ""),
                    metadata=fields.get("metadata"),
                )
            elif status == TaskStatus.QUARANTINED_FAKE_RESULT:
                raise TaskBoardError(
                    "quarantined_fake_result is an audit-only terminal status"
                )
        elif fields:
            # Raw column update (no status change)
            async with self._open() as db:
                await db.execute("BEGIN IMMEDIATE")
                current_row = await (
                    await db.execute(
                        "SELECT metadata FROM tasks WHERE id = ?", (task_id,)
                    )
                ).fetchone()
                if current_row is not None:
                    try:
                        validate_generic_campaign_mutation(
                            current_row[0], task_id=task_id,
                            replacement_raw=fields.get("metadata"),
                            replacement_provided="metadata" in fields,
                            assigned_to_provided="assigned_to" in fields, result_provided="result" in fields,
                        )
                    except CampaignTaskMutationError as exc:
                        await db.rollback()
                        raise TaskBoardError(str(exc)) from exc
                sets = []
                params: list[Any] = []
                for col, val in fields.items():
                    if col not in self._ALLOWED_COLUMNS:
                        await db.rollback()
                        raise TaskBoardError(f"Invalid column: {col!r}")
                    sets.append(f"{col} = ?")
                    params.append(self._coerce_db_value(col, val))
                params.append(task_id)
                await db.execute(
                    f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params,
                )
                await db.commit()

    async def compare_and_swap_campaign_status(
        self,
        expected: Task,
        *,
        new_status: TaskStatus,
        assigned_to: str | None,
        metadata: dict[str, Any],
    ) -> Task | None:
        """Transition one exact campaign row under an immediate transaction."""
        authority = expected.metadata.get("mission_campaign_authority")
        replacement_authority = metadata.get("mission_campaign_authority")
        if (
            not isinstance(authority, dict)
            or replacement_authority != authority
            or authority.get("claimed_principal") != assigned_to
            or new_status
            not in {
                TaskStatus.ASSIGNED,
                TaskStatus.RUNNING,
            }
            or new_status not in _TRANSITIONS.get(expected.status, set())
        ):
            raise TaskBoardError("campaign status CAS authority is invalid")
        async with self._open() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
            ).fetchone()
            deps = await self._fetch_deps(db, expected.id)
            current = self._row_to_task(row, deps) if row is not None else None
            if current != expected:
                await db.rollback()
                return None
            cursor = await db.execute(
                "UPDATE tasks SET status = ?, assigned_to = ?, metadata = ?,"
                " updated_at = ? WHERE id = ? AND status = ? AND assigned_to IS ?"
                " AND result IS ? AND metadata = ? AND updated_at = ?",
                (
                    new_status.value,
                    assigned_to,
                    self._coerce_db_value("metadata", metadata),
                    _utc_now().isoformat(),
                    expected.id,
                    expected.status.value,
                    expected.assigned_to,
                    expected.result,
                    row[10],
                    expected.updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return None
            await db.commit()
            updated_row = await (
                await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
            ).fetchone()
            assert updated_row is not None
            return self._row_to_task(updated_row, deps)

    async def compare_and_swap_campaign_metadata(
        self,
        expected: Task,
        *,
        metadata: dict[str, Any],
    ) -> Task | None:
        """Replace only one exact pending campaign row's authority metadata."""
        if (
            expected.status is not TaskStatus.PENDING
            or expected.assigned_to is not None
            or expected.result is not None
            or expected.metadata.get("sadhana_bootstrap_schema")
            != "dharma.sadhana.mission_bootstrap.v1"
            or metadata.get("mission_campaign_authority") is None
            or metadata.get("campaign_id") != expected.metadata.get("campaign_id")
            or metadata.get("goal_id") != expected.metadata.get("goal_id")
            or metadata.get("mission_task_creation_hash")
            != expected.metadata.get("mission_task_creation_hash")
        ):
            raise TaskBoardError("campaign metadata CAS boundary is invalid")
        async with self._open() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
            ).fetchone()
            deps = await self._fetch_deps(db, expected.id)
            current = self._row_to_task(row, deps) if row is not None else None
            if current != expected:
                await db.rollback()
                return None
            cursor = await db.execute(
                "UPDATE tasks SET metadata = ?, updated_at = ?"
                " WHERE id = ? AND status = ? AND assigned_to IS NULL"
                " AND result IS NULL AND metadata = ? AND updated_at = ?",
                (
                    self._coerce_db_value("metadata", metadata),
                    _utc_now().isoformat(),
                    expected.id,
                    TaskStatus.PENDING.value,
                    row[10],
                    expected.updated_at.isoformat(),
                ),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return None
            await db.commit()
            updated_row = await (
                await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
            ).fetchone()
            assert updated_row is not None
            return self._row_to_task(updated_row, deps)

    async def compare_and_swap_terminal_projection(
        self, expected: Task, *, metadata: dict[str, Any], result: str | None = None,
        expected_claim_id: str = "", expected_agent_id: str = "", runtime_state_store: Any = None,
    ) -> Task | None:
        """Apply a receipt-backed graph effect to one exact task attempt."""
        try:
            return await _cas_terminal_projection(
                self, expected, metadata=metadata, result=result,
                expected_claim_id=expected_claim_id, expected_agent_id=expected_agent_id,
                runtime_state_store=runtime_state_store,
            )
        except CampaignTaskMutationError as exc:
            raise TaskBoardError(str(exc)) from exc

    async def resolve_campaign_pre_effect_failure(
        self,
        task_id: str,
        *,
        expected_status: TaskStatus,
        expected_agent_id: str | None,
        expected_metadata: dict[str, Any],
        authenticated_principal: str,
        provider_task_scheduled: bool = False,
    ) -> Literal["pending", "indeterminate", "conflict"]:
        from dharma_swarm.mission_control_task_attempts import (
            CampaignTaskAttemptError,
            resolve_campaign_pre_effect_failure,
        )

        try:
            return await resolve_campaign_pre_effect_failure(
                self,
                task_id,
                expected_status=expected_status,
                expected_agent_id=expected_agent_id,
                expected_metadata=expected_metadata,
                authenticated_principal=authenticated_principal,
                provider_task_scheduled=provider_task_scheduled,
            )
        except CampaignTaskAttemptError as exc:
            raise TaskBoardError(str(exc)) from exc

    async def advance_campaign_dispatch_attempt(
        self,
        task_id: str,
        *,
        expected_status: TaskStatus,
        expected_agent_id: str,
        expected_metadata: dict[str, Any],
        next_authority: dict[str, Any],
        next_governance: dict[str, Any],
        next_routing: dict[str, Any],
    ) -> Literal["advanced", "exhausted", "conflict"]:
        from dharma_swarm.mission_control_task_attempts import (
            CampaignTaskAttemptError,
            advance_campaign_dispatch_attempt,
        )

        try:
            return await advance_campaign_dispatch_attempt(
                self,
                task_id,
                expected_status=expected_status,
                expected_agent_id=expected_agent_id,
                expected_metadata=expected_metadata,
                next_authority=next_authority,
                next_governance=next_governance,
                next_routing=next_routing,
            )
        except CampaignTaskAttemptError as exc:
            raise TaskBoardError(str(exc)) from exc

    # -- status transitions -------------------------------------------------

    async def assign(
        self,
        task_id: str,
        agent_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Assign to an agent (PENDING -> ASSIGNED)."""
        fields: dict[str, Any] = {"assigned_to": agent_id}
        if metadata is not None:
            fields["metadata"] = metadata
        return await self._set_status(task_id, TaskStatus.ASSIGNED, **fields)

    async def start(
        self,
        task_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Mark running (ASSIGNED -> RUNNING)."""
        fields: dict[str, Any] = {}
        if metadata is not None:
            fields["metadata"] = metadata
        return await self._set_status(task_id, TaskStatus.RUNNING, **fields)

    async def complete(
        self,
        task_id: str,
        result: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Mark completed (RUNNING -> COMPLETED)."""
        await self._witness_transition(
            task_id=task_id,
            action=f"complete task {task_id}",
            think_phase="before_complete",
            reflection=(
                f"Completing task {task_id}. Result captured with "
                f"{len((result or '').strip())} chars. Verify requirement coverage."
            ),
        )
        fields: dict[str, Any] = {"result": result}
        if metadata is not None:
            fields["metadata"] = metadata
        return await self._set_status(task_id, TaskStatus.COMPLETED, **fields)

    async def fail(
        self,
        task_id: str,
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Mark failed (RUNNING -> FAILED)."""
        await self._witness_transition(
            task_id=task_id,
            action=f"pivot task {task_id}",
            think_phase="before_pivot",
            reflection=(
                f"Task {task_id} failed with error context. "
                "Summarize failure signature and define pivot strategy."
            ),
        )
        fields: dict[str, Any] = {"result": error}
        if metadata is not None:
            fields["metadata"] = metadata
        return await self._set_status(task_id, TaskStatus.FAILED, **fields)

    async def cancel(
        self,
        task_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Cancel (PENDING|ASSIGNED|RUNNING -> CANCELLED)."""
        fields: dict[str, Any] = {}
        if metadata is not None:
            fields["metadata"] = metadata
        return await self._set_status(task_id, TaskStatus.CANCELLED, **fields)

    async def requeue(
        self,
        task_id: str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """Atomically requeue ordinary work; campaign retry is a typed CAS."""
        async with self._open() as db:
            await db.execute("BEGIN IMMEDIATE")
            row = await (
                await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            ).fetchone()
            if row is None:
                await db.rollback()
                raise TaskBoardError(f"Task {task_id!r} not found")
            task = self._row_to_task(row, await self._fetch_deps(db, task_id))
            if task.status not in {
                TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING,
                TaskStatus.FAILED, TaskStatus.CANCELLED,
            }:
                await db.rollback()
                raise TaskBoardError(
                    f"Cannot requeue task {task_id!r} from status {task.status.value}"
                )
            merged_meta = dict(task.metadata or {})
            if isinstance(metadata, dict):
                merged_meta.update(metadata)
            try:
                validate_generic_campaign_mutation(
                    row[10],
                    task_id=task_id,
                    new_status=TaskStatus.PENDING.value,
                    replacement_raw=merged_meta,
                    replacement_provided=True,
                )
            except CampaignTaskMutationError as exc:
                await db.rollback()
                raise TaskBoardError(str(exc)) from exc
            await db.execute(
                "UPDATE tasks SET status = ?, assigned_to = NULL, result = ?,"
                " metadata = ?, updated_at = ? WHERE id = ?",
                (TaskStatus.PENDING.value, reason,
                 self._coerce_db_value("metadata", merged_meta),
                 _utc_now().isoformat(), task_id),
            )
            await db.commit()
            updated = await (
                await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            ).fetchone()
            assert updated is not None
            return self._row_to_task(updated, await self._fetch_deps(db, task_id))

    # -- dependency management ----------------------------------------------

    async def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """Add a dependency edge: task_id depends on depends_on_id."""
        async with self._open() as db:
            await self._require_existing_task_ids(db, [task_id], label="task")
            await self._require_existing_task_ids(
                db,
                [depends_on_id],
                label="dependency",
            )
            await db.execute(
                "INSERT OR IGNORE INTO task_dependencies VALUES (?,?)",
                (task_id, depends_on_id),
            )
            await db.commit()

    async def get_dependencies(self, task_id: str) -> list[str]:
        """Return task IDs that task_id depends on."""
        async with self._open() as db:
            return await self._fetch_deps(db, task_id)

    async def get_ready_tasks(self) -> list[Task]:
        """Return PENDING tasks whose dependencies are all COMPLETED."""
        async with self._open() as db:
            cur = await db.execute(
                _READY_QUERY, (TaskStatus.PENDING.value, TaskStatus.COMPLETED.value),
            )
            return await self._load_rows(db, await cur.fetchall())

    # -- analytics ----------------------------------------------------------

    async def stats(self) -> dict[str, int]:
        """Return task counts grouped by status."""
        async with self._open() as db:
            cur = await db.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
            counts = {s.value: 0 for s in TaskStatus}
            for status_val, count in await cur.fetchall():
                counts[status_val] = count
            counts["total"] = sum(counts.values())
            return counts
