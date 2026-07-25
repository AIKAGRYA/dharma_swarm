from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.cybernetics_codex import _evaluate_loop_closure_replay
from scripts.loop9_11_conductor_replication_closure_run import run_replay


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_loop9_and_loop11_replay_writes_strict_closure_receipts(tmp_path: Path) -> None:
    receipt_dir = tmp_path / "receipts"
    state_dir = tmp_path / "home" / ".dharma"

    result = run_replay(receipt_dir=receipt_dir, state_dir=state_dir)

    loop9_path = Path(result["loop9"]["path"])
    loop11_path = Path(result["loop11"]["path"])
    assert loop9_path.name.endswith("_loop9_conductor_closure.json")
    assert loop11_path.name.endswith("_loop11_replication_monitor_closure.json")
    assert loop9_path.exists()
    assert loop11_path.exists()

    loop9 = _load(loop9_path)
    loop11 = _load(loop11_path)

    assert _evaluate_loop_closure_replay(loop9)["closed"] is True
    assert _evaluate_loop_closure_replay(loop11)["closed"] is True
    assert loop9["loop"] == 9
    assert loop11["loop"] == 11
    assert loop9["provider_truth"]["external_provider_called"] is False
    assert loop11["provider_truth"]["external_provider_called"] is False
    written = loop9_path.read_text(encoding="utf-8")
    assert "$DHARMA_STATE" in written or "$TMPDIR" in written
    assert str(state_dir) not in written


def test_loop9_receipt_proves_conductor_action_and_later_scheduler_read(
    tmp_path: Path,
) -> None:
    result = run_replay(
        receipt_dir=tmp_path / "receipts",
        state_dir=tmp_path / "home" / ".dharma",
    )
    receipt = _load(result["loop9"]["path"])

    assert receipt["transitions_receipted"] == {
        "sense": True,
        "interpret": True,
        "constrain": True,
        "act": True,
        "adapt": True,
    }
    assert receipt["sense_evidence"]["seeded_signal_path"] in receipt["interpret_evidence"]["task"]
    assert receipt["act_evidence"]["witness_entries_after"] > 0
    assert receipt["act_evidence"]["conductor_mark_count"] > 0
    assert receipt["act_evidence"]["memory_entries"] > 0
    assert receipt["later_cycle_read_evidence"]["suppressed_by_last_run"] is True
    assert receipt["later_cycle_read_evidence"]["immediate_second_tick_jobs_fired"] == 0
    assert receipt["adapt_proof"]["before"] != receipt["adapt_proof"]["after"]


def test_loop11_receipt_proves_replication_action_and_later_monitor_read(
    tmp_path: Path,
) -> None:
    result = run_replay(
        receipt_dir=tmp_path / "receipts",
        state_dir=tmp_path / "home" / ".dharma",
    )
    receipt = _load(result["loop11"]["path"])

    assert receipt["transitions_receipted"] == {
        "sense": True,
        "interpret": True,
        "constrain": True,
        "act": True,
        "adapt": True,
    }
    later = receipt["later_cycle_read_evidence"]
    assert later["pending_before"] == 1
    assert later["pending_after"] == 0
    assert later["materialized_statuses"] == 1
    assert later["child_loaded_from_restarted_roster"] is True
    assert later["probation_loaded_for_child"] is True
    assert "M_MATERIALIZED" in receipt["act_evidence"]["witness_events"]
    assert receipt["adapt_proof"]["before"] != receipt["adapt_proof"]["after"]
