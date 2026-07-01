from __future__ import annotations

import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

from dharma_swarm.forge_v1 import swebench_real
from dharma_swarm.forge_v1.forge_v2 import grade_queue


def _instance(instance_id: str) -> dict:
    return {"instance_id": instance_id, "repo": "example/repo"}


def _rows(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM grade_jobs ORDER BY id")]


def test_grade_queue_claims_unique_instance_batch_atomically(tmp_path: Path) -> None:
    db = tmp_path / "grades.db"
    grade_queue.enqueue_grade(_instance("task-a"), "patch-a1", db_path=db, job_id="a1", priority=10, now=1.0)
    grade_queue.enqueue_grade(_instance("task-a"), "patch-a2", db_path=db, job_id="a2", priority=9, now=2.0)
    grade_queue.enqueue_grade(_instance("task-b"), "patch-b", db_path=db, job_id="b1", priority=1, now=3.0)

    claimed = grade_queue.claim_batch(db_path=db, batch_size=3, run_id="run-1", now=10.0)

    assert [job["id"] for job in claimed] == ["a1", "b1"]
    assert {job["instance_id"] for job in claimed} == {"task-a", "task-b"}
    assert grade_queue.queue_counts(db_path=db) == {"in_flight": 2, "queued": 1}


def test_grade_queue_reclaims_stale_inflight_jobs(tmp_path: Path) -> None:
    db = tmp_path / "grades.db"
    grade_queue.enqueue_grade(_instance("task-a"), "patch-a", db_path=db, job_id="a1", now=1.0)
    first = grade_queue.claim_batch(db_path=db, batch_size=1, run_id="old-run", now=2.0)
    assert [job["id"] for job in first] == ["a1"]

    reclaimed = grade_queue.claim_batch(
        db_path=db,
        batch_size=1,
        run_id="new-run",
        stale_after_s=10.0,
        now=100.0,
    )

    assert [job["id"] for job in reclaimed] == ["a1"]
    row = _rows(db)[0]
    assert row["run_id"] == "new-run"
    assert row["attempts"] == 2


def test_grade_queue_drain_once_batches_with_max_workers(tmp_path: Path) -> None:
    db = tmp_path / "grades.db"
    grade_queue.enqueue_grade(_instance("task-a"), "patch-a", db_path=db, job_id="a1")
    grade_queue.enqueue_grade(_instance("task-b"), "patch-b", db_path=db, job_id="b1")
    calls = []

    def fake_verifier(predictions, **kwargs):
        calls.append({"predictions": predictions, **kwargs})
        return {"task-a": True, "task-b": False}

    summary = grade_queue.drain_once(
        db_path=db,
        batch_size=6,
        max_workers=6,
        timeout=123,
        namespace="swebench",
        verifier=fake_verifier,
        run_id="batch-1",
    )

    assert summary == {"run_id": "batch-1", "claimed": 2, "completed": 2, "errors": 0}
    assert calls[0]["max_workers"] == 6
    assert calls[0]["timeout"] == 123
    assert calls[0]["namespace"] == "swebench"
    assert [item[0]["instance_id"] for item in calls[0]["predictions"]] == ["task-a", "task-b"]
    rows = _rows(db)
    assert {row["id"]: row["status"] for row in rows} == {"a1": "done", "b1": "done"}
    assert {row["id"]: row["resolved"] for row in rows} == {"a1": 1, "b1": 0}


def test_grade_queue_receipts_batch_verifier_errors(tmp_path: Path) -> None:
    db = tmp_path / "grades.db"
    grade_queue.enqueue_grade(_instance("task-a"), "patch-a", db_path=db, job_id="a1")

    def failing_verifier(*_args, **_kwargs):
        raise RuntimeError("docker unavailable")

    summary = grade_queue.drain_once(db_path=db, verifier=failing_verifier, run_id="batch-error")

    assert summary["errors"] == 1
    row = _rows(db)[0]
    assert row["status"] == "error"
    assert "docker unavailable" in row["error"]


def test_swebench_batch_adapter_passes_max_workers_and_reads_reports(monkeypatch, tmp_path: Path) -> None:
    calls = []
    run_eval = types.ModuleType("swebench.harness.run_evaluation")
    constants = types.ModuleType("swebench.harness.constants")
    swebench_pkg = types.ModuleType("swebench")
    harness_pkg = types.ModuleType("swebench.harness")
    constants.RUN_EVALUATION_LOG_DIR = Path("logs/run_evaluation")

    def fake_main(**kwargs):
        calls.append(kwargs)
        predictions = json.loads(Path(kwargs["predictions_path"]).read_text())
        base = constants.RUN_EVALUATION_LOG_DIR / kwargs["run_id"] / "forge_batch"
        for prediction in predictions:
            instance_id = prediction["instance_id"]
            if not prediction["model_patch"]:
                continue
            report_dir = base / instance_id
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "report.json").write_text(
                json.dumps({instance_id: {"resolved": prediction["model_patch"] == "PASS"}})
            )

    run_eval.main = fake_main
    monkeypatch.setitem(sys.modules, "swebench", swebench_pkg)
    monkeypatch.setitem(sys.modules, "swebench.harness", harness_pkg)
    monkeypatch.setitem(sys.modules, "swebench.harness.run_evaluation", run_eval)
    monkeypatch.setitem(sys.modules, "swebench.harness.constants", constants)
    monkeypatch.setattr(swebench_real, "_ensure_docker_host", lambda: None)
    monkeypatch.setattr(swebench_real, "SCRATCH_ROOT", tmp_path / "scratch")

    verdicts = swebench_real.verify_predictions(
        [
            (_instance("task-pass"), "PASS"),
            (_instance("task-fail"), "FAIL"),
            (_instance("task-empty"), ""),
        ],
        run_id="batch-test",
        max_workers=4,
        timeout=77,
        keep_logs=True,
    )

    assert calls[0]["max_workers"] == 4
    assert calls[0]["timeout"] == 77
    assert calls[0]["instance_ids"] == ["task-pass", "task-fail", "task-empty"]
    assert verdicts == {"task-pass": True, "task-fail": False, "task-empty": False}


def test_swebench_batch_adapter_rejects_duplicate_instances() -> None:
    with pytest.raises(ValueError, match="unique instance_id"):
        swebench_real.verify_predictions(
            [
                (_instance("task-a"), "patch-1"),
                (_instance("task-a"), "patch-2"),
            ]
        )
