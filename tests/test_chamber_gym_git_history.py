"""G1 git-history gym — taskpack, held-out seal, scorer, leak guard, E5 mandate.

Fixture repo pattern: a tiny throwaway git repo with real merged "PRs" whose
landed tests are the ground truth, mirroring how the gym reads dharma_swarm's
own history.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.chamber.gym_git_history import (
    LeakError,
    Taskpack,
    assert_leak_free,
    build_taskpack,
    export_sandbox,
    fixture_solver,
    live_solver_status,
    run_gym,
    score_candidate,
    scorer_hash,
    write_holdout_seal,
)
from dharma_swarm.chamber.traces import read_corpus


def _git(repo: Path, *args: str, inp: str | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=gym@test", "-c",
         "user.name=gym", *args],
        capture_output=True, text=True, input=inp, timeout=60,
    )
    assert proc.returncode == 0, f"git {args}: {proc.stderr}"
    return proc.stdout


@pytest.fixture()
def fixture_repo(tmp_path: Path) -> Path:
    """Repo with 2 merged 'PRs', each landing a source fix + a test file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "mymod.py").write_text(
        "def add(a, b):\n    return a - b  # bug\n\n"
        "def mul(a, b):\n    return a + b  # bug\n", encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "seed with bugs")

    _git(repo, "checkout", "-q", "-b", "fix-add")
    (repo / "mymod.py").write_text(
        "def add(a, b):\n    return a + b\n\n"
        "def mul(a, b):\n    return a + b  # bug\n", encoding="utf-8")
    (repo / "test_add.py").write_text(
        "from mymod import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "fix add")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "PR-1: fix add()", "fix-add")

    _git(repo, "checkout", "-q", "-b", "fix-mul")
    (repo / "mymod.py").write_text(
        "def add(a, b):\n    return a + b\n\n"
        "def mul(a, b):\n    return a * b\n", encoding="utf-8")
    (repo / "test_mul.py").write_text(
        "from mymod import mul\n\ndef test_mul():\n    assert mul(2, 3) == 6\n",
        encoding="utf-8")
    _git(repo, "add", "."); _git(repo, "commit", "-q", "-m", "fix mul")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "PR-2: fix mul()", "fix-mul")
    return repo


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").strip()


def _landed_source_diff(repo: Path, task) -> str:
    """The real fix (source only, tests excluded) — a known-correct candidate."""
    return _git(repo, "diff", task.base_sha, task.merge_sha, "--", "mymod.py")


def test_taskpack_build_pins_and_splits(fixture_repo):
    pack = build_taskpack(fixture_repo, _head(fixture_repo),
                          holdout_fraction=0.5, seed=3)
    assert len(pack.tasks) == 2
    assert all(t.test_files for t in pack.tasks)
    assert pack.taskpack_sha() == build_taskpack(
        fixture_repo, _head(fixture_repo), holdout_fraction=0.5, seed=3
    ).taskpack_sha()
    assert 1 <= len(pack.held_out_ids) < 2 or len(pack.held_out_ids) == 1


def test_holdout_seal_written_and_digested(fixture_repo, tmp_path):
    pack = build_taskpack(fixture_repo, _head(fixture_repo), seed=3)
    seal = write_holdout_seal(pack, tmp_path / "seal.json")
    on_disk = json.loads((tmp_path / "seal.json").read_text())
    assert on_disk == seal and seal["digest"]
    assert seal["taskpack_sha"] == pack.taskpack_sha()


def test_sandbox_has_no_git_and_leak_guard_trips(fixture_repo, tmp_path):
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    sandbox = export_sandbox(fixture_repo, pack.tasks[0].base_sha,
                             tmp_path / "sb")
    assert not (sandbox / ".git").exists()
    assert_leak_free(sandbox)
    (sandbox / ".git").mkdir()  # plant a repo -> kill rule fires
    with pytest.raises(LeakError):
        assert_leak_free(sandbox)


def test_cheating_solver_finds_no_history_in_sandbox(fixture_repo, tmp_path):
    """Adversary check: a solver that greps git history for the landed fix
    gets nothing — the sandbox carries no objects at all."""
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    task = pack.tasks[0]
    sandbox = export_sandbox(fixture_repo, task.base_sha, tmp_path / "sb")
    cheat = subprocess.run(["git", "-C", str(sandbox), "log", "--all"],
                           capture_output=True, text=True)
    assert cheat.returncode != 0  # not a repository: nothing to steal


def test_scorer_passes_landed_fix_and_fails_empty_diff(fixture_repo, tmp_path):
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    task = next(t for t in pack.tasks if "PR-1" in t.prompt)
    good = score_candidate(fixture_repo, task,
                           _landed_source_diff(fixture_repo, task),
                           tmp_path / "good")
    assert good.correct and good.passed >= 1 and not good.errored
    bad = score_candidate(fixture_repo, task, "", tmp_path / "bad")
    assert not bad.correct


def test_scorer_rejects_non_applying_diff(fixture_repo, tmp_path):
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    res = score_candidate(fixture_repo, pack.tasks[0],
                          "--- a/nope.py\n+++ b/nope.py\n@@ -1 +1 @@\n-x\n+y\n",
                          tmp_path / "na")
    assert res.errored and "apply" in res.detail


def test_run_gym_end_to_end_writes_traces_and_receipt(fixture_repo, tmp_path):
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    answers = {
        t.task_id: {"seat_good": _landed_source_diff(fixture_repo, t),
                    "seat_bad": ""}
        for t in pack.tasks
    }
    receipt = run_gym(fixture_repo, pack, fixture_solver(answers),
                      ["seat_good", "seat_bad"], tmp_path / "run", seed=11)
    assert receipt["schema"] == "chamber_gym_run.v1"
    assert receipt["tasks_run"] == 2 and receipt["tasks_correct"] == 2
    assert receipt["taskpack_sha"] == pack.taskpack_sha()
    assert receipt["scorer_hash"] == scorer_hash()
    rows = read_corpus(tmp_path / "run" / receipt["trace_corpus"]["file"])
    assert len(rows) == 2 and receipt["trace_corpus"]["rows"] == 2
    for row in rows:  # per-seat labels feed the E1 decomposition
        by_seat = {a["seat_id"]: a["correct"] for a in row["answers"]}
        assert by_seat == {"seat_good": True, "seat_bad": False}
        assert row["correct"] is True
    assert "train-signal only" in receipt["aggregation_rule"]
    assert receipt["capability_claim"].startswith("NONE")


def test_live_solver_reports_honest_status():
    available, reason = live_solver_status()
    assert available is False and reason  # never silently green in Slice A
