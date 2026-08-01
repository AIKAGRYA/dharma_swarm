"""Pin the loop kill-switch contract across the unattended-merge chain.

Contract (docs/ops/loop_control/README.md, Tier 2 under the 2026-07-29
operator ruling):

- automerge.yml, codex-mention-router.yml, and merge-master-mike-backlog.yml
  each carry "Halt on loop kill-switch" as the FIRST step of their job, so
  nothing in the unattended chain runs while the switch is engaged.
- The guard reads docs/ops/loop_control/KILLSWITCH on the loop-control
  branch, exits 1 when present, proceeds only on 404, and fails closed on
  any other error.
- loop-emergency-stop.yml and loop-resume.yml are workflow_dispatch-only;
  resume demands the literal confirmation string "resume".
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

GUARD_STEP_NAME = "Halt on loop kill-switch"
SWITCH_URL_FRAGMENT = "contents/docs/ops/loop_control/KILLSWITCH?ref=loop-control"

GUARDED = {
    "automerge.yml": "evaluate",
    "codex-mention-router.yml": "route",
    "merge-master-mike-backlog.yml": "backlog",
}


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def _triggers(doc: dict) -> dict:
    # PyYAML parses the bare key `on` as boolean True.
    return doc.get("on", doc.get(True))


def test_guard_is_first_step_of_every_chain_workflow():
    for workflow, job_name in GUARDED.items():
        doc = _load(workflow)
        job = doc["jobs"][job_name]
        first = job["steps"][0]
        assert first.get("name") == GUARD_STEP_NAME, (
            f"{workflow}:{job_name} must start with the kill-switch guard; "
            f"first step is {first.get('name') or first.get('uses')!r}"
        )
        run = first["run"]
        assert SWITCH_URL_FRAGMENT in run, f"{workflow}: guard must read the loop-control switch path"
        assert "exit 1" in run, f"{workflow}: guard must exit non-zero when engaged/unknown"
        # The GitHub 404 for a missing BRANCH says "No commit found for the
        # ref loop-control" (observed live on PR #1157 run 30433704716), not
        # "Not Found" — the guard must treat both as absent, plus the generic
        # HTTP 404 markers, or a fresh repo fails closed forever.
        assert "No commit found" in run, f"{workflow}: guard must treat a missing loop-control branch as absent"
        assert "HTTP 404" in run, f"{workflow}: guard must match gh's HTTP 404 marker"
        assert "Not Found" in run, f"{workflow}: guard must proceed only on an explicit 404"


def test_guard_fails_closed_on_unknown_state():
    for workflow in GUARDED:
        run = _load(workflow)["jobs"][GUARDED[workflow]]["steps"][0]["run"]
        assert "failing closed" in run, f"{workflow}: unknown switch state must fail closed"


def test_emergency_stop_is_dispatch_only():
    triggers = _triggers(_load("loop-emergency-stop.yml"))
    assert set(triggers) == {"workflow_dispatch"}, (
        "loop-emergency-stop must have no schedule/event triggers"
    )


def test_resume_is_dispatch_only_and_requires_confirmation():
    doc = _load("loop-resume.yml")
    triggers = _triggers(doc)
    assert set(triggers) == {"workflow_dispatch"}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert inputs["confirm"]["required"] is True
    steps = doc["jobs"]["resume"]["steps"]
    verify = steps[0]
    assert '"${CONFIRM}" != "resume"' in verify["run"], (
        "resume must refuse unless the confirmation input is exactly 'resume'"
    )


def test_control_workflows_write_only_the_control_branch():
    for name in ("loop-emergency-stop.yml", "loop-resume.yml"):
        doc = _load(name)
        text = (WORKFLOWS / name).read_text()
        assert doc["permissions"] == {"contents": "write"}
        assert "CONTROL_BRANCH: loop-control" in text, (
            f"{name}: switch writes must target the loop-control branch, never main"
        )
