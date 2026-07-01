from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import spine_loop


def test_spine_loop_ingests_latest_report_each_tick(tmp_path: Path) -> None:
    scheduler = tmp_path / "scheduler"
    run = scheduler / "forge_2_1_spine_8h_20260701T000000Z"
    run.mkdir(parents=True)
    (run / "campaign_meta_report.json").write_text('{"schema":"x","arms_tested":[]}', encoding="utf-8")
    calls = []

    def fake_ingester(run_dir, *, store_root, epoch_id):
        calls.append((run_dir, store_root, epoch_id))
        return {
            "ok": True,
            "store": {"n_new": 1 if len(calls) == 1 else 0, "n_duplicate": 0 if len(calls) == 1 else 1},
        }

    state = spine_loop.run_spine_loop(
        run_dir=None,
        scheduler_label="forge_2_1_spine_8h",
        run_root=scheduler,
        loop_root=tmp_path / "loops",
        label="test_loop",
        duration_hours=None,
        max_iterations=3,
        interval_seconds=0.0,
        store_root=tmp_path / "store",
        epoch_id="epoch_test",
        ingester=fake_ingester,
    )

    assert state["stop_reason"] == "max_iterations"
    assert state["iterations"] == 3
    assert state["ingests_ok"] == 3
    assert state["new_signal_rows"] == 1
    assert state["duplicate_signal_rows"] == 2
    assert [call[0] for call in calls] == [run, run, run]
    assert all(call[1] == tmp_path / "store" for call in calls)
    assert all(call[2] == "epoch_test" for call in calls)

    loop_dir = Path(state["loop_dir"])
    rows = [
        json.loads(line)
        for line in (loop_dir / "spine_loop_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in rows] == [
        "spine_loop_tick",
        "spine_loop_tick",
        "spine_loop_tick",
        "spine_loop_stop",
    ]
    assert rows[0]["report_changed"] is True
    assert rows[1]["report_changed"] is False


def test_spine_loop_receipts_missing_report(tmp_path: Path) -> None:
    run = tmp_path / "scheduler" / "forge_2_1_spine_8h_20260701T000000Z"
    run.mkdir(parents=True)

    state = spine_loop.run_spine_loop(
        run_dir=run,
        scheduler_label=None,
        run_root=tmp_path / "scheduler",
        loop_root=tmp_path / "loops",
        label="missing_report",
        duration_hours=None,
        max_iterations=1,
        interval_seconds=0.0,
        store_root=None,
        epoch_id="epoch_test",
    )

    loop_dir = Path(state["loop_dir"])
    rows = [
        json.loads(line)
        for line in (loop_dir / "spine_loop_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["status"] == "no_campaign_meta_report"
