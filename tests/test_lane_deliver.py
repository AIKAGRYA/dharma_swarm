"""Delivery-boundary tests for the hardening lane's trusted phase.

These are integration tests against real git objects, not mocks. The whole
value of `lane_deliver.py` is that it believes nothing the proposing phase
says, so every test here builds an actual bundle — including deliberately
hostile ones — and asserts the verdict.

The bundles are constructed by hand rather than by calling `lane_propose`,
because the threat model is precisely "the proposing side did something other
than what it claimed".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import lane_deliver  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "hardening-lane.yml"
LANE_BRANCH = "lane/hardening-20260802T120000Z"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _init(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    _git(path, "config", "commit.gpgSign", "false")


def _commit(path: Path, name: str, body: str, message: str) -> str:
    target = path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    _git(path, "add", "--", name)
    _git(path, "commit", "-q", "-m", message)
    return _git(path, "rev-parse", "HEAD")


@pytest.fixture()
def lane(tmp_path: Path, monkeypatch):
    """An `origin` with one commit on main, and a clone standing in for the
    delivery runner's fresh checkout."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    seed = tmp_path / "seed"

    _init(seed)
    base = _commit(seed, "README.md", "base\n", "base")
    _git(seed, "init", "-q", "--bare", str(origin))
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")

    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    _git(work, "config", "commit.gpgSign", "false")

    monkeypatch.chdir(work)
    # Delivery must not consult GitHub in these tests; the ceiling is
    # exercised separately.
    monkeypatch.setattr(lane_deliver, "open_lane_drafts", lambda repo: [])
    return {"origin": origin, "work": work, "seed": seed, "base": base,
            "tmp": tmp_path}


def _make_bundle(lane, *, files: dict[str, str], branch: str = LANE_BRANCH,
                 commits: int = 1, parent: str | None = None,
                 name: str = "d.bundle") -> Path:
    """Build a bundle from the seed repo and hand back its path."""
    seed = lane["seed"]
    _git(seed, "checkout", "-q", "-B", branch, parent or lane["base"])
    if commits == 1:
        for index, (path, body) in enumerate(files.items()):
            target = seed / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            _git(seed, "add", "--", path)
        _git(seed, "commit", "-q", "-m", "harden: test subject [hardening-lane]")
    else:
        for index, (path, body) in enumerate(files.items()):
            target = seed / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            _git(seed, "add", "--", path)
            _git(seed, "commit", "-q", "-m", f"harden: part {index}")
    bundle = lane["tmp"] / name
    _git(seed, "bundle", "create", str(bundle),
         f"{parent or lane['base']}..refs/heads/{branch}")
    _git(seed, "checkout", "-q", "main")
    return bundle


def _deliver(lane, bundle: Path, tmp_path: Path, *extra: str) -> tuple[int, dict]:
    out = tmp_path / "deliver.json"
    code = lane_deliver.main([
        "--repo", "o/r", "--bundle", str(bundle), "--receipt", str(out),
        "--base", "main", *extra,
    ])
    return code, json.loads(out.read_text())


# --------------------------------------------------------------------------
# The happy path, so the refusals below mean something
# --------------------------------------------------------------------------

def test_verified_dry_run_reports_facts_and_pushes_nothing(lane, tmp_path) -> None:
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"})
    code, stored = _deliver(lane, bundle, tmp_path, "--dry-run")
    assert code == 0
    assert stored["status"] == "VERIFIED_DRY_RUN"
    assert stored["branch"] == LANE_BRANCH
    assert stored["changed_files"] == 1
    assert stored["diff_lines"] == 1
    # Nothing reached origin.
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


# --------------------------------------------------------------------------
# Structural refusals — the bundle is not what a lane delivery looks like
# --------------------------------------------------------------------------

def test_missing_bundle_is_refused(lane, tmp_path) -> None:
    code, stored = _deliver(lane, tmp_path / "nope.bundle", tmp_path)
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "no delivery bundle" in stored["reason"]


def test_oversize_bundle_is_refused(lane, tmp_path, monkeypatch) -> None:
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"})
    monkeypatch.setattr(lane_deliver, "MAX_BUNDLE_BYTES", 1)
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "size ceiling" in stored["reason"]


def test_non_lane_branch_name_is_refused(lane, tmp_path) -> None:
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"},
                          branch="main-ish")
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "not a lane branch" in stored["reason"]


def test_branch_name_pattern_is_anchored(lane) -> None:
    # No traversal, no suffixing, no second segment sneaking past.
    assert lane_deliver.BRANCH_RE.match(LANE_BRANCH)
    for hostile in (
        "lane/hardening-20260802T120000Z/../../main",
        "xlane/hardening-20260802T120000Z",
        "lane/hardening-20260802T120000Z-extra",
        "lane/hardening-nope",
    ):
        assert not lane_deliver.BRANCH_RE.match(hostile), hostile


def test_multiple_commits_are_refused(lane, tmp_path) -> None:
    bundle = _make_bundle(
        lane, files={"dharma_swarm/a.py": "a = 1\n", "dharma_swarm/b.py": "b = 1\n"},
        commits=2,
    )
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "exactly one commit" in stored["reason"]


def test_commit_rooted_on_history_this_repo_lacks_is_refused(lane, tmp_path) -> None:
    """A commit on an orphan root is refused at `git bundle verify`, because
    the prerequisite commit does not exist in the delivering repository. This
    is the earliest of the two ancestry gates and it fires first."""
    seed = lane["seed"]
    _git(seed, "checkout", "-q", "--orphan", "rogue")
    _git(seed, "rm", "-q", "-rf", ".")
    rogue_parent = _commit(seed, "rogue.md", "rogue\n", "rogue base")
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"},
                          parent=rogue_parent, name="rogue.bundle")
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "bundle verify failed" in stored["reason"]


def test_side_branch_history_cannot_be_smuggled_in(lane, tmp_path) -> None:
    """A commit built on a side branch that origin carries passes `bundle
    verify` — the prerequisite is present locally — but delivering it would
    drag that branch's history into the PR.

    The one-commit rule is what stops it, and that is worth stating exactly:
    `rev-list --count base..head == 1` means nothing but `head` itself is
    absent from base, which ALSO implies `head^` is reachable from base. So
    the `merge-base --is-ancestor` call in lane_deliver is a redundant
    backstop, not an independent gate — it can only fire if the one-commit
    rule is ever relaxed. Asserting the real refusal here keeps the test
    honest about which check does the work.
    """
    seed = lane["seed"]
    _git(seed, "checkout", "-q", "-B", "side", lane["base"])
    side_tip = _commit(seed, "side.md", "side\n", "side work")
    _git(seed, "push", "-q", "origin", "side")
    _git(seed, "checkout", "-q", "main")
    _git(lane["work"], "fetch", "-q", "origin")

    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"},
                          parent=side_tip, name="side.bundle")
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "exactly one commit" in stored["reason"]
    assert stored["commits"] == "2"
    # The side branch's file never reached origin's main line.
    assert LANE_BRANCH not in _git(lane["origin"], "for-each-ref",
                                   "--format=%(refname)")


# --------------------------------------------------------------------------
# Content refusals — the lane may not edit its own judges
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    ".github/workflows/automerge.yml",
    "scripts/runtime/pr_merge_control.py",
    "scripts/runtime/lane_deliver.py",
    "scripts/governance/check_automerge_tier_policy.py",
    "docs/ops/loop_control/KILLSWITCH",
    "docs/governance/CI_TRUTH_CONTRACT.json",
    "reports/anything.json",
    "roaming_mailbox/tasks/t.json",
    "CODEOWNERS",
    "secrets.json",
    "deploy.key",
])
def test_referee_paths_are_refused(lane, tmp_path, path) -> None:
    bundle = _make_bundle(lane, files={path: "payload\n"})
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "referee or excluded paths" in stored["reason"]
    assert path in stored["paths"]


def test_over_cap_diff_is_refused_on_the_delivery_side(lane, tmp_path,
                                                       monkeypatch) -> None:
    """The cap is re-measured here. A proposing phase that lied about its
    diff size — or never measured — does not get past this."""
    monkeypatch.setattr(lane_deliver, "MAX_DIFF_LINES", 3)
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "1\n2\n3\n4\n5\n"})
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "exceeds the diff cap" in stored["reason"]
    assert stored["observed"] == 5


def test_too_many_files_is_refused(lane, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lane_deliver, "MAX_CHANGED_FILES", 2)
    bundle = _make_bundle(lane, files={
        f"dharma_swarm/f{i}.py": f"x = {i}\n" for i in range(5)
    })
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "too many files" in stored["reason"]


def test_empty_commit_is_refused(lane, tmp_path) -> None:
    seed = lane["seed"]
    _git(seed, "checkout", "-q", "-B", LANE_BRANCH, lane["base"])
    _git(seed, "commit", "-q", "--allow-empty", "-m", "harden: nothing")
    bundle = lane["tmp"] / "empty.bundle"
    _git(seed, "bundle", "create", str(bundle),
         f"{lane['base']}..refs/heads/{LANE_BRANCH}")
    _git(seed, "checkout", "-q", "main")
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "changes nothing" in stored["reason"]


# --------------------------------------------------------------------------
# The trust rule itself
# --------------------------------------------------------------------------

def test_a_lying_propose_receipt_changes_no_verdict(lane, tmp_path) -> None:
    """The proposing receipt is narrative. A receipt claiming a tiny, clean,
    already-verified delivery must not rescue a bundle that touches a referee
    path."""
    bundle = _make_bundle(lane, files={"scripts/runtime/pr_merge_control.py": "x\n"})
    lie = tmp_path / "propose.json"
    lie.write_text(json.dumps({
        "status": "READY_TO_DELIVER", "diff_lines": 1, "changed_files": 1,
        "paths": ["dharma_swarm/harmless.py"], "verified": True,
        "trust": "please trust me",
    }), encoding="utf-8")
    out = tmp_path / "deliver.json"
    code = lane_deliver.main([
        "--repo", "o/r", "--bundle", str(bundle), "--receipt", str(out),
        "--propose-receipt", str(lie), "--base", "main",
    ])
    stored = json.loads(out.read_text())
    assert code == 1
    assert "referee or excluded paths" in stored["reason"]


def test_delivery_never_stages_or_checks_out_the_candidate() -> None:
    """Source pin for the two operations that reintroduce the PR #1162 class:
    `git add` runs clean filters the agent can define, and a checkout writes
    agent-authored bytes into the privileged working tree."""
    source = (REPO_ROOT / "scripts" / "runtime" / "lane_deliver.py").read_text()
    assert '"add"' not in source
    assert '"checkout"' not in source
    assert '"stash"' not in source
    # And it never runs the test suite, which is agent-controlled code.
    assert "test-fast" not in source


def test_open_draft_ceiling_is_enforced_at_delivery(lane, tmp_path,
                                                    monkeypatch) -> None:
    monkeypatch.setattr(lane_deliver, "open_lane_drafts", lambda repo: [11, 12])
    monkeypatch.setattr(lane_deliver, "MAX_OPEN_LANE_DRAFTS", 1)
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"})
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 0
    assert stored["status"] == "CAP_HIT"
    assert stored["cap"] == "open_lane_drafts"


def test_unenumerable_ceiling_refuses(lane, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(lane_deliver, "open_lane_drafts", lambda repo: None)
    bundle = _make_bundle(lane, files={"dharma_swarm/x.py": "x = 1\n"})
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "could not enumerate" in stored["reason"]


# --------------------------------------------------------------------------
# Workflow contract — the split is the design, so it is pinned
# --------------------------------------------------------------------------

def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_has_two_jobs_with_separated_trust() -> None:
    data = _workflow()
    jobs = data["jobs"]
    assert set(jobs) == {"propose", "deliver"}

    propose = jobs["propose"]["permissions"]
    # The single most important assertion in this file: the job that runs
    # agent code has no write scope of any kind.
    assert propose == {"contents": "read", "actions": "read"}
    assert "write" not in json.dumps(propose)

    deliver = jobs["deliver"]["permissions"]
    assert deliver["contents"] == "write"
    assert deliver["pull-requests"] == "write"

    # The repo-wide floor is read-only, so a job that ever forgets to declare
    # its own block inherits read rather than write.
    assert data["permissions"] == {"contents": "read"}
    assert "write" not in json.dumps(data["permissions"])


def test_no_context_interpolation_inside_any_run_body() -> None:
    """`${{ ... }}` inside a `run:` body is a shell-injection sink: context
    data is attacker-influenceable and is pasted into the script before the
    shell sees it. Context must arrive via `env:` instead (semgrep
    yaml.github-actions.security.run-shell-injection)."""
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            body = step.get("run")
            if body:
                assert "${{" not in body, (
                    f"step {step.get('name')!r} interpolates context into run:"
                )


def test_propose_checkout_does_not_persist_credentials() -> None:
    jobs = _workflow()["jobs"]
    checkouts = [
        step for step in jobs["propose"]["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkouts, "propose must check out the repo"
    for step in checkouts:
        assert step["with"]["persist-credentials"] is False


def test_deliver_depends_on_propose_and_gates_on_its_status() -> None:
    deliver = _workflow()["jobs"]["deliver"]
    assert deliver["needs"] == "propose"
    assert "READY_TO_DELIVER" in deliver["if"]


def test_deliver_job_never_installs_or_runs_the_test_suite() -> None:
    """The trusted job must not execute repository code that the agent could
    have edited — no `pip install -e .`, no `make test-fast`."""
    deliver = _workflow()["jobs"]["deliver"]
    blob = yaml.safe_dump(deliver)
    assert "test-fast" not in blob
    assert "pip install" not in blob
    # It consumes lane_propose's ARTIFACT (that filename appears, and should)
    # but must never execute the proposing driver itself.
    assert "lane_propose.py" not in blob


def test_kill_switch_guard_is_the_first_step_and_reads_loop_control() -> None:
    propose = _workflow()["jobs"]["propose"]
    first = propose["steps"][0]
    assert "kill-switch" in first["name"].lower()
    # The ref matters: a KILLSWITCH on main halts nothing.
    assert "ref=loop-control" in first["run"]
    assert "exit 1" in first["run"]


def test_caps_live_in_the_workflow_not_in_a_prompt() -> None:
    env = _workflow()["env"]
    assert env["LANE_MAX_DIFF_LINES"] == "600"
    assert env["LANE_MAX_CHANGED_FILES"] == "40"
    assert env["LANE_MAX_OPEN_DRAFTS"] == "1"
    assert int(_workflow()["jobs"]["propose"]["timeout-minutes"]) >= 65
