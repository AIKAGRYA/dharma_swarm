"""Exact crash/replay tests for the non-campaign legacy Board lane."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.graph import reconcile_board_legacy as legacy
from dharma_swarm.graph.reconciler import GraphReconciler
from dharma_swarm.models import TaskPriority
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.task_board_effect_commit import EFFECT_COMMIT_SCHEMA

NOW = datetime(2026, 8, 24, 2, 0, 0, tzinfo=timezone.utc)


async def _seed_legacy_attempt(
    tmp_path: Path,
    *,
    active_claim: bool = True,
) -> tuple[RuntimeStateStore, TaskBoard, str, str, str]:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    runtime.init_db_sync()
    board = TaskBoard(tmp_path / "task_board.db")
    await board.init_db()
    prerequisite = await board.create("preserved dependency")
    task = await board.create(
        "legacy exact replay",
        description="full predecessor fields survive",
        priority=TaskPriority.URGENT,
        created_by="legacy-fixture",
        depends_on=[prerequisite.id],
        metadata={"fixture_owner": "preserved"},
    )
    run_id = "run-legacy-exact"
    claim_id = "claim-legacy-exact"
    agent_id = "agent-legacy-exact"
    metadata = {
        "fixture_owner": "preserved",
        "run_id": run_id,
        "runtime_run_id": run_id,
        "claim_id": claim_id,
        "agent_id": agent_id,
    }
    if active_claim:
        metadata["active_claim"] = {
            "claim_id": claim_id,
            "agent_id": agent_id,
            "claimed_at": (NOW - timedelta(minutes=10)).isoformat(),
        }
    await board.assign(task.id, agent_id, metadata=metadata)
    legacy_metadata = {
        "legacy_no_identity_allowed": True,
        "runtime_spine_status": "legacy_no_identity",
    }
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs"
            " (run_id, session_id, task_id, claim_id, parent_run_id, assigned_by,"
            " assigned_to, status, started_at, metadata_json)"
            " VALUES (?, '', ?, ?, '', '', ?, 'claimed', ?, ?)",
            (
                run_id,
                task.id,
                claim_id,
                agent_id,
                (NOW - timedelta(minutes=10)).isoformat(),
                json.dumps(legacy_metadata),
            ),
        )
        db.execute(
            "INSERT INTO task_claims"
            " (claim_id, task_id, session_id, agent_id, status, claimed_at,"
            " retry_count, metadata_json) VALUES (?, ?, '', ?, 'claimed', ?, 0, ?)",
            (
                claim_id,
                task.id,
                agent_id,
                (NOW - timedelta(minutes=10)).isoformat(),
                json.dumps(legacy_metadata),
            ),
        )
        db.commit()
    return runtime, board, task.id, run_id, claim_id


def _ledger_counts(runtime: RuntimeStateStore, board: TaskBoard) -> tuple[int, int, int]:
    with sqlite3.connect(runtime.db_path) as db:
        intents = db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_intents"
        ).fetchone()[0]
        acks = db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_acks"
        ).fetchone()[0]
    with sqlite3.connect(board._db_path) as db:
        effects = db.execute(
            "SELECT COUNT(*) FROM task_board_effect_commits"
        ).fetchone()[0]
    return int(intents), int(acks), int(effects)


def _load_intent(runtime: RuntimeStateStore, run_id: str) -> dict:
    with sqlite3.connect(runtime.db_path) as db:
        raw = db.execute(
            "SELECT intent_json FROM legacy_task_board_settlement_intents"
            " WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
    return json.loads(raw)


async def test_exact_legacy_requeue_commits_full_board_effect_before_ack(
    tmp_path: Path,
) -> None:
    runtime, board, task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.errors == []
    assert report.requeued_runs == [run_id]
    assert _ledger_counts(runtime, board) == (1, 1, 1)
    task = await board.get(task_id)
    assert task is not None
    assert task.status.value == "pending"
    assert task.assigned_to is None
    assert "active_claim" not in task.metadata
    assert task.metadata["fixture_owner"] == "preserved"
    intent = _load_intent(runtime, run_id)
    assert intent["predecessor_snapshot"]["description"] == (
        "full predecessor fields survive"
    )
    assert intent["predecessor_snapshot"]["priority"] == "urgent"
    assert intent["predecessor_snapshot"]["created_by"] == "legacy-fixture"
    assert len(intent["predecessor_snapshot"]["depends_on"]) == 1
    assert intent["target_snapshot"] == task.model_dump(mode="json")
    with sqlite3.connect(runtime.db_path) as db:
        proof = db.execute(
            "SELECT proof_mode, effect_receipt_json"
            " FROM legacy_task_board_settlement_acks WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert proof[0] == legacy.LEGACY_SETTLEMENT_PROOF_MODE
    receipt = json.loads(proof[1])
    assert receipt["expected_snapshot"] == intent["predecessor_snapshot"]
    assert receipt["target_snapshot"] == intent["target_snapshot"]


async def test_runtime_intent_survives_crash_before_board_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)
    original = legacy.commit_locked_task_effect
    calls = 0

    async def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected crash before Board CAS")
        return await original(*args, **kwargs)

    monkeypatch.setattr(legacy, "commit_locked_task_effect", fail_once)
    reconciler = GraphReconciler(runtime, task_board=board)

    first = await reconciler.reconcile(now=NOW)
    assert first.errors == [f"legacy_projection:{run_id}:RuntimeError"]
    assert _ledger_counts(runtime, board) == (1, 0, 0)
    assert (await board.get(task_id)).status.value == "assigned"

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))
    assert replay.errors == []
    assert calls == 2
    assert _ledger_counts(runtime, board) == (1, 1, 1)
    assert (await board.get(task_id)).status.value == "pending"


async def test_board_commit_before_ack_replays_without_second_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)
    original = legacy._append_ack
    calls = 0

    async def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected crash after Board commit")
        return await original(*args, **kwargs)

    monkeypatch.setattr(legacy, "_append_ack", fail_once)
    reconciler = GraphReconciler(runtime, task_board=board)

    first = await reconciler.reconcile(now=NOW)
    assert first.errors == [f"legacy_projection:{run_id}:RuntimeError"]
    committed = await board.get(task_id)
    assert committed is not None and committed.status.value == "pending"
    committed_updated_at = committed.updated_at
    assert _ledger_counts(runtime, board) == (1, 0, 1)

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))
    assert replay.errors == []
    assert calls == 2
    assert _ledger_counts(runtime, board) == (1, 1, 1)
    assert (await board.get(task_id)).updated_at == committed_updated_at


async def test_reassignment_after_crash_cannot_be_overwritten_by_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)

    async def crash(*args, **kwargs):
        raise RuntimeError("injected crash before Board CAS")

    monkeypatch.setattr(legacy, "commit_locked_task_effect", crash)
    reconciler = GraphReconciler(runtime, task_board=board)
    first = await reconciler.reconcile(now=NOW)
    assert first.errors == [f"legacy_projection:{run_id}:RuntimeError"]
    monkeypatch.undo()

    next_metadata = {
        "fixture_owner": "new-attempt",
        "active_claim": {"claim_id": "claim-new", "agent_id": "agent-new"},
    }
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET assigned_to = 'agent-new', metadata = ?, updated_at = ?"
            " WHERE id = ?",
            (
                json.dumps(next_metadata),
                (NOW + timedelta(seconds=1)).isoformat(),
                task_id,
            ),
        )
        db.commit()

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=2))
    assert replay.errors == [f"legacy_projection:{run_id}:RuntimeError"]
    current = await board.get(task_id)
    assert current is not None
    assert current.assigned_to == "agent-new"
    assert current.metadata == next_metadata
    assert _ledger_counts(runtime, board) == (1, 0, 0)


async def test_pending_legacy_intent_with_unavailable_board_is_red(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, _task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)

    async def crash(*args, **kwargs):
        raise RuntimeError("injected crash before Board CAS")

    monkeypatch.setattr(legacy, "commit_locked_task_effect", crash)
    reconciler = GraphReconciler(runtime, task_board=board)
    await reconciler.reconcile(now=NOW)
    reconciler._task_board = None

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))

    assert replay.errors == [
        f"legacy_projection:{run_id}:task_board_unavailable"
    ]
    assert reconciler.boot_census_succeeded is False
    assert _ledger_counts(runtime, board) == (1, 0, 0)


async def test_forged_board_commit_receipt_cannot_authorize_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)

    async def crash(*args, **kwargs):
        raise RuntimeError("injected crash before Board CAS")

    monkeypatch.setattr(legacy, "commit_locked_task_effect", crash)
    reconciler = GraphReconciler(runtime, task_board=board)
    await reconciler.reconcile(now=NOW)
    monkeypatch.undo()
    intent = _load_intent(runtime, run_id)
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "INSERT INTO task_board_effect_commits"
            " (effect_id, effect_kind, task_id, authority_sha256,"
            " expected_snapshot_sha256, expected_snapshot_json,"
            " target_snapshot_sha256, target_snapshot_json, effect_payload_sha256,"
            " effect_payload_json, committed_at, receipt_sha256, receipt_json,"
            " schema_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                intent["effect_id"],
                intent["effect_kind"],
                task_id,
                intent["authority_sha256"],
                "0" * 64,
                "{}",
                "1" * 64,
                "{}",
                "2" * 64,
                "{}",
                NOW.isoformat(),
                "3" * 64,
                "{}",
                EFFECT_COMMIT_SCHEMA,
            ),
        )
        db.commit()

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))

    assert replay.errors == [f"legacy_projection:{run_id}:ValueError"]
    assert (await board.get(task_id)).status.value == "assigned"
    assert _ledger_counts(runtime, board) == (1, 0, 1)


async def test_legacy_source_without_exact_active_claim_stays_runtime_live(
    tmp_path: Path,
) -> None:
    runtime, board, _task_id, run_id, _claim_id = await _seed_legacy_attempt(
        tmp_path,
        active_claim=False,
    )

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.errors == [f"run:{run_id}:ValueError"]
    with sqlite3.connect(runtime.db_path) as db:
        status = db.execute(
            "SELECT status FROM delegation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        intents = db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_intents"
        ).fetchone()[0]
    assert status == "claimed"
    assert intents == 0
    assert _ledger_counts(runtime, board) == (0, 0, 0)


async def test_restored_live_claim_cannot_authorize_pending_legacy_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, task_id, run_id, claim_id = await _seed_legacy_attempt(tmp_path)

    async def crash(*args, **kwargs):
        raise RuntimeError("injected crash before Board commit")

    monkeypatch.setattr(legacy, "commit_locked_task_effect", crash)
    reconciler = GraphReconciler(runtime, task_board=board)
    first = await reconciler.reconcile(now=NOW)
    assert first.errors == [f"legacy_projection:{run_id}:RuntimeError"]
    monkeypatch.undo()
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "UPDATE task_claims SET status = 'running', recovered_at = NULL"
            " WHERE claim_id = ?",
            (claim_id,),
        )
        db.commit()

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))

    assert replay.errors == [f"legacy_projection:{run_id}:ValueError"]
    assert (await board.get(task_id)).status.value == "assigned"
    assert _ledger_counts(runtime, board) == (1, 0, 0)


async def test_runtime_writer_fence_survives_authorize_through_board_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, board, task_id, run_id, _claim_id = await _seed_legacy_attempt(tmp_path)
    original = legacy.commit_locked_task_effect
    mutation_was_fenced = False

    async def attempt_interleaving_mutation(*args, **kwargs):
        nonlocal mutation_was_fenced
        with sqlite3.connect(runtime.db_path, timeout=0.05) as attacker:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                attacker.execute(
                    "UPDATE delegation_runs SET status = 'claimed' WHERE run_id = ?",
                    (run_id,),
                )
                attacker.commit()
        mutation_was_fenced = True
        return await original(*args, **kwargs)

    monkeypatch.setattr(
        legacy,
        "commit_locked_task_effect",
        attempt_interleaving_mutation,
    )

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.errors == []
    assert mutation_was_fenced is True
    assert (await board.get(task_id)).status.value == "pending"
    assert _ledger_counts(runtime, board) == (1, 1, 1)
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT status FROM delegation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()[0] == "failed"
