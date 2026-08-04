"""G1 git-history gym — taskpack, held-out seal, scorer, leak guard, E5 mandate.

Fixture repo pattern: a tiny throwaway git repo with real merged "PRs" whose
landed tests are the ground truth, mirroring how the gym reads dharma_swarm's
own history.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.chamber.gym_git_history import (
    LeakError,
    Taskpack,
    _is_test_file,
    _parse_pytest_summary,
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


def _install_python3_path_poison(root: Path) -> tuple[Path, Path]:
    """Install a leading PATH python3 that records use and fails closed."""
    poison_bin = root / "poison-bin"
    poison_bin.mkdir()
    marker = root / "python3-invoked"
    shim = poison_bin / "python3"
    shim.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' poison > {shlex.quote(str(marker))}\n"
        "exit 97\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return poison_bin, marker


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


def test_export_sandbox_clears_stale_files_on_retry(fixture_repo, tmp_path):
    # Greptile PR #830: a retry on a deterministic path must not inherit
    # stale files that were not present at base_sha.
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    dest = tmp_path / "sandbox"
    export_sandbox(fixture_repo, pack.tasks[0].base_sha, dest)
    stale = dest / "STALE_INTERRUPTED_RUN.py"
    stale.write_text("raise SystemExit('contamination')\n", encoding="utf-8")
    export_sandbox(fixture_repo, pack.tasks[0].base_sha, dest)  # retry
    assert not stale.exists()  # clean tree of exactly base_sha
    assert (dest / "mymod.py").exists()


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


def test_scorer_uses_current_interpreter_not_path_python3(
    fixture_repo,
    tmp_path,
    monkeypatch,
):
    poison_bin, marker = _install_python3_path_poison(tmp_path)
    monkeypatch.setenv(
        "PATH",
        str(poison_bin) + os.pathsep + os.environ.get("PATH", ""),
    )
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    task = next(t for t in pack.tasks if "PR-1" in t.prompt)

    result = score_candidate(
        fixture_repo,
        task,
        _landed_source_diff(fixture_repo, task),
        tmp_path / "path-poison",
    )

    assert result.correct and result.passed >= 1 and not result.errored, result.detail
    assert not marker.exists()


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


# --- review-round regression tests ---

def test_both_pytest_filename_conventions_are_ground_truth():
    # R1-6: pytest's default python_files is test_*.py AND *_test.py.
    assert _is_test_file("test_add.py")
    assert _is_test_file("foo_test.py")
    assert _is_test_file("pkg/bar_test.py")
    assert not _is_test_file("helper.py")
    assert not _is_test_file("testing.py")


@pytest.mark.parametrize("summary,expected", [
    ("1 passed in 0.1s", (1, 0, False)),
    ("1 failed, 2 passed in 0.3s", (2, 1, False)),
    ("3 passed, 1 xfailed in 0.2s", (3, 0, False)),  # xfailed != failed
    ("2 errors in 0.1s", (0, 0, True)),
    ("1 error in 0.1s", (0, 0, True)),
])
def test_parse_pytest_summary_reads_only_the_tally(summary, expected):
    assert _parse_pytest_summary(f"collecting...\n{summary}") == expected


def test_parse_summary_ignores_poisoned_test_output():
    # R1-4: a test body printing "5 passed" must not poison the count.
    stdout = 'print output: "5 passed"\n1 failed, 1 passed in 0.2s'
    assert _parse_pytest_summary(stdout) == (1, 1, False)


def test_candidate_conftest_injection_is_blocked_end_to_end(fixture_repo, tmp_path):
    # R2-1 (the critical exploit): a diff adding a root conftest that
    # neutralizes every test must NOT score an unfixed bug as correct.
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    task = pack.tasks[0]
    attack = ("diff --git a/conftest.py b/conftest.py\n"
              "new file mode 100644\nindex 0000000..1111111\n"
              "--- /dev/null\n+++ b/conftest.py\n@@ -0,0 +1,2 @@\n"
              "+def pytest_pyfunc_call(pyfuncitem):\n+    return True\n")
    res = score_candidate(fixture_repo, task, attack, tmp_path / "atk")
    assert not res.correct
    assert "policy" in res.detail


def test_renamed_or_deleted_landed_test_does_not_crash_taskpack(fixture_repo):
    # R1-7: a merge that renames a landed test away must not enter the pack
    # with a path absent at merge (which would crash the scorer's git show).
    def g(*a, inp=None):
        return _git(fixture_repo, *a, inp=inp)
    g("checkout", "-q", "-b", "rename-test")
    # rename an existing landed test file
    g("mv", "test_add.py", "test_add_renamed.py")
    g("commit", "-q", "-am", "rename test")
    g("checkout", "-q", "main")
    g("merge", "-q", "--no-ff", "-m", "PR-3: rename", "rename-test")
    pack = build_taskpack(fixture_repo, _head(fixture_repo), holdout_fraction=0)
    for t in pack.tasks:  # every listed test file exists at its merge
        for rel in t.test_files:
            r = subprocess.run(["git", "-C", str(fixture_repo), "cat-file",
                                "-e", f"{t.merge_sha}:{rel}"], capture_output=True)
            assert r.returncode == 0
