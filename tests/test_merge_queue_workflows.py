"""Contracts for required checks evaluated on native merge-group candidates."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

def _workflow(name: str) -> dict[str, object]:
    with (WORKFLOWS / name).open(encoding="utf-8") as handle:
        return yaml.load(handle, Loader=yaml.BaseLoader)


def _step(workflow: dict[str, object], job_id: str, name: str) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_id]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    for step in steps:
        if isinstance(step, dict) and step.get("name") == name:
            return step
    raise AssertionError(f"step {name!r} not found in {job_id!r}")


def test_every_required_workflow_subscribes_to_merge_group() -> None:
    manifest = json.loads(
        (REPO_ROOT / "scripts" / "governance" / "ci_parity_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for row in manifest["required_contexts"]:
        workflow = _workflow(row["workflow"])
        triggers = workflow["on"]
        assert isinstance(triggers, dict)
        assert "merge_group" in triggers, row["context"]


def test_repaired_required_workflows_only_accept_checks_requested() -> None:
    for name in ("docops.yml", "coherence-delta.yml"):
        triggers = _workflow(name)["on"]
        assert isinstance(triggers, dict)
        merge_group = triggers["merge_group"]
        assert isinstance(merge_group, dict)
        assert merge_group["types"] == ["checks_requested"]


def test_docops_classifies_pr_and_merge_group_as_exact_delta_candidates() -> None:
    workflow = _workflow("docops.yml")
    checkout = _step(workflow, "docops-integrity", "Checkout exact event head")
    checkout_with = checkout["with"]
    assert isinstance(checkout_with, dict)
    assert "pull_request.head.sha" in checkout_with["ref"]
    assert "merge_group.head_sha" in checkout_with["ref"]
    assert checkout_with["fetch-depth"] == "0"
    assert checkout_with["persist-credentials"] == "false"

    gate = _step(workflow, "docops-integrity", "Run DocOps gate")
    script = gate["run"]
    env = gate["env"]
    assert isinstance(script, str)
    assert isinstance(env, dict)
    assert "github.event_name == 'pull_request' || " in env["IS_CHANGE_CANDIDATE"]
    assert "github.event_name == 'merge_group'" in env["IS_CHANGE_CANDIDATE"]
    assert "pull_request.base.sha" in env["PR_BASE_SHA"]
    assert "pull_request.head.sha" in env["PR_HEAD_SHA"]
    assert "merge_group.base_sha" in env["MERGE_GROUP_BASE_SHA"]
    assert "merge_group.head_sha" in env["MERGE_GROUP_HEAD_SHA"]
    assert 'case "$EVENT_NAME" in' in script
    assert "pull_request)" in script
    assert "merge_group)" in script
    assert "schedule|workflow_dispatch)" in script
    assert "Unsupported DocOps event" in script
    assert 'actual_head="$(git rev-parse HEAD)"' in script
    assert "git merge-base --is-ancestor" in script
    assert 'args+=(--counts-advisory --changed-from "$event_base")' in script


def test_docops_manual_and_scheduled_audits_remain_strict() -> None:
    script = _step(
        _workflow("docops.yml"), "docops-integrity", "Run DocOps gate"
    )["run"]
    assert isinstance(script, str)
    strict_branch = script.split("schedule|workflow_dispatch)", 1)[1].split(";;", 1)[0]
    assert "counts-advisory" not in strict_branch
    assert "changed-from" not in strict_branch


def test_coherence_merge_group_executes_fail_closed_attestation() -> None:
    workflow = _workflow("coherence-delta.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["coherence-delta"]
    assert isinstance(job, dict)
    job_if = job["if"]
    assert "github.event_name == 'merge_group'" in job_if
    assert "github.event_name != 'merge_group'" not in job_if

    attestation = _step(workflow, "coherence-delta", "Attest merge-group candidate")
    assert "github.event_name == 'merge_group'" in attestation["if"]
    script = attestation["run"]
    assert isinstance(script, str)
    assert "checks_requested" in script
    assert "refs/heads/main" in script
    assert "40-character commit SHA" in script
    assert 'actual_head="$(git rev-parse HEAD)"' in script
    assert "git merge-base --is-ancestor" in script


def test_coherence_pr_body_steps_are_pr_only() -> None:
    workflow = _workflow("coherence-delta.yml")
    for name in (
        "Fetch PR comments (comment fallback)",
        "Self-heal — derive + post Coherence Delta if missing",
        "Validate Coherence Delta fields",
    ):
        step = _step(workflow, "coherence-delta", name)
        assert "github.event_name == 'pull_request'" in step["if"]
