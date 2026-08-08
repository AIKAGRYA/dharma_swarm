"""`pr-ci-health` must not rebase the whole backlog on every merge to main.

The workflow once subscribed to `push: branches: [main]` and, on each such
push, rebased every conflict-free behind-main PR. Each rebase relaunches that
PR's full workflow set, so one merge cost roughly one full CI run per open PR.

Measured 2026-08-07: four merges (01:42, 03:03, 04:37, 06:04Z) produced four
rebase waves of ~18-20 PRs each. The queue reached 676 runs, a 2-second
required job waited 80 minutes for a runner, and PR #1286 was rebased four
times -- discarding a complete 38/38 green sweep it had already earned.

The trigger's stated premise was "require branches up to date before merging"
being enabled, which made a behind-main PR unmergeable. That premise no longer
holds: a behind-main PR reports `mergeable_state: unstable` (mergeable), not
`behind`. With the premise gone the trigger was pure cost.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pr-ci-health.yml"
)


def _triggers() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 parses the bare key `on` as boolean True.
    return doc.get("on", doc.get(True)) or {}


def test_no_push_to_main_trigger() -> None:
    """THE regression. Re-adding this re-creates the rebase stampede."""
    assert "push" not in _triggers(), (
        "pr-ci-health subscribes to push again; every merge to main will rebase "
        "the whole backlog and relaunch a full CI run per open PR"
    )


def test_the_hourly_backstop_is_retained() -> None:
    """Removing the stampede must not remove the safety net. The cron pass
    still triages, reruns transient flakes, and rebases -- just once an hour
    instead of once per merge."""
    triggers = _triggers()
    assert "schedule" in triggers, "the hourly mechanical backstop was removed"
    assert "workflow_dispatch" in triggers, "manual invocation was removed"


def test_the_healing_steps_still_exist() -> None:
    """Guard against 'fixing' the cost by gutting the workflow instead."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    modes = " ".join(
        str(step.get("if", "")) for step in doc["jobs"]["triage-and-heal"]["steps"]
    )
    for mode in ("report", "rerun", "rebase"):
        assert mode in modes, f"the {mode} step disappeared"
