"""Tests for CorrelationContext propagation, signal fanout, trace_id stores,
and task-claim consistency guard.

Covers:
  1. CorrelationContext dataclass + contextvars propagation
  2. TelicSeam signal emission to signal_bus
  3. trace_id columns in TaskBoard, RuntimeStateStore, TelemetryPlaneStore
  4. Guardian consistency guard: COMPLETED task + still-OPEN claim detection
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dharma_swarm.correlation_context import (
    CorrelationContext,
    correlation_scope,
    correlation_scope_sync,
    get_correlation,
    set_correlation,
)


# ---------------------------------------------------------------------------
# 1. CorrelationContext unit tests
# ---------------------------------------------------------------------------


class TestCorrelationContext:
    def test_default_trace_id_generated(self):
        ctx = CorrelationContext()
        assert ctx.trace_id.startswith("trc_")
        assert len(ctx.trace_id) == 20  # "trc_" + 16 hex chars

    def test_empty_default(self):
        ctx = get_correlation()
        assert ctx.trace_id == ""
        assert ctx.proposal_id == ""
        assert ctx.session_id == ""

    def test_set_and_get(self):
        ctx = CorrelationContext(
            trace_id="trc_test123",
            proposal_id="prop_abc",
            session_id="sess_001",
        )
        token = set_correlation(ctx)
        try:
            current = get_correlation()
            assert current.trace_id == "trc_test123"
            assert current.proposal_id == "prop_abc"
            assert current.session_id == "sess_001"
        finally:
            from dharma_swarm.correlation_context import _correlation_var
            _correlation_var.reset(token)

    def test_with_proposal(self):
        ctx = CorrelationContext(trace_id="trc_a", session_id="sess_1")
        ctx2 = ctx.with_proposal("prop_xyz")
        assert ctx2.trace_id == "trc_a"
        assert ctx2.proposal_id == "prop_xyz"
        assert ctx2.session_id == "sess_1"
        # original unchanged (frozen)
        assert ctx.proposal_id == ""

    def test_as_dict(self):
        ctx = CorrelationContext(
            trace_id="trc_d", proposal_id="prop_d", session_id="sess_d"
        )
        d = ctx.as_dict()
        assert d == {
            "trace_id": "trc_d",
            "proposal_id": "prop_d",
            "session_id": "sess_d",
        }

    def test_frozen(self):
        ctx = CorrelationContext()
        with pytest.raises(AttributeError):
            ctx.trace_id = "changed"  # type: ignore[misc]


class TestCorrelationScope:
    @pytest.mark.asyncio
    async def test_async_scope_sets_and_resets(self):
        before = get_correlation()
        assert before.trace_id == ""

        async with correlation_scope(
            trace_id="trc_scope", session_id="sess_scope"
        ) as ctx:
            assert ctx.trace_id == "trc_scope"
            inner = get_correlation()
            assert inner.trace_id == "trc_scope"
            assert inner.session_id == "sess_scope"

        after = get_correlation()
        assert after.trace_id == ""

    @pytest.mark.asyncio
    async def test_async_scope_auto_generates_trace_id(self):
        async with correlation_scope() as ctx:
            assert ctx.trace_id.startswith("trc_")

    def test_sync_scope_sets_and_resets(self):
        before = get_correlation()
        assert before.trace_id == ""

        with correlation_scope_sync(
            trace_id="trc_sync", proposal_id="prop_sync"
        ) as ctx:
            assert ctx.trace_id == "trc_sync"
            inner = get_correlation()
            assert inner.proposal_id == "prop_sync"

        after = get_correlation()
        assert after.trace_id == ""

    @pytest.mark.asyncio
    async def test_nested_scopes(self):
        async with correlation_scope(trace_id="trc_outer") as outer:
            assert get_correlation().trace_id == "trc_outer"
            async with correlation_scope(trace_id="trc_inner") as inner:
                assert get_correlation().trace_id == "trc_inner"
            assert get_correlation().trace_id == "trc_outer"
        assert get_correlation().trace_id == ""


# ---------------------------------------------------------------------------
# 2. TelicSeam signal emission tests
# ---------------------------------------------------------------------------


def _make_seam(tmp_path: Path, signal_bus=None):
    """Create a TelicSeam with isolated registry + lineage state."""
    from dharma_swarm.lineage import LineageGraph
    from dharma_swarm.ontology import OntologyRegistry
    from dharma_swarm.telic_seam import TelicSeam

    registry = OntologyRegistry.create_dharma_registry()
    lineage = LineageGraph(tmp_path / "lineage.db")
    return TelicSeam(registry=registry, lineage=lineage, signal_bus=signal_bus)


class TestTelicSeamSignalFanout:
    @pytest.mark.asyncio
    async def test_record_outcome_emits_signal(self, tmp_path: Path):
        from dharma_swarm.signal_bus import (
            SIGNAL_OUTCOME_RECORDED,
            SignalBus,
        )

        bus = SignalBus()
        seam = _make_seam(tmp_path, signal_bus=bus)

        from dharma_swarm.models import Task, TaskPriority, TaskStatus
        task = Task(
            id="task_001",
            title="test task",
            status=TaskStatus.RUNNING,
            priority=TaskPriority.NORMAL,
            created_by="test",
        )
        proposal_id = seam.record_dispatch(
            task=task,
            agent_id="agent_a",
            topology="pipeline",
        )
        assert proposal_id is not None

        async with correlation_scope(
            trace_id="trc_fanout", session_id="sess_fanout"
        ):
            outcome_id = seam.record_outcome(
                task=task,
                agent_id="agent_a",
                success=True,
                result_summary="Test passed",
            )
            assert outcome_id is not None

        signals = bus.drain()
        outcome_signals = [
            s for s in signals if s.get("type") == SIGNAL_OUTCOME_RECORDED
        ]
        assert len(outcome_signals) >= 1
        sig = outcome_signals[0]
        assert sig["trace_id"] == "trc_fanout"
        assert sig["session_id"] == "sess_fanout"
        assert sig["success"] is True
        assert sig["agent_id"] == "agent_a"

    @pytest.mark.asyncio
    async def test_record_value_event_emits_signal(self, tmp_path: Path):
        from dharma_swarm.signal_bus import (
            SIGNAL_VALUE_EVENT_RECORDED,
            SignalBus,
        )

        bus = SignalBus()
        seam = _make_seam(tmp_path, signal_bus=bus)

        from dharma_swarm.models import Task, TaskPriority, TaskStatus
        task = Task(
            id="task_002",
            title="value test",
            status=TaskStatus.RUNNING,
            priority=TaskPriority.NORMAL,
            created_by="test",
        )
        proposal_id = seam.record_dispatch(
            task=task, agent_id="agent_v", topology="pipeline",
        )
        assert proposal_id is not None
        outcome_id = seam.record_outcome(
            task=task,
            agent_id="agent_v",
            success=True,
            result_summary="value outcome",
        )
        assert outcome_id is not None

        async with correlation_scope(
            trace_id="trc_value", session_id="sess_value"
        ):
            ve_id = seam.record_value_event(
                outcome_id=outcome_id,
                task=task,
                agent_id="agent_v",
                result_text="value result",
            )
            assert ve_id is not None

        signals = bus.drain()
        ve_signals = [
            s for s in signals if s.get("type") == SIGNAL_VALUE_EVENT_RECORDED
        ]
        assert len(ve_signals) >= 1
        sig = ve_signals[0]
        assert sig["trace_id"] == "trc_value"
        assert sig["agent_id"] == "agent_v"

    @pytest.mark.asyncio
    async def test_no_signal_without_bus(self, tmp_path: Path):
        """TelicSeam without signal_bus should not raise."""
        from dharma_swarm.models import Task, TaskPriority, TaskStatus

        seam = _make_seam(tmp_path)  # no signal_bus
        task = Task(
            id="task_003",
            title="no bus test",
            status=TaskStatus.RUNNING,
            priority=TaskPriority.NORMAL,
            created_by="test",
        )
        proposal_id = seam.record_dispatch(
            task=task, agent_id="a", topology="pipeline",
        )
        assert proposal_id is not None
        outcome_id = seam.record_outcome(
            task=task, agent_id="a", success=True,
            result_summary="ok",
        )
        assert outcome_id is not None


# ---------------------------------------------------------------------------
# 3. trace_id column tests
# ---------------------------------------------------------------------------


class TestTaskBoardTraceId:
    @pytest.mark.asyncio
    async def test_trace_id_stored_on_create(self, tmp_path: Path):
        from dharma_swarm.task_board import TaskBoard

        db_path = tmp_path / "tasks.db"
        board = TaskBoard(db_path)
        await board.init_db()

        async with correlation_scope(trace_id="trc_tb_test"):
            task = await board.create(title="trace test")

        # Read from SQLite directly
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            row = await (
                await db.execute(
                    "SELECT trace_id FROM tasks WHERE id = ?", (task.id,)
                )
            ).fetchone()
        assert row is not None
        assert row[0] == "trc_tb_test"

    @pytest.mark.asyncio
    async def test_trace_id_in_metadata(self, tmp_path: Path):
        from dharma_swarm.task_board import TaskBoard

        db_path = tmp_path / "tasks.db"
        board = TaskBoard(db_path)
        await board.init_db()

        async with correlation_scope(trace_id="trc_meta"):
            task = await board.create(title="metadata test")

        assert task.metadata.get("trace_id") == "trc_meta"

    @pytest.mark.asyncio
    async def test_trace_id_empty_without_context(self, tmp_path: Path):
        from dharma_swarm.task_board import TaskBoard

        db_path = tmp_path / "tasks.db"
        board = TaskBoard(db_path)
        await board.init_db()

        task = await board.create(title="no context test")

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            row = await (
                await db.execute(
                    "SELECT trace_id FROM tasks WHERE id = ?", (task.id,)
                )
            ).fetchone()
        assert row is not None
        assert row[0] == ""

    @pytest.mark.asyncio
    async def test_trace_id_migration_idempotent(self, tmp_path: Path):
        """Calling init_db twice should not fail (migration is idempotent)."""
        from dharma_swarm.task_board import TaskBoard

        db_path = tmp_path / "tasks.db"
        board = TaskBoard(db_path)
        await board.init_db()
        await board.init_db()  # second call should be fine


class TestRuntimeStateTraceId:
    @pytest.mark.asyncio
    async def test_claim_has_trace_id_column(self, tmp_path: Path):
        from dharma_swarm.runtime_state import RuntimeStateStore

        db_path = tmp_path / "runtime.db"
        store = RuntimeStateStore(db_path=db_path)
        await store.init_db()

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            cols = await (
                await db.execute("PRAGMA table_info(task_claims)")
            ).fetchall()
        col_names = [c[1] for c in cols]
        assert "trace_id" in col_names

    @pytest.mark.asyncio
    async def test_delegation_run_has_trace_id_column(self, tmp_path: Path):
        from dharma_swarm.runtime_state import RuntimeStateStore

        db_path = tmp_path / "runtime.db"
        store = RuntimeStateStore(db_path=db_path)
        await store.init_db()

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            cols = await (
                await db.execute("PRAGMA table_info(delegation_runs)")
            ).fetchall()
        col_names = [c[1] for c in cols]
        assert "trace_id" in col_names


class TestTelemetryPlaneTraceId:
    @pytest.mark.asyncio
    async def test_critical_tables_have_trace_id(self, tmp_path: Path):
        from dharma_swarm.telemetry_plane import TelemetryPlaneStore

        db_path = tmp_path / "telemetry.db"
        store = TelemetryPlaneStore(db_path=db_path)
        await store.init_db()

        import aiosqlite
        for table in ("routing_decisions", "policy_decisions", "economic_events"):
            async with aiosqlite.connect(db_path) as db:
                cols = await (
                    await db.execute(f"PRAGMA table_info({table})")
                ).fetchall()
            col_names = [c[1] for c in cols]
            assert "trace_id" in col_names, f"trace_id missing in {table}"


# ---------------------------------------------------------------------------
# 4. Consistency guard tests
# ---------------------------------------------------------------------------


class TestTaskConsistencyGuard:
    async def test_detects_split_lifecycle(self, tmp_path: Path):
        """COMPLETED task + still-OPEN claim should produce BLOCKER finding."""
        db_path = tmp_path / "state" / "runtime.db"
        db_path.parent.mkdir(parents=True)
        db = sqlite3.connect(str(db_path))
        db.execute(
            "CREATE TABLE tasks ("
            " id TEXT PRIMARY KEY, title TEXT, description TEXT DEFAULT '',"
            " status TEXT, priority TEXT DEFAULT 'normal',"
            " assigned_to TEXT, created_by TEXT DEFAULT 'system',"
            " created_at TEXT, updated_at TEXT,"
            " result TEXT, metadata TEXT DEFAULT '{}',"
            " trace_id TEXT DEFAULT '')"
        )
        db.execute(
            "CREATE TABLE task_claims ("
            " claim_id TEXT PRIMARY KEY, task_id TEXT, session_id TEXT DEFAULT '',"
            " agent_id TEXT, status TEXT, claimed_at TEXT,"
            " acked_at TEXT, heartbeat_at TEXT, stale_after TEXT,"
            " recovered_at TEXT, retry_count INTEGER DEFAULT 0,"
            " metadata_json TEXT DEFAULT '{}', trace_id TEXT DEFAULT '')"
        )
        db.execute(
            "INSERT INTO tasks VALUES"
            " ('t1','Task One','','completed','normal',NULL,'sys','2026-01-01','2026-01-01',NULL,'{}','')"
        )
        db.execute(
            "INSERT INTO task_claims VALUES"
            " ('c1','t1','','agent_x','claimed','2026-01-01',NULL,NULL,NULL,NULL,0,'{}','')"
        )
        db.commit()
        db.close()

        from dharma_swarm.consistency_guard import run_task_consistency_guard
        findings = await run_task_consistency_guard(tmp_path)
        assert len(findings) == 1
        assert findings[0].severity == "BLOCKER"
        assert "Split lifecycle" in findings[0].title
        assert "t1" in findings[0].detail

    async def test_ok_when_claim_released(self, tmp_path: Path):
        """COMPLETED task + released claim should produce INFO finding."""
        db_path = tmp_path / "state" / "runtime.db"
        db_path.parent.mkdir(parents=True)
        db = sqlite3.connect(str(db_path))
        db.execute(
            "CREATE TABLE tasks ("
            " id TEXT PRIMARY KEY, title TEXT, description TEXT DEFAULT '',"
            " status TEXT, priority TEXT DEFAULT 'normal',"
            " assigned_to TEXT, created_by TEXT DEFAULT 'system',"
            " created_at TEXT, updated_at TEXT,"
            " result TEXT, metadata TEXT DEFAULT '{}',"
            " trace_id TEXT DEFAULT '')"
        )
        db.execute(
            "CREATE TABLE task_claims ("
            " claim_id TEXT PRIMARY KEY, task_id TEXT, session_id TEXT DEFAULT '',"
            " agent_id TEXT, status TEXT, claimed_at TEXT,"
            " acked_at TEXT, heartbeat_at TEXT, stale_after TEXT,"
            " recovered_at TEXT, retry_count INTEGER DEFAULT 0,"
            " metadata_json TEXT DEFAULT '{}', trace_id TEXT DEFAULT '')"
        )
        db.execute(
            "INSERT INTO tasks VALUES"
            " ('t2','Task Two','','completed','normal',NULL,'sys','2026-01-01','2026-01-01',NULL,'{}','')"
        )
        db.execute(
            "INSERT INTO task_claims VALUES"
            " ('c2','t2','','agent_y','released','2026-01-01',NULL,NULL,NULL,NULL,0,'{}','')"
        )
        db.commit()
        db.close()

        from dharma_swarm.consistency_guard import run_task_consistency_guard
        findings = await run_task_consistency_guard(tmp_path)
        assert len(findings) == 1
        assert findings[0].severity == "INFO"
        assert "OK" in findings[0].title

    async def test_no_db_returns_empty(self, tmp_path: Path):
        """No database file should return empty findings (not crash)."""
        from dharma_swarm.consistency_guard import run_task_consistency_guard
        findings = await run_task_consistency_guard(tmp_path)
        assert findings == []
