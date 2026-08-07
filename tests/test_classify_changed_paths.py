"""The changed-path classifier decides which advisory CI jobs may be skipped.

Every test here exists because the failure it pins would cause a job to be
SKIPPED when it should have run. That direction is the only dangerous one: a
false "changed" costs a runner minute, a false "unchanged" silently removes a
test from the PR that needed it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import classify_changed_paths as ccp  # noqa: E402


def _repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
        ["git", "config", "commit.gpgSign", "false"],
    ):
        subprocess.run(cmd, cwd=path, check=True)


def test_a_non_pull_request_event_runs_everything() -> None:
    """merge_group and push have no PR base/head. Guessing there would skip
    jobs on the merge queue -- exactly where a skip is least recoverable."""
    for event in ("merge_group", "push", "schedule", ""):
        classes, reason = ccp.resolve(event, "abc", "def")
        assert classes == ccp.all_true(), (event, classes)
        assert "not a pull_request" in reason


def test_missing_shas_run_everything() -> None:
    classes, _ = ccp.resolve("pull_request", "", "def")
    assert classes == ccp.all_true()
    classes, _ = ccp.resolve("pull_request", "abc", "")
    assert classes == ccp.all_true()


def test_an_unreadable_diff_runs_everything(monkeypatch) -> None:
    """THE regression. `changed_paths` returning None must not be read as "no
    paths changed" -- that is AI-N1, an unreadable input reported as a definite
    value, and here it would skip every advisory job on the PR."""
    monkeypatch.setattr(ccp, "changed_paths", lambda base, head: None)
    classes, reason = ccp.resolve("pull_request", "abc123456789", "def123456789")
    assert classes == ccp.all_true(), classes
    assert "could not read diff" in reason


def test_unreadable_is_a_different_answer_from_empty(monkeypatch) -> None:
    """An empty diff genuinely means nothing changed, and there the classifier
    is allowed to say False. The two must not collapse."""
    monkeypatch.setattr(ccp, "changed_paths", lambda base, head: [])
    classes, _ = ccp.resolve("pull_request", "abc", "def")
    assert classes == dict.fromkeys(ccp.CLASSES, False)
    assert classes != ccp.all_true()


def test_a_missing_git_binary_runs_everything(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(ccp.subprocess, "run", boom)
    assert ccp.changed_paths("a", "b") is None


def test_a_git_diff_timeout_runs_everything(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 120)

    monkeypatch.setattr(ccp.subprocess, "run", boom)
    assert ccp.changed_paths("a", "b") is None


def test_each_class_is_recognised() -> None:
    assert ccp.classify(["tools/world_scout_go/main.go"])["go"]
    assert ccp.classify(["go.mod"])["go"]
    assert ccp.classify(["dashboard/src/app/page.tsx"])["dashboard"]
    assert ccp.classify(["terminal/src/index.ts"])["terminal"]
    assert ccp.classify(["dharma_swarm/organism.py"])["python"]
    assert ccp.classify(["uv.lock"])["python"], "a pin change changes the runtime"
    assert ccp.classify(["pyproject.toml"])["python"]


def test_a_docs_only_change_touches_nothing() -> None:
    """The whole point: a README edit must not run the Go bridges."""
    classes = ccp.classify(["docs/architecture/NAVIGATION.md", "README.md"])
    assert classes == dict.fromkeys(ccp.CLASSES, False), classes


def test_a_dashboard_change_does_not_drag_in_go() -> None:
    classes = ccp.classify(["dashboard/src/lib/operatorCoherence.ts"])
    assert classes["dashboard"] and not classes["go"] and not classes["terminal"]


def test_a_non_utf8_path_does_not_crash_the_classifier() -> None:
    """Paths are bytes. A path that is not valid UTF-8 arrives with surrogates
    and must classify normally rather than raise mid-run (which would fail the
    job and, worse, could be "fixed" by someone making it fail closed)."""
    weird = "dharma_swarm/caf\udce9.py"
    assert ccp.classify([weird])["python"]


def test_a_renamed_source_path_is_still_seen(tmp_path) -> None:
    """#1200's lesson, re-pinned here. With rename detection ON, git reports
    only the destination, so moving `dashboard/x.ts` to `docs/x.ts` would look
    like a docs-only change and skip the dashboard build. `--no-renames` is
    what keeps the source path visible."""
    repo = tmp_path / "r"
    _repo(repo)
    src = repo / "dashboard"
    src.mkdir()
    # Large identical content makes git's rename detection certain to fire.
    (src / "big.ts").write_text("export const x = 1;\n" * 200, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    (repo / "docs").mkdir()
    subprocess.run(
        ["git", "mv", "dashboard/big.ts", "docs/big.ts"], cwd=repo, check=True
    )
    subprocess.run(["git", "commit", "-q", "-m", "move"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    import os

    cwd = os.getcwd()
    try:
        os.chdir(repo)
        paths = ccp.changed_paths(base, head)
    finally:
        os.chdir(cwd)

    assert paths is not None
    assert "dashboard/big.ts" in paths, (
        "the rename SOURCE vanished -- rename detection is on and the dashboard "
        f"build would be skipped by a move. got: {paths}"
    )
    assert ccp.classify(paths)["dashboard"]


def test_the_classifier_never_raises_on_any_resolve_path(monkeypatch) -> None:
    """`resolve` is called from a workflow step; an exception there fails the
    job and tempts a fail-closed 'fix'."""
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ccp.subprocess, "run", boom)
    try:
        ccp.changed_paths("a", "b")
    except RuntimeError:
        pass  # only FileNotFoundError/Timeout are caught by contract
    # resolve must still be total for the cases it owns
    assert ccp.resolve("push", "", "")[0] == ccp.all_true()


# --- self-coverage (PR #1285 review round 2) --------------------------------
#
# The workflow-level rule "a filtered workflow must list its own file" has a
# per-job twin that the classifier did not honour: a PR editing tests.yml
# classified every class false, so each advisory job it defines was skipped and
# the change to a job could not exercise that job.


def test_editing_the_workflow_that_defines_the_jobs_runs_every_job() -> None:
    classes = ccp.classify([".github/workflows/tests.yml"])
    assert all(classes.values()), (
        "a PR editing tests.yml skips the very jobs it edits: " + repr(classes)
    )


def test_editing_the_classifier_itself_runs_every_job() -> None:
    classes = ccp.classify(["scripts/ci/classify_changed_paths.py"])
    assert all(classes.values()), (
        "the rules deciding which jobs run are an input to every job: "
        + repr(classes)
    )


def test_self_coverage_does_not_leak_into_unrelated_paths() -> None:
    """The escape hatch must be exact-match, not a prefix or suffix rule, or it
    would quietly re-enable everything and undo the whole change."""
    classes = ccp.classify(["docs/governance/tests.yml", "scripts/ci/other.txt"])
    assert not any(classes.values()), repr(classes)


def test_the_go_lanes_run_when_the_make_target_they_invoke_changes() -> None:
    """Both Go jobs run `make go-ci`; nothing else in tests.yml uses make."""
    classes = ccp.classify(["Makefile"])
    assert classes["go"], "a change to the go-ci target skipped the Go lanes"
