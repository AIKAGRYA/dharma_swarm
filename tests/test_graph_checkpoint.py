"""Tests for dharma_swarm.graph.checkpoint -- atomic dispatch checkpoints and crash restore."""

import asyncio
import json

import pytest

from dharma_swarm.graph.checkpoint import DispatchCheckpoint, GraphCheckpointStore
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity


def _identity(**overrides: str) -> ExecutionIdentity:
    payload = {
        "task_id": "task-ckpt",
        "agent_id": "agent-ckpt",
        "session_id": "session-ckpt",
        "trace_id": "trace-ckpt",
        "correlation_id": "corr-ckpt",
        "run_id": "run-ckpt",
        "claim_id": "claim-ckpt",
        "idempotency_key": "idem-ckpt",
    }
    payload.update(overrides)
    return ExecutionIdentity.new(**payload)


# ---------------------------------------------------------------------------
# DispatchCheckpoint record
# ---------------------------------------------------------------------------


def test_dispatch_checkpoint_roundtrip():
    record = DispatchCheckpoint(
        run_id="r1",
        superstep=3,
        node_id="node-a",
        state_ref="state/r1/3.json",
        created_at="2026-07-05T00:00:00+00:00",
    )
    restored = DispatchCheckpoint.from_dict(record.to_dict())
    assert restored == record


def test_dispatch_checkpoint_is_frozen():
    record = DispatchCheckpoint(
        run_id="r1", superstep=0, node_id="n", state_ref="s", created_at="t"
    )
    with pytest.raises(Exception):
        record.superstep = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Checkpoint persistence
# ---------------------------------------------------------------------------


def test_checkpoint_creates_file(tmp_path):
    store = GraphCheckpointStore("run-file", persist_dir=tmp_path / "ckpt")
    path = store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")

    assert path.exists()
    data = json.loads(path.read_text())
    assert data["run_id"] == "run-file"
    assert len(data["checkpoints"]) == 1
    assert data["checkpoints"][0]["node_id"] == "a"


def test_checkpoint_leaves_no_tmp_files(tmp_path):
    persist = tmp_path / "ckpt"
    store = GraphCheckpointStore("run-atomic", persist_dir=persist)
    store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")
    store.checkpoint(superstep=1, node_id="b", state_ref="ref-1")

    leftovers = [p for p in persist.iterdir() if p.name != "state.json"]
    assert leftovers == []


def test_checkpoint_and_restore(tmp_path):
    persist = tmp_path / "ckpt"
    store = GraphCheckpointStore("run-restore", persist_dir=persist)
    store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")
    store.checkpoint(superstep=1, node_id="b", state_ref="ref-1")

    restored = GraphCheckpointStore.restore("run-restore", persist_dir=persist)

    assert restored.run_id == "run-restore"
    assert len(restored.checkpoints) == 2
    latest = restored.latest()
    assert latest is not None
    assert latest.superstep == 1
    assert latest.node_id == "b"
    assert latest.state_ref == "ref-1"


def test_restore_nonexistent_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        GraphCheckpointStore.restore("nonexistent", persist_dir=tmp_path / "nope")


def test_restore_after_further_checkpoints_sees_latest_state(tmp_path):
    persist = tmp_path / "ckpt"
    store = GraphCheckpointStore("run-latest", persist_dir=persist)
    store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")

    mid = GraphCheckpointStore.restore("run-latest", persist_dir=persist)
    assert len(mid.checkpoints) == 1

    store.checkpoint(superstep=1, node_id="b", state_ref="ref-1")
    final = GraphCheckpointStore.restore("run-latest", persist_dir=persist)
    assert len(final.checkpoints) == 2


def test_superstep_regression_raises(tmp_path):
    store = GraphCheckpointStore("run-regress", persist_dir=tmp_path / "ckpt")
    store.checkpoint(superstep=2, node_id="a", state_ref="ref-2")
    with pytest.raises(ValueError, match="regresses"):
        store.checkpoint(superstep=1, node_id="b", state_ref="ref-1")


def test_failed_write_rolls_back_in_memory_record(tmp_path, monkeypatch):
    import os as os_module

    store = GraphCheckpointStore("run-rollback", persist_dir=tmp_path / "ckpt")
    store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")

    def _boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os_module, "replace", _boom)
    with pytest.raises(OSError, match="disk full"):
        store.checkpoint(superstep=1, node_id="failed", state_ref="ref-failed")
    monkeypatch.undo()

    latest = store.latest()
    assert latest is not None
    assert latest.node_id == "a"

    store.checkpoint(superstep=1, node_id="b", state_ref="ref-1")
    restored = GraphCheckpointStore.restore("run-rollback", persist_dir=tmp_path / "ckpt")
    assert [c.node_id for c in restored.checkpoints] == ["a", "b"]


def test_latest_empty_is_none(tmp_path):
    store = GraphCheckpointStore("run-empty", persist_dir=tmp_path / "ckpt")
    assert store.latest() is None
    assert store.checkpoints == []


# ---------------------------------------------------------------------------
# Spine receipt hook
# ---------------------------------------------------------------------------


def test_checkpoint_records_runtime_receipt(tmp_path):
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    store = GraphCheckpointStore(
        "run-receipt",
        persist_dir=tmp_path / "ckpt",
        runtime_state=runtime,
        execution_identity=identity,
    )

    store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")

    ledger = asyncio.run(runtime.get_run_ledger(identity.run_id))
    assert ledger["identity"] is not None
    assert any(
        receipt.receipt_type == "workflow_checkpoint" and receipt.status == "checkpointed"
        for receipt in ledger["receipts"]
    )


def test_checkpoint_without_runtime_state_records_nothing(tmp_path):
    store = GraphCheckpointStore("run-noreceipt", persist_dir=tmp_path / "ckpt")
    path = store.checkpoint(superstep=0, node_id="a", state_ref="ref-0")
    assert path.exists()
