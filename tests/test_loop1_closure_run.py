from __future__ import annotations

import json
import sqlite3

from scripts.loop1_closure_run import _read_served_provider_truth


def test_loop1_closure_run_counts_served_provider_truth(tmp_path):
    state_dir = tmp_path / "loop1"
    db = state_dir / "state" / "runtime.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        create table delegation_runs (
            run_id text primary key,
            status text,
            metadata_json text
        );
        create table runtime_receipts (
            receipt_id text primary key,
            run_id text,
            payload_json text
        );
        """
    )
    conn.execute(
        "insert into delegation_runs values (?, ?, ?)",
        (
            "run_1",
            "completed",
            json.dumps(
                {
                    "actual_served_provider": "ollama",
                    "actual_served_model": "qwen3-coder",
                }
            ),
        ),
    )
    conn.execute(
        "insert into runtime_receipts values (?, ?, ?)",
        (
            "rr_1",
            "run_1",
            json.dumps({"served_provider": "ollama", "served_model": "qwen3-coder"}),
        ),
    )
    conn.commit()
    conn.close()

    truth = _read_served_provider_truth(state_dir)

    assert truth["exists"] is True
    assert truth["completed_runs_with_truth"] == 1
    assert truth["runtime_receipts_with_truth"] == 1
    assert truth["sample"]["served_provider"] == "ollama"
