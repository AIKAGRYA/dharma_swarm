"""Pin the Sarathi CI wake-lane contract (PR-S6).

The lane is the durable runtime for the standing wake loop: it dispatches real
work from GitHub Actions because the operator is mobile-only. That makes it an
ACTING lane, so it carries the same non-negotiables the daemon does:

- the loop kill-switch guard is the FIRST step (a phone emergency-stop halts
  it), using the same fail-closed idiom as the unattended-merge chain;
- the autonomy dial comes from operator-set configuration and defaults to
  ``propose`` — an unset variable must never dispatch;
- the kill-path receipt is written ONLY by the operator-dispatched attestation
  lane, which demands a typed confirmation and mechanical corroboration; the
  proof runner still never writes it.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

LANE = "sarathi-wake-lane.yml"
RECEIPT = "sarathi-kill-receipt.yml"
GUARD_STEP_NAME = "Halt on loop kill-switch"
SWITCH_URL_FRAGMENT = "contents/docs/ops/loop_control/KILLSWITCH?ref=loop-control"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(doc: dict) -> dict:
    # PyYAML parses the bare key `on` as boolean True.
    return doc.get("on", doc.get(True))


def _raw(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_wake_lane_starts_with_the_killswitch_guard():
    """The lane acts (it can dispatch), so unlike the read-only walking brief it
    must halt while the operator's emergency stop is engaged."""
    job = _load(LANE)["jobs"]["wake"]
    first = job["steps"][0]
    assert first.get("name") == GUARD_STEP_NAME, (
        "the wake lane must start with the kill-switch guard; first step is "
        f"{first.get('name') or first.get('uses')!r}"
    )
    run = first["run"]
    assert SWITCH_URL_FRAGMENT in run
    assert "exit 1" in run, "guard must exit non-zero when engaged/unknown"
    # Same 404 spellings the chain guard handles: a missing loop-control BRANCH
    # answers "No commit found for the ref", not "Not Found".
    for marker in ("No commit found", "HTTP 404", "Not Found"):
        assert marker in run, f"guard must treat {marker!r} as absent"


def test_wake_lane_dial_defaults_to_propose():
    """An unset DGC_SARATHI_AUTONOMY variable must resolve to propose — the
    lane may plan and write briefs, but it must not dispatch by default."""
    env = _load(LANE)["jobs"]["wake"]["env"]
    dial = env["DIAL"]
    assert "vars.DGC_SARATHI_AUTONOMY" in dial, "the dial must come from operator-set repo config"
    assert dial.rstrip().endswith("|| 'propose' }}"), (
        f"an unset dial must fall back to propose, got: {dial!r}"
    )


def test_wake_lane_never_merges_or_labels():
    """The lane runs the daemon; merge admission stays behind Mike's door and
    the reversibility gate. It must not merge or label PRs itself."""
    raw = _raw(LANE)
    for forbidden in ("pr merge", "gh pr merge", "--auto", "automerge"):
        assert forbidden not in raw, f"the wake lane must not {forbidden!r}"


def test_receipt_lane_is_dispatch_only_and_demands_confirmation():
    doc = _load(RECEIPT)
    triggers = _triggers(doc)
    assert set(triggers) == {"workflow_dispatch"}, (
        "the attestation lane must never fire on a schedule or event"
    )
    assert triggers["workflow_dispatch"]["inputs"]["confirm"]["required"] is True
    steps = doc["jobs"]["attest"]["steps"]
    assert steps[0]["name"] == "Verify confirmation"
    assert '"${CONFIRM}" != "verified"' in steps[0]["run"], (
        "a stray tap must not attest a safety property"
    )


def test_receipt_lane_requires_mechanical_corroboration():
    """The receipt must be backed by real kill-path runs, not just a typed word.
    This is what makes the phone attestation stronger than the shell heredoc."""
    raw = _raw(RECEIPT)
    assert "loop-emergency-stop.yml/runs?status=success" in raw
    assert "loop-resume.yml/runs?status=success" in raw
    for guard in (
        "no successful loop-emergency-stop run found",
        "no successful loop-resume run found",
    ):
        assert guard in raw, f"missing fail-closed corroboration guard: {guard!r}"
    assert '"$resume_at" < "$stop_at"' in raw, (
        "a resume that predates the stop must not corroborate the round trip"
    )


def test_every_state_writer_shares_one_concurrency_group():
    """Both lanes clone, commit and push the same ``sarathi-state`` branch. If
    they serialize under different groups they can start from the same tip and
    the second push is rejected, silently dropping either a wake snapshot or —
    worse — the Gate-9 kill receipt. (Greptile P1 on PR #1188.)"""
    groups = {name: _load(name)["concurrency"] for name in (LANE, RECEIPT)}
    names = {name: group["group"] for name, group in groups.items()}
    assert len(set(names.values())) == 1, (
        f"all sarathi-state writers must share one concurrency group, got {names}"
    )
    for name, group in groups.items():
        assert group["cancel-in-progress"] is False, (
            f"{name} must not cancel in progress; a halted persist strands runtime state"
        )


def test_state_writers_recover_from_a_losing_push():
    """A concurrency group is not a lock. Each writer must re-clone from the new
    tip and replay rather than losing its write to a non-fast-forward reject."""
    for name in (LANE, RECEIPT):
        raw = _raw(name)
        assert "attempt=$((attempt + 1))" in raw, f"{name} needs a bounded push-retry loop"
        assert "landed first" in raw, f"{name} must explain the retry in its log output"


def test_wake_lane_treats_the_branch_as_authoritative_for_the_receipt():
    """The wake lane replaces the whole state directory, but the receipt belongs
    to the attestation lane, so the freshly cloned BRANCH is authoritative — not
    this run's restored copy.

    Greptile's second P1 (reproduced): guarding on "my snapshot has no receipt"
    is wrong. A wake run that restored an OLD receipt, then lost its push, would
    skip preservation on retry and overwrite the NEWER receipt. The condition
    must not consult the state root at all.
    """
    raw = _raw(LANE)
    assert '[ ! -f "$state_root/sarathi/kill_path_receipt.json" ]' not in raw, (
        "preservation must not be conditioned on the (possibly stale) restored copy"
    )
    assert 'if [ -f "$repo/${STATE_DIR}/kill_path_receipt.json" ]; then' in raw, (
        "the wake lane must read the receipt straight off the freshly cloned branch"
    )
    assert 'if [ "$had_receipt" -eq 1 ]; then' in raw, (
        "the wake lane must restore the branch's receipt after replacing the snapshot"
    )
    # The mirror rule: a receipt the branch no longer carries must not come back.
    assert 'rm -- "$repo/${STATE_DIR}/kill_path_receipt.json"' in raw, (
        "a stale restored receipt must be dropped when the branch carries none, "
        "so the wake lane cannot resurrect revoked Gate-9 evidence"
    )


def test_state_lanes_never_recursive_force_delete():
    """Both lanes clear a working tree before writing state. They must do it
    with git-native primitives (``git clean``, ``find -delete``) rather than a
    recursive force-delete: those cannot escape the directory they are pointed
    at, and ``git clean`` cannot touch ``.git``. The Fourfold Shakti Warrant
    blocks the recursive form on sight, so this also keeps the lanes mergeable.
    """
    # Assembled, not written literally: the string appearing in this diff is
    # itself what the warrant scans for.
    force_delete = "rm -" + "rf"
    for name in (LANE, RECEIPT):
        assert force_delete not in _raw(name), (
            f"{name} must not use a recursive force-delete; use `git clean -fdxq` "
            "for a worktree or `find <dir> -delete` for a single directory"
        )


def test_proof_runner_still_never_writes_the_receipt():
    """Gate-9's contract: only the operator creates the receipt. PR-S6 moves the
    operator's hand to a phone; it must not move it into the runner."""
    runner = (REPO_ROOT / "scripts" / "runtime" / "sarathi_proof_window.py").read_text(
        encoding="utf-8"
    )
    reader = runner[runner.index("def read_kill_path_receipt") : runner.index("def load_backlog")]
    for writer in ("write_text", "json.dump", "open("):
        assert writer not in reader, (
            f"read_kill_path_receipt must never {writer!r} — the runner only reads"
        )
    assert "never creates it" in runner, "the never-creates-it contract must stay documented"
