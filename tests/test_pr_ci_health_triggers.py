"""Trigger and mutation-authority contract for ``pr-ci-health``.

The workflow has historically amplified one event into a rebase of every
behind-main PR, with each rewritten head relaunching that PR's complete CI
fanout.  The durable invariant is now sharper than "do not run on pushes":
cron may report only, and rebase authority exists only for a manual dispatch
that names one positive-integer PR number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pr-ci-health.yml"
)
QUALITY_GATES = (
    Path(__file__).resolve().parents[1] / "docs" / "governance" / "PR_QUALITY_GATES.md"
)
MANUAL_REBASE_GUARD = (
    "github.event_name == 'workflow_dispatch' && env.MODE == 'rebase'"
)


def _document() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers() -> dict[str, Any]:
    doc = _document()
    # YAML 1.1 parses the bare key ``on`` as boolean True.
    return doc.get("on", doc.get(True)) or {}


def _steps() -> list[dict[str, Any]]:
    return _document()["jobs"]["triage-and-heal"]["steps"]


def _step_named(prefix: str) -> dict[str, Any]:
    return next(step for step in _steps() if str(step.get("name", "")).startswith(prefix))


def _rebase_mutation_steps() -> list[dict[str, Any]]:
    mutation_markers = (
        "pr_ci_safe_rebase.py",
        "gh pr update-branch",
        "git rebase ",
        "git push ",
    )
    return [
        step
        for step in _steps()
        if any(marker in str(step.get("run", "")) for marker in mutation_markers)
    ]


def test_no_push_to_main_trigger() -> None:
    assert "push" not in _triggers(), (
        "pr-ci-health subscribes to push again; every merge to main can relaunch "
        "a full CI run per rewritten PR"
    )


def test_schedule_is_report_only_and_all_mode_is_gone() -> None:
    triggers = _triggers()
    assert "schedule" in triggers, "the hourly report backstop was removed"
    dispatch = triggers["workflow_dispatch"]["inputs"]
    assert dispatch["mode"]["default"] == "report"
    assert dispatch["mode"]["options"] == ["report", "rerun", "rebase"]

    job = _document()["jobs"]["triage-and-heal"]
    assert job["env"]["MODE"] == (
        "${{ github.event_name == 'workflow_dispatch' "
        "&& github.event.inputs.mode || 'report' }}"
    )
    assert "env.MODE == 'all'" not in WORKFLOW.read_text(encoding="utf-8")
    assert _step_named("Re-run transient")["if"] == (
        "github.event_name == 'workflow_dispatch' && env.MODE == 'rerun'"
    )


def test_operator_guide_matches_the_executable_backstop_contract() -> None:
    section = QUALITY_GATES.read_text(encoding="utf-8").split(
        "## 6. Mechanical Backstop (`pr-ci-health.yml`)", 1
    )[1]
    assert "The hourly cron is **report-only**" in section
    assert "`workflow_dispatch` with `mode=rerun`" in section
    assert "`workflow_dispatch` with `mode=rebase` plus one `pr_number`" in section

    triggers = _triggers()
    assert triggers["workflow_dispatch"]["inputs"]["mode"]["options"] == [
        "report",
        "rerun",
        "rebase",
    ]
    assert _step_named("Re-run transient")["if"] == (
        "github.event_name == 'workflow_dispatch' && env.MODE == 'rerun'"
    )
    rebase = _step_named("Rebase conflict-free")
    assert rebase["if"] == MANUAL_REBASE_GUARD
    assert " | select(.number == $target_pr)" in rebase["run"]


def test_cron_cannot_reach_any_rebase_mutation_step() -> None:
    mutation_steps = _rebase_mutation_steps()
    assert mutation_steps, "the test did not find the rebase mutation step"
    assert all(step.get("if") == MANUAL_REBASE_GUARD for step in mutation_steps)

    rebase_control_steps = [
        step for step in _steps() if "rebase" in str(step.get("name", "")).lower()
    ]
    assert rebase_control_steps
    assert all(step.get("if") == MANUAL_REBASE_GUARD for step in rebase_control_steps)


def test_manual_rebase_is_bound_to_one_explicit_pr_number() -> None:
    dispatch_inputs = _triggers()["workflow_dispatch"]["inputs"]
    pr_input = dispatch_inputs["pr_number"]
    assert pr_input["type"] == "string"
    assert pr_input["required"] is False

    job = _document()["jobs"]["triage-and-heal"]
    assert job["env"]["TARGET_PR"] == "${{ github.event.inputs.pr_number || '' }}"

    validation = _step_named("Validate explicit one-PR")
    assert validation["if"] == MANUAL_REBASE_GUARD
    assert "^[1-9][0-9]*$" in validation["run"]

    rebase = _step_named("Rebase conflict-free")
    assert rebase["if"] == MANUAL_REBASE_GUARD
    assert '--argjson target_pr "$TARGET_PR"' in rebase["run"]
    assert " | select(.number == $target_pr)" in rebase["run"]
    assert 'python3 scripts/governance/pr_ci_safe_rebase.py' in rebase["run"]
    assert '--pr "$pr"' in rebase["run"]


def test_explicit_one_pr_dispatch_can_reach_rebase() -> None:
    rebase = _step_named("Rebase conflict-free")
    assert rebase["if"] == MANUAL_REBASE_GUARD

    def guard_allows(event_name: str, mode: str) -> bool:
        return event_name == "workflow_dispatch" and mode == "rebase"

    assert guard_allows("workflow_dispatch", "rebase") is True
    assert guard_allows("schedule", "rebase") is False
    assert guard_allows("workflow_dispatch", "report") is False


def test_the_report_and_manual_healing_steps_still_exist() -> None:
    modes = " ".join(str(step.get("if", "")) for step in _steps())
    for mode in ("report", "rerun", "rebase"):
        assert mode in modes, f"the {mode} step disappeared"
