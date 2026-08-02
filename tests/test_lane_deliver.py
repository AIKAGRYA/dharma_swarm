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

import ast
import inspect
import json
import os
import re
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


def test_non_ascii_referee_path_cannot_evade_the_denylist(lane, tmp_path) -> None:
    """Regression for a verified bypass (Greptile, post-merge on #1197).

    `git diff --name-only` C-quotes paths with non-ASCII bytes, so
    `.github/workflows/é.yml` arrived as `".github/workflows/\\303\\251.yml"`.
    The leading quote meant it no longer matched the `.github/workflows/`
    deny prefix and `denied_paths()` returned []. Reproduced against real git
    before the fix; `-z` makes the output verbatim.
    """
    bundle = _make_bundle(lane, files={".github/workflows/é.yml": "evil\n"})
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "referee or excluded paths" in stored["reason"]
    assert any("é.yml" in p for p in stored["paths"]), stored["paths"]
    assert not any(p.startswith('"') for p in stored["paths"])


def test_renaming_a_referee_file_away_cannot_evade_the_denylist(
        lane, tmp_path) -> None:
    """Regression for a second verified bypass (Codex, post-merge on #1197).

    With rename detection on, `--name-only` reports ONLY the destination, so
    renaming `scripts/runtime/pr_merge_control.py` to a benign path showed
    just the benign name while effectively deleting the referee gate.
    Reproduced against real git; `--no-renames` surfaces both sides.
    """
    seed = lane["seed"]
    referee = "scripts/runtime/pr_merge_control.py"
    body = "\n".join(f"line {i}" for i in range(200)) + "\n"
    base_with_referee = _commit(seed, referee, body, "seed referee")
    _git(seed, "push", "-q", "origin", "main")
    _git(lane["work"], "fetch", "-q", "origin")
    _git(lane["work"], "reset", "-q", "--hard", "origin/main")

    _git(seed, "checkout", "-q", "-B", LANE_BRANCH, base_with_referee)
    (seed / "dharma_swarm").mkdir(parents=True, exist_ok=True)
    _git(seed, "mv", referee, "dharma_swarm/harmless.py")
    _git(seed, "commit", "-q", "-m", "harden: tidy [hardening-lane]")
    bundle = lane["tmp"] / "rename.bundle"
    _git(seed, "bundle", "create", str(bundle),
         f"{base_with_referee}..refs/heads/{LANE_BRANCH}")
    _git(seed, "checkout", "-q", "main")

    out = tmp_path / "deliver.json"
    code = lane_deliver.main(["--repo", "o/r", "--bundle", str(bundle),
                              "--receipt", str(out), "--base", "main"])
    stored = json.loads(out.read_text())
    assert code == 1
    assert "referee or excluded paths" in stored["reason"]
    assert referee in stored["paths"]


def test_large_binary_blob_is_refused_despite_a_zero_line_count(
        lane, tmp_path, monkeypatch) -> None:
    """`git diff --numstat` prints `-` for binaries, so they score zero
    against the line cap; the compressed bundle ceiling does not bound them
    either. The byte ceiling is what actually stops this."""
    monkeypatch.setattr(lane_deliver, "MAX_CHANGED_BLOB_BYTES", 1024)
    payload = ("\x00" * 40_000)
    bundle = _make_bundle(lane, files={"dharma_swarm/blob.bin": payload})
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert "byte ceiling" in stored["reason"]
    assert stored["bytes"] > 1024


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


def test_non_utf8_filename_is_refused_not_crashed(lane, tmp_path) -> None:
    """Regression for a verified crash (Codex on #1200).

    Git filenames are bytes, not UTF-8. A legal name like `bad-\\xff.txt` made
    `text=True` raise UnicodeDecodeError inside `_run()`, which escaped before
    `refuse()` could write a receipt — an untrusted candidate crashing the
    trusted delivery job instead of being deterministically rejected.
    `errors="surrogateescape"` round-trips the bytes so the denylist sees the
    real path and the job returns a verdict.
    """
    seed = lane["seed"]
    _git(seed, "checkout", "-q", "-B", LANE_BRANCH, lane["base"])
    hostile = os.fsdecode(b".github/workflows/bad-\xff.yml")
    target = Path(os.fsencode(str(seed)).decode("utf-8", "surrogateescape")) / hostile
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("evil\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "harden: odd bytes [hardening-lane]")
    bundle = lane["tmp"] / "utf8.bundle"
    _git(seed, "bundle", "create", str(bundle),
         f"{lane['base']}..refs/heads/{LANE_BRANCH}")
    _git(seed, "checkout", "-q", "main")

    # The point is that this returns a verdict rather than raising.
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert stored["status"] == "REFUSED"
    # And the referee denylist still recognises it despite the odd bytes.
    assert "referee or excluded paths" in stored["reason"]


def test_orphan_rollback_deletes_under_an_atomic_lease() -> None:
    """Regression for a verified race (Greptile, #1200).

    The first version read the branch SHA with `ls-remote` and then deleted
    unconditionally — a TOCTOU. Greptile pushed a concurrent writer's commit
    between the two operations and watched the rollback delete it.

    `--force-with-lease=<ref>:<sha>` with a delete refspec binds expectation
    and deletion into one atomic operation. Verified against git 2.43: a
    stale expectation is rejected with "(delete) ... stale info" and the
    branch survives; a matching one deletes.
    """
    body = inspect.getsource(lane_deliver.rollback_branch)
    assert "--force-with-lease=refs/heads/{branch}:{head_sha}" in body
    assert "stale info" in body

    # Scan CODE only. The docstring below describes the TOCTOU it forbids, so
    # a naive source scan matches the very prose documenting the prohibition.
    code_only = "\n".join(
        line for line in
        body.replace(lane_deliver.rollback_branch.__doc__ or "", "").splitlines()
        if not line.strip().startswith("#"))
    # The non-atomic shape must not come back HERE. `ls-remote` is legitimate
    # elsewhere in the module (probing whether a timed-out push landed); what
    # must never return is a read-then-delete inside the rollback itself.
    assert "ls-remote" not in code_only
    assert '"--delete"' not in code_only

    # And the rollback is the module's ONLY ref deletion, so no second path
    # can grow one without a lease.
    source = (REPO_ROOT / "scripts" / "runtime" / "lane_deliver.py").read_text()
    deletions = [line for line in source.splitlines()
                 if 'f":refs/heads/' in line]
    assert len(deletions) == 1, deletions


def test_run_converts_a_timeout_into_a_verdict_not_an_exception() -> None:
    """A hung command must be a failed command, not a crashed delivery."""
    result = lane_deliver._run(
        [sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)
    assert result.returncode == lane_deliver.EXIT_TIMEOUT
    assert "timed out" in result.stderr


def _intercept(monkeypatch, handler):
    """Route lane_deliver's subprocess calls through `handler` first.

    Patched at the subprocess layer, not at `_run`/`_git`: those call each
    other, so patching them recurses.
    """
    real_run = subprocess.run

    def dispatch(cmd, *args, **kwargs):
        verdict = handler(cmd, kwargs)
        if verdict is not None:
            return verdict
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lane_deliver.subprocess, "run", dispatch)


def _is(cmd, *tokens) -> bool:
    return all(token in cmd for token in tokens)


def test_a_clean_pr_create_failure_still_rolls_back(
        lane, tmp_path, monkeypatch) -> None:
    """The unambiguous case: GitHub positively reports no PR for the branch,
    so the push really is an orphan the draft ceiling cannot see."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            return subprocess.CompletedProcess(cmd, 1, "", "validation failed")
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert stored["status"] == "PR_CREATE_FAILED"
    assert stored["branch_rollback"] == "deleted under lease"
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_a_plain_nonzero_create_with_an_existing_pr_keeps_the_branch(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for the general case (Devin on #1200, second pass).

    The first fix gated the existence probe on EXIT_TIMEOUT, which closed the
    reported instance and left the class open. The plainest case needs no race
    at all: a retry where `gh pr create` refuses because a PR for this branch
    ALREADY EXISTS exits non-zero and is not 124, so the branch was deleted —
    closing the very PR whose existence caused the error.
    """
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            return subprocess.CompletedProcess(
                cmd, 1, "", "a pull request for branch ... already exists")
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 0, '[{"number":7}]', "")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PR_CREATE_AMBIGUOUS"
    assert "deleting it would close that PR" in stored["branch_rollback"]
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH in refs


def test_a_missing_gh_binary_still_rolls_the_orphan_back(
        lane, tmp_path, monkeypatch) -> None:
    """The one exit that needs no probe: no process ran, so no mutation can
    have happened. Probing with the same missing binary would only ever answer
    "unknown" and strand the orphan forever."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if cmd and cmd[0] == lane_deliver.GH_BIN:
            raise FileNotFoundError(2, "No such file or directory", cmd[0])
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PR_CREATE_FAILED"
    assert stored["branch_rollback"] == "deleted under lease"
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_a_timed_out_pr_create_never_deletes_a_branch_whose_pr_may_exist(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a defect THIS PR introduced (Devin on #1200).

    Before the TimeoutExpired arm, a hung `gh pr create` crashed main() and
    nothing was deleted. Converting it to a non-zero exit made the rollback
    reachable — but `gh` runs the GraphQL mutation and *then* prints the URL,
    so a timeout in between leaves the PR open on GitHub. Opening a PR does
    not move the branch ref, so the lease still matches and the delete
    succeeds; GitHub closes a PR whose head branch is deleted. The lane would
    have destroyed the work it had just published and called it a failure.
    """
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 300))
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 0, '[{"number":7}]', "")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PR_CREATE_AMBIGUOUS"
    assert "deleting it would close that PR" in stored["branch_rollback"]
    # The branch that possibly-created PR points at is still there.
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH in refs


def test_a_timed_out_pr_create_with_no_pr_does_roll_back(
        lane, tmp_path, monkeypatch) -> None:
    """Ambiguity resolved in the other direction: GitHub says no PR exists,
    so the branch really is an orphan and the rollback proceeds."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 300))
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PR_CREATE_FAILED"
    assert stored["branch_rollback"] == "deleted under lease"
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_an_unenumerable_pr_list_keeps_the_branch(
        lane, tmp_path, monkeypatch) -> None:
    """An orphan branch is recoverable; a closed PR is not. When the lane
    cannot prove no PR exists, it must not delete."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 300))
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 1, "", "gh unavailable")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PR_CREATE_AMBIGUOUS"
    assert "could not be proven safe" in stored["branch_rollback"]
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH in refs


def test_a_timed_out_push_that_landed_is_rolled_back(
        lane, tmp_path, monkeypatch) -> None:
    """A timed-out push is ambiguous too: the ref may have landed before the
    client gave up. Reporting PUSH_FAILED and walking away strands exactly the
    orphan the rollback exists to remove."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})
    real_run = subprocess.run

    def handler(cmd, kw):
        # Let the real push land, then report a timeout to the caller.
        if "push" in cmd and not any("--force-with-lease" in a for a in cmd):
            real_run(cmd, **kw)
            return subprocess.CompletedProcess(cmd, lane_deliver.EXIT_TIMEOUT,
                                               "", "timed out")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PUSH_FAILED"
    assert stored["branch_rollback"] == "deleted under lease"
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_relocating_a_large_file_is_measured_not_waved_through(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a verified accounting hole (Devin on #1200).

    `changed_paths()` gained `--no-renames` so a rename shows both sides to
    the denylist. `numstat_lines()` was left on git's default rename
    detection, which reports a pure relocation as ONE `0\\t0\\told => new`
    record. Measured on git 2.43 against an 800-line file: 0 lines with
    detection on, 1600 with it off. So the two gates disagreed about the same
    commit — two files, zero lines — and thousands of relocated lines sailed
    under MAX_DIFF_LINES with only the 4 MiB blob ceiling above them.
    """
    seed = lane["seed"]
    body = "\n".join(f"line_{i} = {i}" for i in range(800)) + "\n"
    _git(seed, "checkout", "-q", "-B", "seed-big", lane["base"])
    (seed / "dharma_swarm").mkdir(parents=True, exist_ok=True)
    (seed / "dharma_swarm" / "big.py").write_text(body, encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "seed the file")
    seeded = _git(seed, "rev-parse", "HEAD")
    _git(seed, "push", "-q", "origin", "seed-big:refs/heads/main")

    # One commit that does nothing but relocate it.
    _git(seed, "checkout", "-q", "-B", LANE_BRANCH, seeded)
    _git(seed, "mv", "dharma_swarm/big.py", "dharma_swarm/moved.py")
    _git(seed, "commit", "-q", "-m", "harden: relocate [hardening-lane]")
    bundle = lane["tmp"] / "rename.bundle"
    _git(seed, "bundle", "create", str(bundle),
         f"{seeded}..refs/heads/{LANE_BRANCH}")
    _git(seed, "checkout", "-q", "main")
    _git(lane["work"], "fetch", "-q", "origin")

    code, stored = _deliver(lane, bundle, tmp_path)
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "diff cap" in stored["reason"], stored["reason"]
    # And the count is the real one, not the zero rename detection reports.
    assert stored["observed"] >= 1600, stored["observed"]


def test_a_pure_rename_does_not_consume_the_blob_budget(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a false refusal (Greptile on #1200).

    `changed_paths()` runs `--no-renames`, so a relocation arrives as
    delete(old) + add(new). The new blob is byte-identical to one already in
    the base tree, so charging it billed the candidate for content it never
    shipped: measured at 4096 bytes for a pure rename of a 4096-byte file.

    Comparing base and candidate blobs per path — the fix as prescribed —
    does not close it, because the destination is a new path with no base
    blob and still charges 4096. Membership in the base tree's blob-OID set
    answers 0.
    """
    seed = lane["seed"]
    _git(seed, "checkout", "-q", "-B", "seed-blob", lane["base"])
    (seed / "dharma_swarm").mkdir(parents=True, exist_ok=True)
    (seed / "dharma_swarm" / "asset.bin").write_bytes(b"A" * 4096)
    _git(seed, "add", "-A")
    _git(seed, "commit", "-q", "-m", "seed the asset")
    seeded = _git(seed, "rev-parse", "HEAD")
    _git(seed, "push", "-q", "origin", "seed-blob:refs/heads/main")

    _git(seed, "checkout", "-q", "-B", LANE_BRANCH, seeded)
    _git(seed, "mv", "dharma_swarm/asset.bin", "dharma_swarm/moved.bin")
    _git(seed, "commit", "-q", "-m", "harden: relocate [hardening-lane]")
    bundle = lane["tmp"] / "blob.bundle"
    _git(seed, "bundle", "create", str(bundle),
         f"{seeded}..refs/heads/{LANE_BRANCH}")
    _git(seed, "checkout", "-q", "main")
    _git(lane["work"], "fetch", "-q", "origin")
    # Fetch the candidate into THIS repo before measuring it. Without this,
    # `ls-tree` failed and the old fail-open `entries()` returned {}, so the
    # assertion below passed at 0 for the wrong reason entirely — the
    # fail-open Devin found (#1200) was also hiding a vacuous test.
    _git(lane["work"], "fetch", "-q", str(bundle), f"refs/heads/{LANE_BRANCH}")
    head = _git(lane["work"], "rev-parse", "FETCH_HEAD")

    # The blob budget must see zero NEW content...
    assert lane_deliver.changed_blob_bytes(seeded, head) == 0

    # ...so a ceiling far below the file's size does not refuse it.
    monkeypatch.setattr(lane_deliver, "MAX_CHANGED_BLOB_BYTES", 100)
    code, stored = _deliver(lane, bundle, tmp_path, "--dry-run")
    assert code == 0, stored
    assert stored["status"] == "VERIFIED_DRY_RUN"


def test_one_new_blob_at_many_paths_is_charged_once(
        lane, tmp_path, monkeypatch) -> None:
    """The unique-OID half of the accounting, which the docstring claimed and
    nothing pinned (Greptile's follow-up on #1200).

    Delivery never checks the candidate out — `git fetch` of the bundle
    unpacks OBJECTS — so the cost of the same blob at three paths is one
    blob, and charging it three times would measure something that never
    happens. `MAX_CHANGED_FILES` bounds the path-count axis separately.
    """
    body = "A" * 2048
    bundle = _make_bundle(lane, files={
        "dharma_swarm/one.py": body,
        "dharma_swarm/two.py": body,
        "dharma_swarm/three.py": body,
    })
    _git(lane["work"], "fetch", "-q", "origin")
    _git(lane["work"], "fetch", "-q", str(bundle), f"refs/heads/{LANE_BRANCH}")
    head = _git(lane["work"], "rev-parse", "FETCH_HEAD")

    # Three paths, one object: charged once, not three times.
    assert lane_deliver.changed_blob_bytes(lane["base"], head) == 2048

    # And a ceiling above one copy but below three still admits it.
    monkeypatch.setattr(lane_deliver, "MAX_CHANGED_BLOB_BYTES", 3000)
    code, stored = _deliver(lane, bundle, tmp_path, "--dry-run")
    assert code == 0, stored
    assert stored["status"] == "VERIFIED_DRY_RUN"


def test_new_content_still_counts_against_the_blob_budget(
        lane, tmp_path, monkeypatch) -> None:
    """The other side of the same measurement: content the base does NOT
    have is charged in full, which is what the ceiling exists for."""
    bundle = _make_bundle(lane, files={"dharma_swarm/fat.py": "A" * 4096})
    monkeypatch.setattr(lane_deliver, "MAX_CHANGED_BLOB_BYTES", 100)
    code, stored = _deliver(lane, bundle, tmp_path, "--dry-run")
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "blob" in stored["reason"].lower(), stored["reason"]


def test_a_long_task_body_still_yields_a_recoverable_consumption_claim(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a verified starvation loop (Devin on #1200).

    The id used to be recoverable only from the truncated `Target:` blob.
    `receipt()` writes with sort_keys=True, so the target round-trips as
    body, kind, summary, task_id — free-form body FIRST — and `[:400]` cut
    the id off. Measured: a body over ~300 characters dropped it entirely, so
    `attempted_task_ids()` never saw the task and `select_target()` re-picked
    the same oldest one on every scheduled run.

    This round-trips the real chain: propose receipt -> delivery PR body ->
    the reader's regex. The pre-existing test used a short hand-written body
    and never reached the truncation.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))
    import lane_propose

    target = {"kind": "mailbox", "task_id": "T-2026-08-02-alpha",
              "summary": "harden the thing",
              "body": "Please harden the following surface. " + ("x" * 600)}

    # Exactly how propose writes it, and how delivery reads it back.
    receipt_path = tmp_path / "propose.json"
    lane_propose.receipt({"status": "READY_TO_DELIVER", "target": target},
                         receipt_path)
    read_back = lane_deliver.load_propose_receipt(receipt_path)["target"]
    assert list(read_back) == ["body", "kind", "summary", "task_id"], \
        "key order assumption changed; the truncation risk may have moved"

    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})
    captured: dict[str, str] = {}

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            captured["body"] = cmd[cmd.index("--body") + 1]
            return subprocess.CompletedProcess(cmd, 0, "https://pr/1", "")
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path,
                            "--propose-receipt", str(receipt_path))
    assert code == 0, stored
    assert stored["status"] == "DRAFT_PR_OPENED"

    # The truncated summary really does lose it...
    assert '"task_id"' not in json.dumps(read_back)[:400]
    # ...and the dedicated claim line carries it anyway.
    recovered = re.findall(r'"task_id"\s*:\s*"((?:[^"\\]|\\.)*)"',
                           captured["body"])
    assert "T-2026-08-02-alpha" in recovered, captured["body"][:400]


def test_a_plain_push_failure_that_actually_landed_is_rolled_back(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for the push-side twin of the create-side bug (Greptile on
    #1200).

    A connection reset after the remote accepts the ref exits non-zero and is
    not 124, so the probe gated on EXIT_TIMEOUT never ran and the receipt
    said "nothing to roll back" over a branch that exists. An orphan
    `lane/hardening-*` is invisible to the open-draft ceiling, which counts
    PRs, so every retry adds another.
    """
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})
    real_run = subprocess.run

    def handler(cmd, kw):
        # Let the real push land, then report a plain (non-timeout) failure.
        if "push" in cmd and not any("--force-with-lease" in a for a in cmd):
            real_run(cmd, **kw)
            return subprocess.CompletedProcess(
                cmd, 1, "", "fatal: the remote end hung up unexpectedly")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PUSH_FAILED"
    assert stored["branch_rollback"] == "deleted under lease"
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_an_unanswerable_probe_still_attempts_the_leased_rollback(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a stranded orphan (Greptile on #1200, executed harness).

    When the push failed AND the `ls-remote` probe also failed, `landed`
    stayed empty and the receipt said "nothing to roll back" over a branch
    that exists — invisible to the open-draft ceiling, accumulating on every
    retry.

    The lease, not the probe, is what makes the delete safe. Measured against
    git 2.43 in all three remote states: ref absent -> rejected (stale info),
    ref at our SHA -> deleted, ref at another SHA -> rejected. So attempting
    is never worse than declining.
    """
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})
    real_run = subprocess.run

    def handler(cmd, kw):
        # The push lands, then reports failure.
        if "push" in cmd and not any("--force-with-lease" in a for a in cmd):
            real_run(cmd, **kw)
            return subprocess.CompletedProcess(cmd, 1, "", "connection reset")
        # ...and the reconciliation probe cannot answer.
        if "ls-remote" in cmd:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: unreachable")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PUSH_FAILED"
    assert "probe unanswerable" in stored["branch_rollback"]
    assert "deleted under lease" in stored["branch_rollback"]
    # The orphan is actually gone.
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_an_unanswerable_probe_cannot_delete_another_writers_branch(
        lane, tmp_path, monkeypatch) -> None:
    """The lease still protects a concurrent writer even when we attempt the
    rollback blind — which is what makes attempting safe."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})
    # Build the concurrent writer's commit BEFORE patching, so its setup does
    # not re-enter the handler below (the patch is on subprocess.run itself,
    # which this file's own _git helper also uses).
    _git(lane["seed"], "checkout", "-q", "-B", "intruder", lane["base"])
    (lane["seed"] / "other.txt").write_text("x\n", encoding="utf-8")
    _git(lane["seed"], "add", "-A")
    _git(lane["seed"], "commit", "-q", "-m", "intruder")
    _git(lane["seed"], "checkout", "-q", "main")
    real_run = subprocess.run

    def handler(cmd, kw):
        if "push" in cmd and not any("--force-with-lease" in a for a in cmd):
            real_run(cmd, **kw)
            # The writer moves the branch after our push lands, via the
            # UNPATCHED runner so this does not recurse.
            real_run(["git", "-C", str(lane["seed"]), "push", "-q", "--force",
                      "origin", f"intruder:refs/heads/{LANE_BRANCH}"],
                     capture_output=True, check=True)
            return subprocess.CompletedProcess(cmd, 1, "", "connection reset")
        if "ls-remote" in cmd:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: unreachable")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert "lease refused the delete" in stored["branch_rollback"]
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH in refs, "the concurrent writer's branch must survive"


def test_a_push_that_never_landed_has_nothing_to_roll_back(
        lane, tmp_path, monkeypatch) -> None:
    """The other side: a push that genuinely failed leaves no ref, so the
    probe answers honestly rather than inventing a rollback."""
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if "push" in cmd and not any("--force-with-lease" in a for a in cmd):
            return subprocess.CompletedProcess(
                cmd, 1, "", "fatal: protected branch hook declined")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path)

    assert code == 1
    assert stored["status"] == "PUSH_FAILED"
    assert stored["branch_rollback"].startswith("nothing to roll back")
    refs = _git(lane["origin"], "for-each-ref", "--format=%(refname)")
    assert LANE_BRANCH not in refs


def test_a_malformed_target_does_not_crash_after_the_push(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a crash this PR introduced (Devin on #1200).

    `target` comes from the untrusted receipt and is never type-validated —
    `proposed.get("target", {})` does not protect, because the default applies
    only when the key is ABSENT, not when it is present and null. `.get()` on
    None raised AttributeError after the push and before `gh pr create`, so it
    escaped main(): no receipt, no PR, no rollback, stranded branch.
    """
    receipt_path = tmp_path / "propose.json"
    receipt_path.write_text('{"status": "READY_TO_DELIVER", "target": null}',
                            encoding="utf-8")
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if _is(cmd, "pr", "create"):
            return subprocess.CompletedProcess(cmd, 0, "https://pr/1", "")
        if _is(cmd, "pr", "list"):
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return None

    _intercept(monkeypatch, handler)
    # A verdict, not an exception.
    code, stored = _deliver(lane, bundle, tmp_path,
                            "--propose-receipt", str(receipt_path))
    assert code == 0, stored
    assert stored["status"] == "DRAFT_PR_OPENED"

    for hostile in ('"not-a-dict"', '[1, 2, 3]', '123'):
        receipt_path.write_text(
            '{"status": "READY_TO_DELIVER", "target": %s}' % hostile,
            encoding="utf-8")
        code, stored = _deliver(lane, bundle, tmp_path, "--dry-run",
                                "--propose-receipt", str(receipt_path))
        assert code == 0, (hostile, stored)


def test_an_unreadable_blob_listing_refuses_rather_than_admitting(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for a fail-OPEN on the only ceiling bounding binary content
    (Devin on #1200).

    `entries()` ignored the return code, and `_run` yields empty stdout for
    both a missing binary (127) and a timeout (124). An unreadable head
    listing therefore read as "the candidate contains nothing": charged 0,
    returned 0, and `blob_bytes > MAX_CHANGED_BLOB_BYTES` could never fire.
    Binary content already scores zero against the line cap, so nothing else
    would have caught it.
    """
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if "ls-tree" in cmd:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: not a tree")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path, "--dry-run")
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "changed blob bytes" in stored["reason"], stored["reason"]


def test_an_unmeasurable_diff_refuses_rather_than_admitting(
        lane, tmp_path, monkeypatch) -> None:
    """Regression for the last fail-open measurement gate (Devin on #1200).

    `_run` synthesizes empty stdout for a missing binary (127) and a timeout
    (124), so an unreadable `--numstat` summed to zero and
    `lines > MAX_DIFF_LINES` could never fire — a change of any size admitted
    because the ruler broke.
    """
    bundle = _make_bundle(lane, files={"dharma_swarm/ok.py": "x = 1\n"})

    def handler(cmd, kw):
        if "--numstat" in cmd:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: bad rev")
        return None

    _intercept(monkeypatch, handler)
    code, stored = _deliver(lane, bundle, tmp_path, "--dry-run")
    assert code == 1
    assert stored["status"] == "REFUSED"
    assert "changed lines" in stored["reason"], stored["reason"]


def test_every_gate_input_checks_its_return_code() -> None:
    """The recurring defect of this PR, converted into a mechanical check.

    Six separate review findings reduced to one shape: a function that feeds a
    gate reads `result.stdout` without inspecting `result.returncode`. Because
    `_run` synthesizes an empty-stdout CompletedProcess for a missing binary
    (127) and a timeout (124), an unreadable measurement becomes a permissive
    zero — the ceiling cannot fire, or the run reports "nothing changed" over
    work it simply could not see.

    Reviewers caught these one at a time, each in a different function. This
    asserts the property over ALL of them at once, so a seventh instance fails
    here instead of costing another round. (CLAUDE.md: prefer uncharmable
    mechanical checks over reviewer vigilance.)
    """
    # Safe by construction, and each is verified by its own test above:
    #   changed_paths   — empty output is refused at the call site
    #                     ("candidate commit changes nothing")
    #   commit_subject  — cosmetic PR title with a literal fallback
    #   _run/_git/_run_bytes — the runners themselves; they PRODUCE the code
    exempt = {"changed_paths", "commit_subject",
              "_run", "_git", "_run_bytes"}

    offenders: list[str] = []
    for module in ("lane_deliver.py", "lane_propose.py"):
        source = (REPO_ROOT / "scripts" / "runtime" / module).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name in exempt:
                continue
            body = ast.get_source_segment(source, node) or ""
            runs = any(call in body for call in
                       ("_git(", "_run(", "_run_bytes("))
            if runs and "returncode" not in body:
                offenders.append(f"{module}::{node.name}")

    assert not offenders, (
        "these feed a gate but never inspect returncode, so an unreadable "
        f"input reads as a permissive zero: {offenders}")


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
    assert set(jobs) == {"preflight", "propose", "deliver"}

    # preflight holds the delivery PAT and runs no agent code; that is why it
    # is a job of its own rather than a step of propose (Devin on #1200).
    assert jobs["preflight"]["permissions"] == {"contents": "read"}

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


def test_kill_switch_guard_is_the_first_step_of_EVERY_job() -> None:
    """Propose can run 45 minutes after its own check. If the operator
    engages the switch during that window, delivery must not still push —
    so the guard is per-job, matching docs/ops/loop_control/README.md."""
    for job_name in ("preflight", "propose", "deliver"):
        first = _workflow()["jobs"][job_name]["steps"][0]
        assert "kill-switch" in first["name"].lower(), job_name
        # The ref matters: a KILLSWITCH on main halts nothing.
        assert "ref=loop-control" in first["run"], job_name
        assert "exit 1" in first["run"], job_name


def test_delivery_requires_a_ci_triggering_credential() -> None:
    """A push made with the default github.token does not trigger workflows,
    so a lane draft pushed with it strands with zero check runs — the
    `ci_never_ran` pathology pr-ci-health.yml already fights. Delivery
    prefers a PAT and degrades to verify-only without one."""
    deliver = _workflow()["jobs"]["deliver"]
    blob = yaml.safe_dump(deliver)
    assert "LANE_DELIVERY_PUSH_TOKEN" in blob
    assert "HAS_TRUSTED_TOKEN" in blob
    # Fail-closed: no trusted credential => --dry-run, never a silent push.
    verify = [s for s in deliver["steps"] if s.get("name", "").startswith("Verify")][0]
    assert 'HAS_TRUSTED_TOKEN}" != "true"' in verify["run"]
    assert "--dry-run" in verify["run"]


def test_model_credentials_are_scoped_to_the_driver_step_only() -> None:
    """Regression for a verified widening (Devin on #1200).

    At job level the provider secrets were in scope for every step of the job
    that runs untrusted agent code — including `pip install -e ".[dev]"` and
    `npm install -g`, both of which execute third-party install hooks with
    whatever the environment holds. Only the driver step needs them.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text())
    propose = workflow["jobs"]["propose"]
    keys = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"}

    assert not (keys & set(propose.get("env") or {})), (
        "model credentials must not be job-level env")

    carriers = [step.get("name") for step in propose["steps"]
                if keys & set(step.get("env") or {})]
    assert carriers == ["Run the proposing phase"], carriers

    # And no step that installs third-party code carries them.
    for step in propose["steps"]:
        run = step.get("run") or ""
        if "pip install" in run or "npm install" in run:
            assert not (keys & set(step.get("env") or {})), step.get("name")


def test_no_agent_budget_is_spent_on_a_run_that_cannot_deliver() -> None:
    """Regression for two safety behaviours cancelling out (Devin on #1200).

    Delivery degrades to --dry-run without a push credential, so no lane PR is
    opened; `attempted_task_ids()` infers consumption from delivered PR
    bodies, so it returns the empty set forever; `select_target()` then picks
    fresh[0] — the oldest ready mailbox task — on every scheduled run while
    newer tasks starve, burning a 45-minute agent budget each pass.
    """
    data = _workflow()
    propose = data["jobs"]["propose"]
    assert propose.get("needs") == "preflight"
    assert propose.get("if") == "needs.preflight.outputs.deliverable == 'true'"
    assert (data["jobs"]["preflight"]["outputs"]["deliverable"]
            == "${{ steps.probe.outputs.deliverable }}")


def test_the_untrusted_job_never_holds_a_delivery_credential() -> None:
    """Regression for a guard that broke the premise it protected (Devin,
    #1200).

    The first version of the budget guard checked the credential inside
    `propose`, which materialized a push-capable PAT in the job that runs
    agent code — the one thing this whole workflow is built to prevent. The
    probe belongs in a job that holds no agent.
    """
    data = _workflow()
    rendered = json.dumps(data["jobs"]["propose"])
    for secret in ("LANE_DELIVERY_PUSH_TOKEN", "MERGEMASTERMIKE_PAT"):
        assert secret not in rendered, secret
    # And it lives where an agent never runs.
    preflight = json.dumps(data["jobs"]["preflight"])
    assert "LANE_DELIVERY_PUSH_TOKEN" in preflight
    assert "checkout" not in preflight.lower()
    assert "DHARMA_LANE_AGENT_CMD" not in preflight


def test_preflight_probes_push_authority_not_mere_presence() -> None:
    """A configured-but-expired or under-scoped credential passes a presence
    test, spends the budget, and then delivery verify-onlys anyway — the same
    starvation loop with extra steps. Both checkpoints run the identical
    `.permissions.push` probe (Devin on #1200)."""
    steps = _workflow()["jobs"]["preflight"]["steps"]
    probe = [s for s in steps if s.get("id") == "probe"][0]["run"]
    assert ".permissions.push" in probe
    # An explicit operator dry-run must still exercise the lane.
    assert "OPERATOR_DRY_RUN" in probe

    deliver_steps = _workflow()["jobs"]["deliver"]["steps"]
    validate = [s for s in deliver_steps
                if "credential" in (s.get("name") or "").lower()][0]["run"]
    assert ".permissions.push" in validate


def test_caps_live_in_the_workflow_not_in_a_prompt() -> None:
    env = _workflow()["env"]
    assert env["LANE_MAX_DIFF_LINES"] == "600"
    assert env["LANE_MAX_CHANGED_FILES"] == "40"
    assert env["LANE_MAX_OPEN_DRAFTS"] == "1"
    assert int(_workflow()["jobs"]["propose"]["timeout-minutes"]) >= 65
