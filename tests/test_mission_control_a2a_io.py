from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from dharma_swarm import mission_control_a2a_io as io
from dharma_swarm.mission_control_a2a import A2ANativeExecutionRef, _SCAN_LIMIT
from dharma_swarm.mission_control_a2a_candidate import (
    load_exact_proposals,
    load_exact_proposals_from_connection,
)
from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
    MissionControlError,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sidecar(database: Path, suffix: str) -> Path:
    return Path(f"{database}{suffix}")


def _simple_database(path: Path, *, wal: bool = False) -> sqlite3.Connection | None:
    connection = sqlite3.connect(path)
    if wal:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        connection.execute("PRAGMA wal_autocheckpoint=0")
    connection.execute("CREATE TABLE values_table (id INTEGER PRIMARY KEY, value TEXT)")
    connection.execute("INSERT INTO values_table VALUES (1, 'old')")
    connection.commit()
    if wal:
        return connection
    connection.close()
    return None


def _query(
    database: Path,
    *queries: io.ReadQuery,
    max_database_bytes: int = io._MAX_DATABASE_BYTES,
) -> tuple[tuple[sqlite3.Row, ...], ...]:
    return io._read_only_queries(
        database,
        "test",
        tuple(queries),
        max_database_bytes=max_database_bytes,
    )


def _mission_database(path: Path, status: object) -> None:
    metadata = json.dumps(
        {"mission_id": "mission-1", "schema_version": MISSION_CONTROL_SCHEMA},
        sort_keys=True,
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE sessions ("
            "session_id TEXT PRIMARY KEY, status, metadata_json TEXT)",
        )
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            ("mission:mission-1", status, metadata),
        )


def test_clean_wal_database_uses_noncreating_immutable_read(tmp_path: Path) -> None:
    database = tmp_path / "clean.sqlite3"
    writer = _simple_database(database, wal=True)
    assert writer is not None
    writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    writer.close()
    wal = _sidecar(database, "-wal")
    shm = _sidecar(database, "-shm")
    assert not wal.exists() and not shm.exists()
    before = (database.stat(), _sha(database))

    (rows,) = _query(
        database,
        io.ReadQuery("SELECT value FROM values_table WHERE id = 1"),
    )

    assert rows[0][0] == "old"
    after = database.stat()
    assert (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) == (
        before[0].st_dev, before[0].st_ino, before[0].st_size,
        before[0].st_mtime_ns, before[0].st_ctime_ns,
    )
    assert _sha(database) == before[1]
    assert not wal.exists() and not shm.exists()


def test_active_wal_row_is_visible_without_durable_writes(tmp_path: Path) -> None:
    database = tmp_path / "active.sqlite3"
    writer = _simple_database(database, wal=True)
    assert writer is not None
    writer.execute("UPDATE values_table SET value = 'committed' WHERE id = 1")
    writer.commit()
    wal = _sidecar(database, "-wal")
    shm = _sidecar(database, "-shm")
    before = (_sha(database), _sha(wal), wal.stat().st_ino, shm.stat().st_ino)
    try:
        (rows,) = _query(database, io.ReadQuery("SELECT value FROM values_table"))
        assert rows[0][0] == "committed"
        assert (_sha(database), _sha(wal), wal.stat().st_ino) == before[:3]
        assert shm.stat().st_ino == before[3]
        assert stat.S_ISREG(shm.lstat().st_mode)
    finally:
        writer.close()


def test_existing_wal_without_shm_rebuilds_coordination_only(tmp_path: Path) -> None:
    database = tmp_path / "wal-without-shm.sqlite3"
    writer = _simple_database(database, wal=True)
    assert writer is not None
    writer.execute("UPDATE values_table SET value = 'wal-only' WHERE id = 1")
    writer.commit()
    wal = _sidecar(database, "-wal")
    shm = _sidecar(database, "-shm")
    main_bytes, wal_bytes = database.read_bytes(), wal.read_bytes()
    writer.close()
    database.write_bytes(main_bytes)
    wal.write_bytes(wal_bytes)
    shm.unlink(missing_ok=True)
    before = (_sha(database), _sha(wal), wal.stat().st_ino)

    (rows,) = _query(database, io.ReadQuery("SELECT value FROM values_table"))

    assert rows[0][0] == "wal-only"
    assert (_sha(database), _sha(wal), wal.stat().st_ino) == before


def test_connection_capability_never_escapes(tmp_path: Path) -> None:
    database = tmp_path / "closed-plan.sqlite3"
    _simple_database(database)

    results = _query(
        database,
        io.ReadQuery("SELECT value FROM values_table"),
        io.ReadQuery("SELECT count(*) FROM values_table"),
    )

    assert type(results) is tuple
    assert all(type(rows) is tuple for rows in results)
    assert all(isinstance(row, sqlite3.Row) for rows in results for row in rows)
    assert not any(
        isinstance(value, (sqlite3.Connection, sqlite3.Cursor))
        or callable(value)
        for rows in results
        for row in rows
        for value in row
    )


def test_query_plan_rejects_adapter_capability_before_open(tmp_path: Path) -> None:
    database = tmp_path / "adapter.sqlite3"
    escaped = tmp_path / "adapter-ran"
    _simple_database(database)

    class SideEffectingAdapter:
        def __conform__(self, _protocol: object) -> str:
            escaped.write_text("adapter executed", encoding="utf-8")
            return "old"

    with pytest.raises(MissionControlError, match="query plan is invalid"):
        _query(
            database,
            io.ReadQuery(
                "SELECT value FROM values_table WHERE value = ?",
                (SideEffectingAdapter(),),
            ),
        )

    assert not escaped.exists()


@pytest.mark.parametrize(
    "query",
    (
        io.ReadQuery("SELECT '\ud800'"),
        io.ReadQuery("SELECT ?", ("\ud800",)),
    ),
)
def test_query_plan_rejects_non_utf8_text(
    tmp_path: Path,
    query: io.ReadQuery,
) -> None:
    database = tmp_path / "non-utf8.sqlite3"
    _simple_database(database)

    with pytest.raises(MissionControlError, match="query plan is invalid"):
        _query(database, query)


@pytest.mark.parametrize(
    "statement",
    (
        "UPDATE values_table SET value = 'forbidden' WHERE id = 1",
        "CREATE TABLE forbidden (value TEXT)",
        "PRAGMA user_version=2",
        "ATTACH DATABASE ':memory:' AS foreign_db",
        "ROLLBACK",
    ),
)
def test_query_plan_rejects_mutation_and_escape(
    tmp_path: Path,
    statement: str,
) -> None:
    database = tmp_path / "query-only.sqlite3"
    _simple_database(database)
    before = _sha(database)

    with pytest.raises(MissionControlError, match="forbidden SQLite action"):
        _query(database, io.ReadQuery(statement))

    assert _sha(database) == before


def test_attach_escape_cannot_create_external_database(tmp_path: Path) -> None:
    database = tmp_path / "attach-source.sqlite3"
    escaped = tmp_path / "escaped.sqlite3"
    _simple_database(database)

    with pytest.raises(MissionControlError, match="forbidden SQLite action"):
        _query(
            database,
            io.ReadQuery("ATTACH DATABASE ? AS escaped", (str(escaped),)),
        )
    assert not escaped.exists()


def test_result_byte_bound_is_transaction_wide(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "results.sqlite3"
    _simple_database(database)
    monkeypatch.setattr(io, "_SQLITE_MAX_RESULT_BYTES", 250)

    with pytest.raises(MissionControlError, match="result bound"):
        _query(
            database,
            io.ReadQuery("SELECT printf('%080d', 1)"),
            io.ReadQuery("SELECT printf('%080d', 2)"),
        )


def test_vm_budget_interrupts_recursive_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "budget.sqlite3"
    _simple_database(database)
    monkeypatch.setattr(io, "_SQLITE_VM_OP_BUDGET", 2_000)
    monkeypatch.setattr(io, "_SQLITE_PROGRESS_INTERVAL", 100)

    with pytest.raises(MissionControlError, match="read budget was exceeded"):
        _query(
            database,
            io.ReadQuery(
                "WITH RECURSIVE counter(value) AS ("
                "VALUES(1) UNION ALL SELECT value + 1 FROM counter WHERE value < 100000"
                ") SELECT sum(value) FROM counter",
            ),
        )


def test_elapsed_deadline_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "deadline.sqlite3"
    _simple_database(database)
    monkeypatch.setattr(io, "_SQLITE_READ_DEADLINE_SECONDS", -1.0)

    with pytest.raises(MissionControlError, match="deadline expired"):
        _query(database, io.ReadQuery("SELECT value FROM values_table"))


def test_immutable_state_drift_refuses_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "drift.sqlite3"
    _simple_database(database)
    original = io._regular_state
    main_reads = 0

    def drift(path: Path, label: str):
        nonlocal main_reads
        state = original(path, label)
        if path == database and state is not None:
            main_reads += 1
            if main_reads > 1:
                return (*state[:3], state[3] + 1, state[4])
        return state

    monkeypatch.setattr(io, "_regular_state", drift)
    with pytest.raises(MissionControlError, match="changed during immutable read"):
        _query(database, io.ReadQuery("SELECT value FROM values_table"))


def test_real_scale_sparse_database_is_admitted(tmp_path: Path) -> None:
    database = tmp_path / "large.sqlite3"
    _simple_database(database)
    os.truncate(database, 614_383_616)

    (rows,) = _query(database, io.ReadQuery("SELECT value FROM values_table"))

    assert rows[0][0] == "old"


def test_database_larger_than_global_bound_refuses(tmp_path: Path) -> None:
    database = tmp_path / "too-large.sqlite3"
    _simple_database(database)
    os.truncate(database, io._MAX_DATABASE_BYTES + 1)

    with pytest.raises(MissionControlError, match="exceeds its read bound"):
        _query(database, io.ReadQuery("SELECT 1"))


def test_wal_only_logical_size_exceeding_bound_refuses(tmp_path: Path) -> None:
    database = tmp_path / "wal-logical.sqlite3"
    writer = _simple_database(database, wal=True)
    assert writer is not None
    writer.execute("CREATE TABLE extra (payload BLOB)")
    writer.execute("INSERT INTO extra VALUES (zeroblob(20000))")
    writer.commit()
    try:
        assert database.stat().st_size <= 8_192
        with pytest.raises(MissionControlError, match="logical bound"):
            _query(
                database,
                io.ReadQuery("SELECT 1"),
                max_database_bytes=8_192,
            )
    finally:
        writer.close()


@pytest.mark.parametrize(
    ("suffix", "size"),
    (("-wal", io._MAX_WAL_BYTES + 1), ("-shm", io._MAX_SHM_BYTES + 1)),
)
def test_oversized_sidecars_refuse(tmp_path: Path, suffix: str, size: int) -> None:
    database = tmp_path / "oversized.sqlite3"
    _simple_database(database)
    _sidecar(database, "-wal").touch()
    _sidecar(database, suffix).touch()
    os.truncate(_sidecar(database, suffix), size)

    with pytest.raises(MissionControlError, match="exceeds its read bound"):
        _query(database, io.ReadQuery("SELECT 1"))


@pytest.mark.parametrize("suffix", ("-wal", "-shm", "-journal"))
def test_sidecar_symlink_refuses(tmp_path: Path, suffix: str) -> None:
    database = tmp_path / "unsafe-sidecar.sqlite3"
    target = tmp_path / "target"
    _simple_database(database)
    target.write_bytes(b"")
    _sidecar(database, suffix).symlink_to(target)

    with pytest.raises(MissionControlError, match="snapshot is not regular"):
        _query(database, io.ReadQuery("SELECT 1"))


def test_main_symlink_regular_journal_and_orphan_shm_refuse(tmp_path: Path) -> None:
    real = tmp_path / "real.sqlite3"
    linked = tmp_path / "linked.sqlite3"
    _simple_database(real)
    linked.symlink_to(real)
    with pytest.raises(MissionControlError, match="not a regular file"):
        _query(linked, io.ReadQuery("SELECT 1"))

    journal_db = tmp_path / "journal.sqlite3"
    _simple_database(journal_db)
    _sidecar(journal_db, "-journal").touch()
    with pytest.raises(MissionControlError, match="rollback journal"):
        _query(journal_db, io.ReadQuery("SELECT 1"))

    orphan_db = tmp_path / "orphan.sqlite3"
    _simple_database(orphan_db)
    _sidecar(orphan_db, "-shm").touch()
    with pytest.raises(MissionControlError, match="orphaned SHM"):
        _query(orphan_db, io.ReadQuery("SELECT 1"))


def test_absent_and_malformed_databases_remain_noncreating(tmp_path: Path) -> None:
    absent = tmp_path / "absent.sqlite3"
    with pytest.raises(MissionControlError, match="database is unavailable"):
        _query(absent, io.ReadQuery("SELECT 1"))
    assert not absent.exists()

    malformed = tmp_path / "malformed.sqlite3"
    malformed.write_bytes(b"not sqlite")
    before = malformed.read_bytes()
    with pytest.raises(MissionControlError, match="unavailable or malformed"):
        _query(malformed, io.ReadQuery("SELECT 1"))
    assert malformed.read_bytes() == before


def test_semantic_job_bound_counts_utf8_bytes_before_fetch(tmp_path: Path) -> None:
    database = tmp_path / "semantic.sqlite3"
    envelope_json = json.dumps({"text": "界" * 1_500}, ensure_ascii=False)
    assert len(envelope_json) < 2_000 < len(envelope_json.encode("utf-8"))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE semantic_jobs ("
            "event_id TEXT PRIMARY KEY, envelope_sha256 TEXT, "
            "envelope_json, status TEXT)",
        )
        connection.execute(
            "INSERT INTO semantic_jobs VALUES (?, ?, ?, ?)",
            ("event-1", "a" * 64, envelope_json, "PENDING"),
        )

    with pytest.raises(MissionControlError, match="envelope exceeds its read bound"):
        io.read_semantic_job(database, "event-1", max_bytes=2_000)


def test_active_mission_is_required_exactly(tmp_path: Path) -> None:
    database = tmp_path / "active.sqlite3"
    _mission_database(database, "active")
    io.require_mission(database, "mission-1")


@pytest.mark.parametrize("status", ("completed", "inactive", 1, None))
def test_inactive_mission_refuses(tmp_path: Path, status: object) -> None:
    database = tmp_path / "inactive.sqlite3"
    _mission_database(database, status)
    with pytest.raises(MissionControlError, match="is not active canonically"):
        io.require_mission(database, "mission-1")


def test_candidate_query_preserves_order_cardinality_and_slot_rows(
    tmp_path: Path,
) -> None:
    database = tmp_path / "proposals.sqlite3"
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE runtime_receipts (
            receipt_id TEXT, receipt_type TEXT, status TEXT, run_id TEXT,
            task_id TEXT, trace_id TEXT, correlation_id TEXT,
            causation_id TEXT, parent_run_id TEXT, agent_id TEXT,
            idempotency_key TEXT, side_effect_key TEXT, payload_json TEXT,
            created_at TEXT
        );
        CREATE TABLE idempotency_records (
            idempotency_key TEXT, side_effect_key TEXT, run_id TEXT,
            task_id TEXT, trace_id TEXT, correlation_id TEXT, status TEXT,
            result_receipt_id TEXT, metadata_json TEXT, created_at TEXT,
            updated_at TEXT
        );
        """,
    )
    created_at = "2026-08-28T00:00:00+00:00"

    def add_proposal(receipt_id: str, side_effect_key: str) -> None:
        connection.execute(
            "INSERT INTO runtime_receipts VALUES "
            "(?, 'self_mod_proposal', 'recorded', 'run', 'task', 'trace', "
            "'correlation', 'cause', 'parent', 'agent', 'idem', ?, '{}', ?)",
            (receipt_id, side_effect_key, created_at),
        )

    def add_slot(side_effect_key: str, index: int) -> None:
        connection.execute(
            "INSERT INTO idempotency_records VALUES "
            "(?, ?, 'run', 'task', 'trace', 'correlation', 'recorded', "
            "'result', '{}', ?, ?)",
            (f"slot-{side_effect_key}-{index}", side_effect_key, created_at, created_at),
        )

    # Proposal timestamps tie. Slot rowids deliberately begin with proposal B,
    # which used to reorder the joined result ahead of proposal A.
    add_proposal("proposal-a", "effect-a")
    add_proposal("proposal-b", "effect-b")
    add_proposal("proposal-without-slot", "effect-none")
    add_proposal("duplicate-receipt", "effect-duplicate")
    add_proposal("duplicate-receipt", "effect-duplicate")
    add_slot("effect-b", 0)
    add_slot("effect-a", 0)
    add_slot("effect-a", 1)
    add_slot("effect-duplicate", 0)
    connection.commit()

    ref = A2ANativeExecutionRef(
        mission_id="mission",
        task_id="task",
        agent_uid="agent",
        packet_id="packet",
        correlation_id="correlation",
        delivery_id="delivery",
        proposal_id="proposal",
        content_sha256="a" * 64,
    )
    expected = load_exact_proposals_from_connection(connection, ref, scan_limit=10)
    connection.close()

    actual = load_exact_proposals(database, ref, scan_limit=10)

    assert actual == expected
    assert [item.receipt.receipt_id for item in actual] == [
        "proposal-a",
        "proposal-b",
        "proposal-without-slot",
        "duplicate-receipt",
        "duplicate-receipt",
    ]
    assert [len(item.idempotency_rows) for item in actual] == [2, 1, 0, 1, 1]


def test_candidate_join_row_budget_covers_saturation_fanout() -> None:
    assert io._SQLITE_MAX_RESULT_ROWS >= (_SCAN_LIMIT + 1) * 3
