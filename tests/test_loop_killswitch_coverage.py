"""Mechanical contract: the loop kill-switch actually halts every lane it should.

The kill-switch is only as good as its coverage. Before this contract existed
the guard was copy-pasted into some lanes and simply absent from five
write-capable scheduled lanes, so engaging the switch left PR-closing,
branch-deleting and main-pushing automation running.

This module pins three things:

1. the shared guard exists and fails closed;
2. every lane that must halt carries a guard; and
3. no NEW write-capable automated lane can appear unclassified -- it must be
   added to ``GUARDED_LANES`` or given an explicit, written exemption reason.

(3) is the uncharmable part: the set of write-capable automated workflows is
derived from the workflow YAML, never from a hand-maintained list.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ACTION_PATH = REPO_ROOT / ".github" / "actions" / "loop-killswitch" / "action.yml"

ACTION_REFERENCE = "./.github/actions/loop-killswitch"
INLINE_MARKER = "docs/ops/loop_control/KILLSWITCH"

AUTOMATION_TRIGGERS = frozenset(
    {
        "schedule",
        "push",
        "workflow_dispatch",
        "issue_comment",
        "pull_request_review_comment",
    }
)

# Lanes that must stop while the switch is engaged.
GUARDED_LANES = frozenset(
    {
        "automerge.yml",
        "codex-mention-router.yml",
        "docops-reconcile-main.yml",
        "hardening-lane.yml",
        "loop-watcher.yml",
        "merge-master-mike-backlog.yml",
        "pr-ci-health.yml",
        "pr-dedupe.yml",
        "stale-pr.yml",
    }
)

# Lanes newly brought under the switch, which must use the shared action rather
# than growing a seventh inline copy of the guard.
SHARED_ACTION_LANES = frozenset(
    {
        "docops-reconcile-main.yml",
        "pr-ci-health.yml",
        "pr-dedupe.yml",
        "stale-pr.yml",
    }
)

# Lanes that SHOULD halt and currently do not. These are open gaps, recorded
# with the reason they could not be closed here -- deliberately kept separate
# from EXEMPT_LANES so a real hole is never filed as a design decision.
DEFERRED_LANES = {
    "branch-janitor.yml": (
        "owned by track sovereign-safety-tcb-2026-07; the AgentOps packet-scope "
        "gate correctly refuses a titanium-scoped packet that edits a sibling "
        "track's surface, so the guard must land in a packet filed under that "
        "track. Deletes branches on dispatch"
    ),
    "active-track.yml": (
        "carries the merge-required 'Onboarding admission parity' check, so a "
        "workflow-level halt would block every merge in the repository. Needs a "
        "job-level guard on its publish job alone, which force-pushes derived "
        "status to generated/status on every main push"
    ),
}

# Write-capable automated lanes that deliberately keep running while halted.
# Every entry needs a reason a reviewer can check, not just an allowlist slot.
EXEMPT_LANES = {
    "loop-emergency-stop.yml": (
        "engages the kill-switch; gating it on the switch would make the stop "
        "un-pressable once already halted"
    ),
    "loop-resume.yml": (
        "clears the kill-switch; gating it on the switch would make the halt "
        "unrecoverable"
    ),
    "walking-brief.yml": (
        "documented in-file exception: operator brief is reporting only and is "
        "the surface an operator reads while deciding whether to resume"
    ),
    "codeql.yml": (
        "its write scope is security-events (scan upload), not repository "
        "content, and it mutates nothing a halt needs to stop"
    ),
    "semgrep.yml": (
        "its write scope is security-events (scan upload), not repository "
        "content, and it mutates nothing a halt needs to stop"
    ),
}


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _permissions_grant_write(permissions: object) -> bool:
    if permissions == "write-all":
        return True
    if isinstance(permissions, dict):
        return any(value == "write" for value in permissions.values())
    return False


def _is_write_capable(document: dict) -> bool:
    if _permissions_grant_write(document.get("permissions")):
        return True
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return False
    return any(
        isinstance(job, dict) and _permissions_grant_write(job.get("permissions"))
        for job in jobs.values()
    )


def _triggers(document: dict) -> set[str]:
    # PyYAML resolves the unquoted `on:` key to the boolean True.
    raw = document.get("on", document.get(True))
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, dict):
        return set(raw)
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    return set()


def _is_automated(document: dict) -> bool:
    return bool(_triggers(document) & AUTOMATION_TRIGGERS)


def _workflow_paths() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml"))


def _write_capable_automated_lanes() -> set[str]:
    lanes = set()
    for path in _workflow_paths():
        document = _load(path)
        if _is_write_capable(document) and _is_automated(document):
            lanes.add(path.name)
    return lanes


def _has_guard(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return ACTION_REFERENCE in text or INLINE_MARKER in text


def test_shared_guard_action_exists_and_is_composite():
    assert ACTION_PATH.is_file(), f"missing shared guard action at {ACTION_PATH}"
    document = _load(ACTION_PATH)
    assert document.get("runs", {}).get("using") == "composite"


def test_shared_guard_fails_closed_on_unknown_state():
    """Present => halt, 404 => proceed, anything else => refuse to run."""
    text = ACTION_PATH.read_text(encoding="utf-8")
    assert "HALTED BY KILLSWITCH" in text
    assert "kill-switch absent" in text
    assert "failing closed" in text
    # Two distinct `exit 1` paths: switch engaged, and indeterminate state.
    assert text.count("exit 1") >= 2


@pytest.mark.parametrize("lane", sorted(GUARDED_LANES))
def test_guarded_lane_carries_a_kill_switch_guard(lane: str):
    path = WORKFLOW_DIR / lane
    assert path.is_file(), f"{lane} is listed as guarded but does not exist"
    assert _has_guard(path), (
        f"{lane} must halt while the loop kill-switch is engaged; add "
        f"`uses: {ACTION_REFERENCE}` after checkout"
    )


@pytest.mark.parametrize("lane", sorted(SHARED_ACTION_LANES))
def test_newly_covered_lane_uses_the_shared_action(lane: str):
    """These lanes must not regrow a private copy of the guard."""
    text = (WORKFLOW_DIR / lane).read_text(encoding="utf-8")
    assert ACTION_REFERENCE in text, f"{lane} should consume the shared action"


def test_every_write_capable_automated_lane_is_classified():
    """A new write-capable automated lane must be guarded, exempt, or deferred."""
    classified = GUARDED_LANES | set(EXEMPT_LANES) | set(DEFERRED_LANES)
    unclassified = _write_capable_automated_lanes() - classified
    assert not unclassified, (
        "these write-capable automated workflows are neither guarded, exempt, "
        f"nor a recorded deferred gap for the loop kill-switch: {sorted(unclassified)}"
    )


def test_exemptions_are_real_and_reasoned():
    for lane, reason in EXEMPT_LANES.items():
        assert (WORKFLOW_DIR / lane).is_file(), f"exempt lane {lane} does not exist"
        assert len(reason.strip()) > 30, f"exemption for {lane} needs a real reason"


def test_deferred_gaps_are_real_reasoned_and_still_open():
    """A deferred lane is an admitted hole, not a design decision.

    If one acquires a guard, it must graduate to GUARDED_LANES so the coverage
    test starts enforcing it, rather than lingering here as a stale excuse.
    """
    for lane, reason in DEFERRED_LANES.items():
        path = WORKFLOW_DIR / lane
        assert path.is_file(), f"deferred lane {lane} does not exist"
        assert len(reason.strip()) > 30, f"deferred lane {lane} needs a real reason"
        assert not _has_guard(path), (
            f"{lane} now carries a guard; move it from DEFERRED_LANES to "
            "GUARDED_LANES so its coverage is enforced"
        )


def test_deferred_and_exempt_are_disjoint():
    overlap = set(DEFERRED_LANES) & set(EXEMPT_LANES)
    assert not overlap, f"a lane cannot be both an admitted gap and exempt: {overlap}"


def test_switch_management_lanes_are_never_guarded():
    """Guarding these would make a halt unrecoverable."""
    for lane in ("loop-emergency-stop.yml", "loop-resume.yml"):
        text = (WORKFLOW_DIR / lane).read_text(encoding="utf-8")
        assert ACTION_REFERENCE not in text, (
            f"{lane} manages the kill-switch and must not be gated on it"
        )
