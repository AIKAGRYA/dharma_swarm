from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

import dharma_swarm.spine.identity as identity_module
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore
from dharma_swarm.runtime_state_effect_fence import (
    EFFECT_RECEIPT_ID_PREFIX,
    require_effect_fence_schema,
)
from dharma_swarm.spine.identity import ExecutionIdentity


def _identity(*, idempotency_key: str = "ordinary-idempotency") -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id="task-1",
        trace_id="trace-1",
        correlation_id="correlation-1",
        run_id="run-1",
        claim_id="claim-1",
        idempotency_key=idempotency_key,
        agent_id="agent-1",
        session_id="session-1",
    )


@pytest.mark.parametrize(
    "surface",
    ["receipt_identity", "raw_receipt", "idempotency_begin", "result_receipt"],
)
def test_generic_runtime_state_cannot_occupy_exact_effect_aliases(
    tmp_path, surface: str,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    receipt_id = EFFECT_RECEIPT_ID_PREFIX + "a" * 64
    identity = _identity()

    with pytest.raises(ValueError, match="reserved self-mod/exact-governance slot"):
        if surface == "receipt_identity":
            runtime.build_runtime_receipt(
                replace(identity, idempotency_key="idem_" + receipt_id),
                receipt_type="ordinary",
                status="completed",
            )
        elif surface == "raw_receipt":
            runtime.record_runtime_receipt_sync(
                RuntimeReceipt(
                    receipt_id="ordinary-receipt",
                    receipt_type="ordinary",
                    status="completed",
                    idempotency_key="idem_" + receipt_id,
                )
            )
        elif surface == "idempotency_begin":
            runtime.try_begin_idempotent_side_effect_sync(
                replace(identity, idempotency_key="idem_" + receipt_id),
                "ordinary-side-effect",
            )
        else:
            assert runtime.try_begin_idempotent_side_effect_sync(
                identity, "ordinary-side-effect"
            )
            runtime.complete_idempotent_side_effect_sync(
                identity,
                "ordinary-side-effect",
                result_receipt_id=receipt_id,
            )


def test_process_boot_id_rotates_when_pid_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_pid = identity_module.os.getpid()
    monkeypatch.setattr(identity_module.os, "getpid", lambda: original_pid)
    first = identity_module.process_boot_id()
    assert identity_module.process_boot_id() == first

    monkeypatch.setattr(identity_module.os, "getpid", lambda: original_pid + 1)
    second = identity_module.process_boot_id()

    assert second != first
    assert identity_module.process_boot_id() == second


def test_exact_effect_schema_rejects_cascading_receipt_sink(tmp_path) -> None:
    runtime_path = tmp_path / "runtime.db"
    RuntimeStateStore(runtime_path, include_memory_plane=False).init_db_sync()
    with sqlite3.connect(runtime_path) as database:
        original_sql = str(database.execute(
            "SELECT sql FROM sqlite_schema WHERE type='table'"
            " AND name='runtime_receipts'"
        ).fetchone()[0])
        database.execute("PRAGMA foreign_keys=OFF")
        database.execute("CREATE TABLE ordinary_owner (id TEXT PRIMARY KEY)")
        database.execute(
            "ALTER TABLE runtime_receipts RENAME TO runtime_receipts_original"
        )
        database.execute(
            original_sql.rsplit(")", 1)[0]
            + ", FOREIGN KEY (task_id) REFERENCES ordinary_owner(id)"
            " ON DELETE CASCADE)"
        )
        database.execute("DROP TABLE runtime_receipts_original")
        database.execute(
            "CREATE INDEX idx_runtime_receipts_run_created"
            " ON runtime_receipts(run_id, created_at)"
        )
        database.execute(
            "CREATE INDEX idx_runtime_receipts_trace_created"
            " ON runtime_receipts(trace_id, created_at)"
        )
        database.execute(
            "CREATE INDEX idx_runtime_receipts_idempotency"
            " ON runtime_receipts(idempotency_key)"
        )

        with pytest.raises(sqlite3.DatabaseError, match="sink schema is not exact"):
            require_effect_fence_schema(database)
