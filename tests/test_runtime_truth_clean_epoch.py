from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


def _load_epoch_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "runtime"
        / "mark_runtime_truth_clean_epoch.py"
    )
    spec = importlib.util.spec_from_file_location(
        "mark_runtime_truth_clean_epoch",
        script_path,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mark_runtime_truth_clean_epoch_writes_idempotent_receipt_and_file(
    capsys,
    tmp_path: Path,
) -> None:
    module = _load_epoch_module()
    state_root = tmp_path / "dharma"
    runtime_db = tmp_path / "runtime.db"
    since_created_at = "2026-06-18T12:34:56Z"

    args = [
        "--state-root",
        str(state_root),
        "--db",
        str(runtime_db),
        "--since-created-at",
        since_created_at,
        "--reason",
        "test boundary",
        "--json",
    ]
    assert module.main(args) == 0
    first_output = json.loads(capsys.readouterr().out)
    assert module.main(args) == 0
    second_output = json.loads(capsys.readouterr().out)

    assert second_output["receipt_id"] == first_output["receipt_id"]
    epoch_path = state_root / "state" / "runtime_truth_clean_epoch.json"
    epoch = json.loads(epoch_path.read_text(encoding="utf-8"))
    assert epoch["schema_version"] == "runtime_truth_clean_epoch.v1"
    assert epoch["since_created_at"] == "2026-06-18T12:34:56+00:00"
    assert epoch["receipt_id"] == first_output["receipt_id"]

    with sqlite3.connect(runtime_db) as db:
        rows = db.execute(
            """
            SELECT receipt_id, receipt_type, status, payload_json
            FROM runtime_receipts
            WHERE receipt_id = ?
            """,
            (first_output["receipt_id"],),
        ).fetchall()
    assert len(rows) == 1
    receipt_id, receipt_type, status, payload_json = rows[0]
    payload = json.loads(payload_json)
    assert receipt_id == first_output["receipt_id"]
    assert receipt_type == "runtime_truth_clean_epoch"
    assert status == "active"
    assert payload["since_created_at"] == "2026-06-18T12:34:56+00:00"
    assert "historical dirty receipts are not rewritten" in (
        payload["historical_dirt_policy"]
    )
