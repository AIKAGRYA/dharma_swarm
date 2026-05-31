from __future__ import annotations

import json

import pytest

from dharma_swarm.dharma_eval import (
    DharmaEvalManifest,
    DharmaEvalTask,
    build_scoreboard,
    load_manifest,
    score_output,
    write_manifest,
)


def test_manifest_hash_is_stable(tmp_path):
    manifest = DharmaEvalManifest(
        suite_id="mini",
        tasks=[
            DharmaEvalTask(
                task_id="t1",
                split="train",
                domain="repo_repair",
                expected={"ok": True},
            )
        ],
    )

    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    loaded = load_manifest(path)

    assert loaded.manifest_hash.startswith("sha256:")
    assert loaded.manifest_hash == load_manifest(path).manifest_hash


def test_scoreboard_compares_common_tasks_only():
    manifest_hash = "sha256:manifest"
    task = DharmaEvalTask(
        task_id="holdout-1",
        split="holdout",
        domain="governance",
        expected={"status": "ok"},
    )
    baseline = score_output(
        task,
        {"status": "fail"},
        candidate_id="incumbent",
        suite_id="suite",
        manifest_hash=manifest_hash,
    )
    candidate = score_output(
        task,
        {"status": "ok"},
        candidate_id="child",
        suite_id="suite",
        manifest_hash=manifest_hash,
    )

    board = build_scoreboard(
        suite_id="suite",
        manifest_hash=manifest_hash,
        baseline_id="incumbent",
        candidate_id="child",
        baseline_scores=[baseline],
        candidate_scores=[candidate],
        split="holdout",
        min_delta=0.5,
    )

    assert board.candidate_wins is True
    assert board.delta == pytest.approx(1.0)
    assert board.candidate_passed == 1


def test_load_manifest_rejects_empty_task_id(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "suite_id": "bad",
                "tasks": [
                    {
                        "task_id": "",
                        "split": "train",
                        "domain": "repo_repair",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_manifest(path)


def test_scoreboard_rejects_mixed_manifest_hashes():
    """Forge anti-contamination: a board must refuse scores graded under a different manifest.

    A candidate must never 'win' because it was scored under an easier/altered manifest
    than the baseline. build_scoreboard must reject any contributing score whose
    manifest_hash disagrees with the board's declared manifest_hash.
    """
    task = DharmaEvalTask(
        task_id="holdout-1",
        split="holdout",
        domain="governance",
        expected={"status": "ok"},
    )
    baseline = score_output(
        task,
        {"status": "ok"},
        candidate_id="incumbent",
        suite_id="suite",
        manifest_hash="sha256:manifest-A",
    )
    candidate = score_output(
        task,
        {"status": "ok"},
        candidate_id="child",
        suite_id="suite",
        manifest_hash="sha256:manifest-B",  # contaminated: graded under a different manifest
    )

    with pytest.raises(ValueError, match="manifest"):
        build_scoreboard(
            suite_id="suite",
            manifest_hash="sha256:manifest-A",
            baseline_id="incumbent",
            candidate_id="child",
            baseline_scores=[baseline],
            candidate_scores=[candidate],
            split="holdout",
        )


def test_scoreboard_rejects_mixed_suite_ids():
    """Forge anti-contamination: a board must refuse scores graded under a different suite.

    Suite contamination is the same class of attack as manifest contamination: a candidate
    must never be compared against a baseline drawn from a different benchmark suite.
    """
    task = DharmaEvalTask(
        task_id="holdout-1",
        split="holdout",
        domain="governance",
        expected={"status": "ok"},
    )
    baseline = score_output(
        task,
        {"status": "ok"},
        candidate_id="incumbent",
        suite_id="suite-A",
        manifest_hash="sha256:m",
    )
    candidate = score_output(
        task,
        {"status": "ok"},
        candidate_id="child",
        suite_id="suite-B",  # contaminated: graded under a different suite
        manifest_hash="sha256:m",
    )

    with pytest.raises(ValueError, match="suite"):
        build_scoreboard(
            suite_id="suite-A",
            manifest_hash="sha256:m",
            baseline_id="incumbent",
            candidate_id="child",
            baseline_scores=[baseline],
            candidate_scores=[candidate],
            split="holdout",
        )
