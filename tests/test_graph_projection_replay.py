"""Crash and corruption regressions for strict TaskBoard projection replay."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest

from dharma_swarm.graph import reconcile_board_replay
from dharma_swarm.graph.reconcile_board_replay import (
    PROJECTION_ACK_SCHEMA,
    _projection_marker,
    ensure_projection_ack_ledger,
    settle_task_board,
)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board_projection_intent import (
    GRAPH_PROJECTION_HISTORY_KEY,
    GRAPH_PROJECTION_KEY,
    build_task_board_projection_intent,
    stable_sha256,
)
from dharma_swarm.task_board_effect_commit import (
    NON_PRODUCTION_PROJECTION_COMMIT_MODE,
)

NOW = datetime(2026, 8, 24, 8, 30, tzinfo=timezone.utc)


class MemoryProjectionBoard:
    """Exact in-memory CAS with optional crash/corrupt-readback faults."""

    projection_commit_mode = NON_PRODUCTION_PROJECTION_COMMIT_MODE

    def __init__(
        self,
        task: Task,
        *,
        fail_before_apply_once: bool = False,
        fail_after_apply_once: bool = False,
        corrupt_readback: bool = False,
    ) -> None:
        self.task = task.model_copy(deep=True)
        self.fail_before_apply_once = fail_before_apply_once
        self.fail_after_apply_once = fail_after_apply_once
        self.corrupt_readback = corrupt_readback
        self.project_calls = 0
        self.get_calls = 0
        self._applied = False
        self._corrupted = False

    async def get(self, task_id: str) -> Task | None:
        assert task_id == self.task.id
        self.get_calls += 1
        if (
            self.corrupt_readback
            and self._applied
            and not self._corrupted
        ):
            metadata = dict(self.task.metadata)
            metadata.pop("projection_delta", None)
            metadata["concurrent_nonprotocol_write"] = True
            self.task = self.task.model_copy(update={"metadata": metadata}, deep=True)
            self._corrupted = True
        return self.task.model_copy(deep=True)

    async def compare_and_swap_terminal_projection(
        self,
        expected: Task,
        *,
        metadata: dict,
        result: str,
        **_kwargs,
    ) -> Task | None:
        self.project_calls += 1
        if self.fail_before_apply_once:
            self.fail_before_apply_once = False
            raise RuntimeError("injected crash before Board CAS")
        if self.task != expected:
            return None
        marker = metadata[GRAPH_PROJECTION_KEY]
        status = (
            TaskStatus.PENDING
            if marker["action"] in {"retry", "requeue"}
            else TaskStatus.COMPLETED
            if marker["action"] == "receipt" and marker["run_status"] == "completed"
            else TaskStatus.FAILED
        )
        assigned_to = (
            None
            if marker["action"] in {"retry", "requeue"}
            else expected.assigned_to
        )
        self.task = expected.model_copy(
            update={
                "status": status,
                "assigned_to": assigned_to,
                "result": result,
                "metadata": dict(metadata),
            },
            deep=True,
        )
        self._applied = True
        if self.fail_after_apply_once:
            self.fail_after_apply_once = False
            raise RuntimeError("injected crash after Board CAS")
        return self.task.model_copy(deep=True)


def _completion_binding(identity: ExecutionIdentity, result: str) -> dict[str, str]:
    side_effect_key = f"invoke_agent:{identity.task_id}:{identity.agent_id}"
    return {
        "schema_version": "dharma.graph.task_board_completion_binding.v1",
        "task_id": identity.task_id,
        "run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "receipt_id": f"receipt-{identity.run_id}",
        "side_effect_key": side_effect_key,
        "idempotency_key": "sek_"
        + hashlib.sha256(side_effect_key.encode()).hexdigest(),
        "dispatch_idempotency_key": identity.idempotency_key,
        "result_sha256": hashlib.sha256(result.encode()).hexdigest(),
    }


def _seed_projection(
    tmp_path: Path,
    *,
    run_id: str,
    action: str = "requeue",
) -> tuple[RuntimeStateStore, MemoryProjectionBoard, dict]:
    runtime = RuntimeStateStore(tmp_path / f"{run_id}-runtime.db")
    runtime.init_db_sync()
    identity = ExecutionIdentity(
        trace_id=f"trace-{run_id}",
        correlation_id=f"correlation-{run_id}",
        task_id=f"task-{run_id}",
        run_id=run_id,
        claim_id=f"claim-{run_id}",
        idempotency_key=f"dispatch-{run_id}",
        agent_id="agent-projection",
        session_id="session-projection",
        metadata={"fixture": "projection_replay"},
    )
    result = f"result-{run_id}"
    intent = build_task_board_projection_intent(
        execution_identity=identity.to_dict(),
        action=action,
        run_status="failed",
        source_kind=("idempotency_record" if action == "retry" else "delegation_run"),
        runtime_authority_snapshot_sha256="a" * 64,
        result=result,
        metadata_set={"projection_delta": "exact"},
        metadata_remove=["active_claim"],
        completion_binding=(
            _completion_binding(identity, result) if action == "retry" else None
        ),
        prepared_at=NOW,
    )
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, claim_id, assigned_by, assigned_to,"
            " status, started_at, completed_at, failure_code, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                identity.session_id,
                identity.task_id,
                identity.claim_id,
                "orchestrator",
                identity.agent_id,
                "failed",
                NOW.isoformat(),
                NOW.isoformat(),
                "fixture_failure",
                json.dumps({"task_board_projection_intent": intent}),
            ),
        )
        db.commit()
    task = Task(
        id=identity.task_id,
        title="strict projection replay fixture",
        status=TaskStatus.RUNNING,
        assigned_to=identity.agent_id,
        metadata={
            "execution_identity": identity.to_dict(),
            "active_claim": {
                "claim_id": identity.claim_id,
                "agent_id": identity.agent_id,
            },
            "fixture_owner": "preserved",
        },
    )
    return runtime, MemoryProjectionBoard(task), intent


def _report() -> SimpleNamespace:
    return SimpleNamespace(errors=[])


def _ledger_counts(runtime: RuntimeStateStore) -> tuple[int, int, int]:
    with sqlite3.connect(runtime.db_path) as db:
        return tuple(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "task_board_projection_targets",
                "task_board_projection_target_witnesses",
                "task_board_projection_acks",
            )
        )


async def _settle(
    runtime: RuntimeStateStore,
    board: MemoryProjectionBoard,
    run_id: str,
) -> SimpleNamespace:
    report = _report()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=report,
        now=NOW,
        logger=SimpleNamespace(error=lambda *_args, **_kwargs: None),
        run_id=run_id,
    )
    return report


@pytest.mark.asyncio
async def test_crash_before_cas_reuses_immutable_prepared_target(tmp_path: Path) -> None:
    run_id = "run-crash-before-cas"
    runtime, board, _intent = _seed_projection(tmp_path, run_id=run_id)
    board.fail_before_apply_once = True

    first = await _settle(runtime, board, run_id)

    assert first.errors == [f"projection:{run_id}:RuntimeError"]
    assert _ledger_counts(runtime) == (1, 0, 0)
    assert board.task.status is TaskStatus.RUNNING

    replay = await _settle(runtime, board, run_id)

    assert replay.errors == []
    assert _ledger_counts(runtime) == (1, 1, 1)
    assert board.project_calls == 2
    assert board.task.metadata["projection_delta"] == "exact"


@pytest.mark.asyncio
async def test_crash_after_cas_before_readback_recovers_exact_target(
    tmp_path: Path,
) -> None:
    run_id = "run-crash-after-cas"
    runtime, board, _intent = _seed_projection(tmp_path, run_id=run_id)
    board.fail_after_apply_once = True

    first = await _settle(runtime, board, run_id)

    assert first.errors == [f"projection:{run_id}:RuntimeError"]
    assert _ledger_counts(runtime) == (1, 0, 0)
    assert board.task.status is TaskStatus.PENDING
    assert board.task.metadata["projection_delta"] == "exact"

    replay = await _settle(runtime, board, run_id)

    assert replay.errors == []
    assert _ledger_counts(runtime) == (1, 1, 1)
    assert board.project_calls == 1


@pytest.mark.asyncio
async def test_exact_witness_closes_after_cas_before_ack_and_later_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_id = "run-crash-before-ack"
    runtime, board, _intent = _seed_projection(
        tmp_path,
        run_id=run_id,
        action="retry",
    )
    real_append = reconcile_board_replay._append_projection_ack

    async def crash_before_ack(*_args, **_kwargs) -> None:
        raise RuntimeError("injected crash after exact witness before ack")

    monkeypatch.setattr(reconcile_board_replay, "_append_projection_ack", crash_before_ack)
    first = await _settle(runtime, board, run_id)

    assert first.errors == [f"projection:{run_id}:RuntimeError"]
    assert _ledger_counts(runtime) == (1, 1, 0)
    first_marker = board.task.metadata[GRAPH_PROJECTION_KEY]

    # A later retry advances the current marker while preserving append-only history.
    next_marker = dict(first_marker, run_id="run-next-retry", projected_at=NOW.isoformat())
    next_history = dict(board.task.metadata[GRAPH_PROJECTION_HISTORY_KEY])
    next_history[next_marker["run_id"]] = next_marker
    board.task = board.task.model_copy(
        update={
            "status": TaskStatus.COMPLETED,
            "assigned_to": "agent-next",
            "result": "later exact result",
            "metadata": {
                **board.task.metadata,
                GRAPH_PROJECTION_KEY: next_marker,
                GRAPH_PROJECTION_HISTORY_KEY: next_history,
            },
        },
        deep=True,
    )

    monkeypatch.setattr(reconcile_board_replay, "_append_projection_ack", real_append)
    replay = await _settle(runtime, board, run_id)

    assert replay.errors == []
    assert _ledger_counts(runtime) == (1, 1, 1)
    assert board.project_calls == 1


@pytest.mark.asyncio
async def test_corrupt_readback_never_becomes_marker_only_ack(tmp_path: Path) -> None:
    run_id = "run-corrupt-readback-replay"
    runtime, board, _intent = _seed_projection(tmp_path, run_id=run_id)
    board.corrupt_readback = True

    first = await _settle(runtime, board, run_id)
    replay = await _settle(runtime, board, run_id)

    assert first.errors == [f"projection:{run_id}:RuntimeError"]
    assert replay.errors == [f"projection:{run_id}:RuntimeError"]
    assert board.task.metadata[GRAPH_PROJECTION_KEY]["run_id"] == run_id
    assert "projection_delta" not in board.task.metadata
    assert board.task.metadata["concurrent_nonprotocol_write"] is True
    assert _ledger_counts(runtime) == (1, 0, 0)
    assert board.project_calls == 1


@pytest.mark.asyncio
async def test_marker_without_prepared_target_is_not_retroactively_blessed(
    tmp_path: Path,
) -> None:
    run_id = "run-marker-only"
    runtime, board, intent = _seed_projection(tmp_path, run_id=run_id)
    marker = _projection_marker(intent)
    board.task = board.task.model_copy(
        update={
            "metadata": {
                **board.task.metadata,
                GRAPH_PROJECTION_KEY: marker,
                GRAPH_PROJECTION_HISTORY_KEY: {run_id: marker},
            }
        },
        deep=True,
    )

    report = await _settle(runtime, board, run_id)

    assert report.errors == [f"projection:{run_id}:RuntimeError"]
    assert _ledger_counts(runtime) == (0, 0, 0)
    assert board.project_calls == 0


@pytest.mark.asyncio
async def test_existing_ack_without_target_witness_is_reported_unproven(
    tmp_path: Path,
) -> None:
    run_id = "run-unproven-old-ack"
    runtime, board, intent = _seed_projection(tmp_path, run_id=run_id)
    marker = _projection_marker(intent)
    encoded_marker = json.dumps(marker, sort_keys=True, separators=(",", ":"))
    async with aiosqlite.connect(runtime.db_path) as db:
        await ensure_projection_ack_ledger(db)
        await db.execute(
            "INSERT INTO task_board_projection_acks"
            " (run_id, task_id, intent_sha256, board_receipt_sha256,"
            " board_receipt_json, acknowledged_at, schema_version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                intent["task_id"],
                intent["intent_sha256"],
                stable_sha256(marker),
                encoded_marker,
                NOW.isoformat(),
                PROJECTION_ACK_SCHEMA,
            ),
        )
        await db.commit()

    report = await _settle(runtime, board, run_id)

    assert report.errors == [f"projection:{run_id}:unproven_ack"]
    assert _ledger_counts(runtime) == (0, 0, 1)
    assert board.project_calls == 0
