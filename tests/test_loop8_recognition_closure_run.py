from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from dharma_swarm.cybernetics_codex import _evaluate_loop_closure_replay


_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "loop8_recognition_closure_run.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("loop8_recognition_closure_run", _SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _transitions() -> dict[str, bool]:
    return {
        "sense": True,
        "interpret": True,
        "constrain": True,
        "act": True,
        "adapt": True,
    }


def _write_loop1(history_dir: Path) -> None:
    payload = {
        "tasks_requested": 2,
        "tasks_completed": 2,
        "tasks_failed": 0,
        "dispatch_dropoffs": 0,
        "tick_errors": [],
        "ticks": 2,
        "adapt_fired": True,
        "stigmergy_marks_before": 0,
        "stigmergy_marks_after": 2,
        "evidence_receipts": {
            "task-1": "ok",
            "task-2": "ok",
        },
        "served_provider_truth": {
            "completed_runs_with_truth": 2,
            "sample": [
                {
                    "provider": "bounded_replay",
                    "model": "local_fixture",
                }
            ],
        },
    }
    (history_dir / "2026-07-01_loop1_fixture_spine_dispatch.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_generic(history_dir: Path, loop: int, loop_id: str) -> None:
    payload = {
        "loop": loop,
        "loop_id": loop_id,
        "cycles": 1,
        "real_data": True,
        "transitions_receipted": _transitions(),
        "adapt_proof": {
            "field": f"fixture loop {loop} fed-forward state",
            "before": {
                "value": loop,
            },
            "after": {
                "value": loop + 100,
            },
            "fed_forward": True,
        },
        "tick_errors": [],
        "cycle_detail": [
            {
                "cycle": 1,
                "fixture": True,
            }
        ],
        "observed_at": "2026-07-01T00:00:00Z",
    }
    (history_dir / f"2026-07-01_loop{loop}_{loop_id}_closure.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_history(history_dir: Path, module, *, omit_loop: int | None = None) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    if omit_loop != 1:
        _write_loop1(history_dir)
    for loop in module.REQUIRED_HISTORY_LOOPS:
        if loop in (1, omit_loop):
            continue
        _write_generic(history_dir, loop, module.LOOP_IDS[loop])


def test_replay_closes_loop8_with_seed_and_later_context_read(tmp_path: Path) -> None:
    module = _load_module()
    history_dir = tmp_path / "history"
    _write_history(history_dir, module)

    report_path = tmp_path / "2026-07-01_loop8_recognition_closure.json"
    report = module.run_replay(
        report_path=report_path,
        history_dir=history_dir,
        work_dir=tmp_path / "state",
    )

    assert report["closed"] is True
    assert module._closure_satisfied(report) is True
    assert _evaluate_loop_closure_replay(report)["closed"] is True
    assert report["loop"] == 8
    assert report["loop_id"] == "recognition_eigenform"
    assert report["real_data"] is True
    assert report["tick_errors"] == []
    assert all(report["transitions_receipted"].values())

    assert report["sense_evidence"]["history_digest"]
    assert len(report["sense_evidence"]["receipts_read"]) == len(module.REQUIRED_HISTORY_LOOPS)
    assert report["interpret_evidence"]["self_model"]["closed_loop_count"] == len(
        module.REQUIRED_HISTORY_LOOPS
    )
    assert report["interpret_evidence"]["cascade_records"]
    assert report["constrain_evidence"]["admitted_to_recognition_engine"] is True
    assert report["act_evidence"]["seed_contains_marker"] is True
    assert report["act_evidence"]["seed_contains_required_loop_domains"] is True
    assert report["act_evidence"]["recognition_seed"]["exists"] is True
    assert report["adapt_proof"]["fed_forward"] is True
    assert report["adapt_proof"]["before"] != report["adapt_proof"]["after"]
    assert report["adapt_evidence"]["context_changed"] is True
    assert report["later_cycle_read_evidence"]["recognition_seed_section_present"] is True
    assert report["later_cycle_read_evidence"]["marker_present_in_later_context"] is True
    assert module.MARKER in report["later_cycle_read_evidence"]["later_context_snippet"]
    assert report["provider_truth"]["external_provider_invoked"] is False
    assert report["provider_truth"]["provider_truth_claimed"] is False
    assert report_path.exists()


def test_reset_work_dir_requires_exact_sentinel(tmp_path: Path) -> None:
    module = _load_module()
    work_dir = tmp_path / "state"
    work_dir.mkdir()
    (work_dir / module.WORK_DIR_SENTINEL).write_text("spoof\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to reset non-owned work dir"):
        module._reset_work_dir(work_dir)

    assert work_dir.exists()
    assert (work_dir / module.WORK_DIR_SENTINEL).read_text(encoding="utf-8") == "spoof\n"


def test_loop1_history_requires_fed_forward_adapt() -> None:
    module = _load_module()
    data = {
        "tasks_requested": 1,
        "tasks_completed": 1,
        "tasks_failed": 0,
        "dispatch_dropoffs": 0,
        "tick_errors": [],
        "ticks": 1,
        "adapt_fired": False,
        "stigmergy_marks_before": 1,
        "stigmergy_marks_after": 1,
        "evidence_receipts": {"task-1": "ok"},
        "served_provider_truth": {"completed_runs_with_truth": 1},
    }

    evaluated = module._evaluate_loop1(data)

    assert evaluated["closed"] is False
    assert evaluated["adapt_proof"]["fed_forward"] is False
    assert not any(evaluated["transitions_receipted"].values())


def test_main_writes_requested_report(tmp_path: Path) -> None:
    module = _load_module()
    history_dir = tmp_path / "history"
    _write_history(history_dir, module)
    report_path = tmp_path / "2026-07-01_loop8_recognition_closure.json"

    rc = module.main(
        [
            "--report",
            str(report_path),
            "--history-dir",
            str(history_dir),
            "--work-dir",
            str(tmp_path / "state"),
        ]
    )

    assert rc == 0
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["closed"] is True
    assert _evaluate_loop_closure_replay(data)["closed"] is True
    assert data["observed_at"] == "2026-07-01T00:00:00Z"


def test_missing_required_history_does_not_close(tmp_path: Path) -> None:
    module = _load_module()
    history_dir = tmp_path / "history"
    _write_history(history_dir, module, omit_loop=7)

    report = module.run_replay(
        report_path=tmp_path / "2026-07-01_loop8_recognition_closure.json",
        history_dir=history_dir,
        work_dir=tmp_path / "state",
    )

    assert report["closed"] is False
    assert report["real_data"] is False
    assert report["transitions_receipted"]["sense"] is False
    assert report["transitions_receipted"]["interpret"] is False
    assert report["transitions_receipted"]["constrain"] is False
    assert report["transitions_receipted"]["act"] is False
    assert report["transitions_receipted"]["adapt"] is False
    assert report["tick_errors"] == []
    assert _evaluate_loop_closure_replay(report)["closed"] is False
    missing = [
        row
        for row in report["sense_evidence"]["receipts_read"]
        if row["loop"] == 7
    ]
    assert missing == [
        {
            "loop": 7,
            "loop_id": "training_flywheel",
            "path": None,
            "sha256": None,
            "closed": False,
            "cycles": None,
        }
    ]


def test_closure_satisfied_rejects_context_without_later_seed_read(tmp_path: Path) -> None:
    module = _load_module()
    history_dir = tmp_path / "history"
    _write_history(history_dir, module)

    report = module.run_replay(
        report_path=tmp_path / "2026-07-01_loop8_recognition_closure.json",
        history_dir=history_dir,
        work_dir=tmp_path / "state",
    )
    report["adapt_proof"]["fed_forward"] = False

    assert module._closure_satisfied(report) is False
