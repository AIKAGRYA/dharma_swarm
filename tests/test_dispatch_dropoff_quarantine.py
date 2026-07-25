"""dispatch_dropoff quarantine — loop-closure-2026-06 residual (item 1).

Proves: dry-run mutates nothing, --execute quarantines only pre-cutoff rows,
a receipt is written with correct counts + rowid sha256, the cybernetics_codex
audit excludes quarantined rows while reporting them separately, and re-runs
are idempotent. Runs entirely against a fixture sqlite DB built from the real
delegation_runs DDL (the runtime DB is absent on repo/CI hosts by design).
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from dharma_swarm.cybernetics_codex import build_audit, read_runtime_summary
from dharma_swarm.cybernetics_codex_format import format_markdown
from dharma_swarm.loop_closure_quarantine import rowids_sha256
from dharma_swarm.runtime_state import _DELEGATION_RUNS_DDL
from scripts.runtime import dispatch_dropoff_quarantine as tool

CUTOFF = "2026-06-18T00:00:00Z"


def _seed_fixture_db(path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(_DELEGATION_RUNS_DDL)
    rows = [
        # 3 historical dropoffs older than CUTOFF (mixed tz suffix styles, and
        # one dated only by started_at — coalesce(completed_at, started_at)).
        ("old_drop_1", "failed", "dispatch_dropoff", "2026-01-05T00:00:00Z", "2026-01-05T00:01:00Z"),
        ("old_drop_2", "failed", "dispatch_dropoff", "2026-02-01T00:00:00+00:00", "2026-02-01T00:01:00+00:00"),
        ("old_drop_3", "failed", "dispatch_dropoff", "2026-03-01T00:00:00Z", None),
        # 1 fresh dropoff at/after CUTOFF — must NEVER be quarantined.
        ("fresh_drop", "failed", "dispatch_dropoff", "2026-07-02T00:00:00Z", "2026-07-02T00:01:00Z"),
        # 1 undated (unparseable) dropoff — never quarantine what can't be dated.
        ("undated_drop", "failed", "dispatch_dropoff", "not-a-timestamp", None),
        # Non-dropoff rows the tool must not touch.
        ("old_timeout", "failed", "claim_timeout", "2026-01-06T00:00:00Z", "2026-01-06T00:01:00Z"),
        ("run_ok_1", "completed", "", "2026-06-20T00:00:00Z", "2026-06-20T00:01:00Z"),
        ("run_ok_2", "completed", "", "2026-07-01T00:00:00Z", "2026-07-01T00:01:00Z"),
    ]
    conn.executemany(
        "insert into delegation_runs "
        "(run_id, task_id, assigned_to, status, started_at, completed_at, failure_code) "
        "values (?, ?, 'agent', ?, ?, ?, ?)",
        [(run_id, f"task_{run_id}", status, started, completed, code)
         for run_id, status, code, started, completed in rows],
    )
    conn.commit()
    conn.close()


@pytest.fixture
def fixture_db(tmp_path):
    db = tmp_path / "runtime.db"
    _seed_fixture_db(db)
    return db


def _columns(db) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        return {row[1] for row in conn.execute("pragma table_info(delegation_runs)")}
    finally:
        conn.close()


def _run(db, *extra: str) -> int:
    return tool.main(["--db", str(db), "--before", CUTOFF, *extra])


def test_dry_run_mutates_nothing(fixture_db, capsys):
    before_bytes = fixture_db.read_bytes()

    assert _run(fixture_db) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["present"] is True
    assert out["executed"] is False
    assert out["candidates"] == 3
    assert out["quarantined_now"] == 0
    assert out["dropoff_live_before"] == 5
    assert out["dropoff_live_after"] == 5
    assert out["dropoff_fresh_live_kept"] == 1
    assert out["dropoff_undated_kept"] == 1
    # Dry-run touches nothing — not even the schema migration.
    assert "quarantined_at" not in _columns(fixture_db)
    assert fixture_db.read_bytes() == before_bytes


def test_execute_quarantines_only_pre_cutoff_rows_with_receipt(fixture_db, tmp_path, capsys):
    receipt_dir = tmp_path / "receipts"

    assert _run(fixture_db, "--execute", "--receipt-dir", str(receipt_dir)) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["executed"] is True
    assert out["quarantined_now"] == 3
    assert out["dropoff_live_before"] == 5
    assert out["dropoff_live_after"] == 2  # fresh + undated stay live
    assert out["dropoff_quarantined_total_after"] == 3

    conn = sqlite3.connect(fixture_db)
    quarantined = dict(
        conn.execute(
            "select run_id, quarantine_reason from delegation_runs "
            "where quarantined_at is not null and quarantined_at != ''"
        ).fetchall()
    )
    quarantined_rowids = [
        int(r[0])
        for r in conn.execute(
            "select rowid from delegation_runs "
            "where quarantined_at is not null and quarantined_at != ''"
        )
    ]
    conn.close()
    assert set(quarantined) == {"old_drop_1", "old_drop_2", "old_drop_3"}
    assert all("loop-closure-2026-06" in reason for reason in quarantined.values())

    # The quarantine receipt the track item demands: counts, cutoff, db path,
    # sha256 of the quarantined-rowid list.
    receipts = list(receipt_dir.glob("dispatch_dropoff_quarantine_*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["db_path"] == str(fixture_db)
    assert receipt["cutoff"] == CUTOFF
    assert receipt["quarantined_now"] == 3
    assert receipt["dropoff_live_before"] == 5
    assert receipt["dropoff_live_after"] == 2
    assert receipt["quarantined_rowids_sha256"] == rowids_sha256(quarantined_rowids)


def test_audit_excludes_quarantined_but_reports_them_separately(fixture_db, tmp_path, capsys):
    _run(fixture_db, "--execute", "--receipt-dir", str(tmp_path / "receipts"))
    capsys.readouterr()

    summary = read_runtime_summary(fixture_db)
    live_counts = {
        str(r.get("failure_code")): int(r.get("count") or 0)
        for r in summary["failure_codes"]
    }
    # Live count excludes quarantined-historical rows...
    assert live_counts["dispatch_dropoff"] == 2
    assert live_counts["claim_timeout"] == 1
    # ...while the quarantined tally is reported separately, never hidden.
    assert summary["quarantine"]["supported"] is True
    assert summary["quarantine"]["dispatch_dropoff_quarantined"] == 3
    assert summary["quarantine"]["failed_rows_quarantined"] == 3

    # End-to-end: the audit packet's loop 1 blocker and the markdown both carry
    # dropoff_live / dropoff_quarantined_historical.
    state = tmp_path / ".dharma"
    (state / "state").mkdir(parents=True)
    (state / "state" / "runtime.db").write_bytes(fixture_db.read_bytes())
    report = build_audit(repo_root=tmp_path, state_dir=state)
    loop1 = report["loop_statuses"][0]
    assert "dispatch_dropoff_quarantined_historical=3" in loop1["blocker"]
    markdown = format_markdown(report)
    assert "dropoff_live=`2`" in markdown
    assert "dropoff_quarantined_historical=`3`" in markdown


def test_rerun_is_idempotent(fixture_db, tmp_path, capsys):
    receipt_dir = tmp_path / "receipts"
    _run(fixture_db, "--execute", "--receipt-dir", str(receipt_dir))
    capsys.readouterr()

    assert _run(fixture_db, "--execute", "--receipt-dir", str(receipt_dir)) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["candidates"] == 0
    assert out["quarantined_now"] == 0
    assert out["dropoff_quarantined_prior"] == 3
    assert out["dropoff_quarantined_total_after"] == 3


def test_missing_db_is_graceful_absence(tmp_path, capsys):
    missing = tmp_path / "nope" / "runtime.db"

    assert _run(missing) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["present"] is False
    assert "nothing to quarantine" in out["detail"]


def test_future_cutoff_is_refused(fixture_db):
    with pytest.raises(SystemExit) as excinfo:
        tool.main(["--db", str(fixture_db), "--before", "2099-01-01T00:00:00Z", "--execute"])
    assert excinfo.value.code == 2


def test_dry_run_and_execute_are_mutually_exclusive(fixture_db):
    with pytest.raises(SystemExit) as excinfo:
        tool.main(["--db", str(fixture_db), "--before", CUTOFF, "--dry-run", "--execute"])
    assert excinfo.value.code == 2
