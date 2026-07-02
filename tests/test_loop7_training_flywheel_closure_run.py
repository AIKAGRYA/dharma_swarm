from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "loop7_training_flywheel_closure_run.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("loop7_training_flywheel_closure_run", _SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_replay_closes_with_scored_traces_strategy_dataset_and_later_read(tmp_path: Path) -> None:
    module = _load_module()
    report = module.run_replay(
        report_path=tmp_path / "loop7_receipt.json",
        work_dir=tmp_path / "state",
    )

    assert module._closure_satisfied(report) is True
    assert report["closed"] is True
    assert report["loop"] == 7
    assert report["loop_id"] == "training_flywheel"
    assert report["real_data"] is True
    assert all(report["transitions_receipted"].values())
    assert report["tick_errors"] == []

    assert report["sense_evidence"]["trajectory_jsonl_lines"] == 5
    assert report["sense_evidence"]["loaded_successful_trajectories"] == 5
    assert report["interpret_evidence"]["min_composite"] >= 0.7
    assert len(report["constrain_evidence"]["reinforcement_eligible"]) == 5
    assert len(report["constrain_evidence"]["dataset_eligible"]) == 5
    assert report["act_evidence"]["pattern_lines_after"] > report["act_evidence"]["pattern_lines_before"]
    assert report["act_evidence"]["dataset_lines_after"] > report["act_evidence"]["dataset_lines_before"]
    assert report["adapt_proof"]["fed_forward"] is True
    assert report["adapt_proof"]["before"] != report["adapt_proof"]["after"]
    assert report["later_cycle_read_evidence"]["fresh_instance"] is True
    assert report["later_cycle_read_evidence"]["fresh_reinforcer_loaded_patterns"] > 0
    assert report["later_cycle_read_evidence"]["prompt_changed"] is True
    assert report["later_cycle_read_evidence"]["injected_fragment"] is True
    assert report["provider_truth"]["external_provider_invoked"] is False
    assert report["provider_truth"]["provider_truth_claimed"] is False


def test_main_writes_receipt(tmp_path: Path) -> None:
    module = _load_module()
    report_path = tmp_path / "2026-07-01_loop7_training_flywheel_closure.json"
    work_dir = tmp_path / "state"

    rc = module.main([
        "--report",
        str(report_path),
        "--work-dir",
        str(work_dir),
    ])

    assert rc == 0
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["loop"] == 7
    assert data["closed"] is True
    assert module._closure_satisfied(data) is True
    text = report_path.read_text(encoding="utf-8")
    assert "$TMPDIR" in text or "<absolute-path>" in text
    assert str(work_dir) not in text
    assert (work_dir / module.WORK_DIR_SENTINEL).read_text(encoding="utf-8") == module.WORK_DIR_SENTINEL_TEXT


def test_reset_work_dir_refuses_non_owned_existing_directory(tmp_path: Path) -> None:
    module = _load_module()
    work_dir = tmp_path / "important"
    work_dir.mkdir()
    keep = work_dir / "keep.txt"
    keep.write_text("do not delete\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to reset non-owned work dir"):
        module._reset_work_dir(work_dir)

    assert keep.read_text(encoding="utf-8") == "do not delete\n"


def test_reset_work_dir_refuses_non_owned_empty_directory(tmp_path: Path) -> None:
    module = _load_module()
    work_dir = tmp_path / "empty"
    work_dir.mkdir()

    with pytest.raises(RuntimeError, match="refusing to reset non-owned work dir"):
        module._reset_work_dir(work_dir)

    assert work_dir.exists()


def test_reset_work_dir_refuses_bad_sentinel_contents(tmp_path: Path) -> None:
    module = _load_module()
    work_dir = tmp_path / "important"
    work_dir.mkdir()
    keep = work_dir / "keep.txt"
    keep.write_text("do not delete\n", encoding="utf-8")
    (work_dir / module.WORK_DIR_SENTINEL).write_text("spoofed\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to reset non-owned work dir"):
        module._reset_work_dir(work_dir)

    assert keep.read_text(encoding="utf-8") == "do not delete\n"

def test_replay_does_not_close_when_reinforcement_threshold_not_met(tmp_path: Path) -> None:
    module = _load_module()
    report = module.run_replay(
        report_path=tmp_path / "loop7_receipt.json",
        work_dir=tmp_path / "state",
        trace_count=4,
    )

    assert report["sense_evidence"]["loaded_successful_trajectories"] == 4
    assert report["transitions_receipted"]["act"] is False
    assert report["real_data"] is False
    assert report["closed"] is False
    assert module._closure_satisfied(report) is False


def test_closure_satisfied_rejects_tick_errors(tmp_path: Path) -> None:
    module = _load_module()
    report = module.run_replay(
        report_path=tmp_path / "loop7_receipt.json",
        work_dir=tmp_path / "state",
    )
    report["tick_errors"] = ["boom"]

    assert module._closure_satisfied(report) is False
