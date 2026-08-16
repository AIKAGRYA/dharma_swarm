"""Mechanical contract: the CI truth registry describes every PR-visible check.

The CI truth contract exists so an agent staring at a red PR can tell which
red blocks merge and how to reproduce it locally. That only works if the
registry is complete. It was not: 23 PR-visible check names had no row at all,
so the registry silently answered "unknown gate" for a large part of the
surface it claims to describe.

This module derives the PR-visible check names from the workflow YAML and
requires each one to be either contracted or explicitly excluded with a
reason. Deriving rather than listing is the point -- a new PR-visible job
cannot land without being classified.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
CONTRACT_PATH = REPO_ROOT / "docs" / "governance" / "CI_TRUTH_CONTRACT.json"

PR_TRIGGERS = frozenset({"pull_request", "merge_group"})

# Job names that are deliberately absent from the registry. Each needs a reason
# a reviewer can check.
EXCLUDED_JOB_NAMES = {
    "pytest": (
        "matrix job; the published check names are the expanded "
        "'pytest (3.11)' / 'pytest (3.12)', both contracted as required"
    ),
    "classify changed paths": (
        "internal path-filter helper for downstream job conditions; it gates "
        "other jobs rather than reporting a reviewable pass/fail semantic"
    ),
    "Publish derived status branch": (
        "push-event-only job inside a PR-triggered workflow; it never reports "
        "a status on a pull request"
    ),
    "Evaluate and dispatch auto-merge": (
        "Merge Master Mike dispatch lane, not a verification gate; it reports "
        "no reviewable pass/fail about the candidate diff"
    ),
}


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


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


def _pr_visible_job_names() -> dict[str, str]:
    """Map published job name -> workflow filename, for PR-visible workflows."""
    names: dict[str, str] = {}
    for path in sorted(WORKFLOW_DIR.glob("*.yml")):
        document = _load_yaml(path)
        if not (_triggers(document) & PR_TRIGGERS):
            continue
        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            name = job.get("name") or job_id
            # Templated names cannot be compared statically.
            if isinstance(name, str) and "${{" not in name:
                names.setdefault(name, path.name)
    return names


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _contracted_names(contract: dict) -> set[str]:
    names: set[str] = set()
    for row in contract["required"] + contract["advisory"]:
        names.update(row["names"])
    return names


def test_every_pr_visible_check_is_contracted_or_excluded():
    contract = _contract()
    published = _pr_visible_job_names()
    unclassified = set(published) - _contracted_names(contract) - set(EXCLUDED_JOB_NAMES)
    detail = sorted(f"{name!r} ({published[name]})" for name in unclassified)
    assert not unclassified, (
        "these PR-visible checks have no CI truth contract row and no "
        f"documented exclusion: {detail}"
    )


def test_exclusions_are_real_and_reasoned():
    published = _pr_visible_job_names()
    for name, reason in EXCLUDED_JOB_NAMES.items():
        assert name in published, (
            f"excluded job name {name!r} is no longer published; drop the "
            "exclusion instead of carrying a stale one"
        )
        assert len(reason.strip()) > 30, f"exclusion for {name!r} needs a real reason"


def test_contract_rows_are_well_formed():
    contract = _contract()
    seen_ids: set[str] = set()
    for row in contract["required"] + contract["advisory"]:
        for field in ("id", "owner", "local_command", "failure_category", "autofix"):
            assert row.get(field), f"row {row.get('id')!r} is missing {field}"
        assert isinstance(row["names"], list) and row["names"]
        assert row["id"] not in seen_ids, f"duplicate contract id {row['id']!r}"
        seen_ids.add(row["id"])
        assert row["autofix"] in {"forbidden", "limited", "manual"}


def test_required_and_advisory_names_do_not_overlap():
    contract = _contract()
    required = {name for row in contract["required"] for name in row["names"]}
    advisory = {name for row in contract["advisory"] for name in row["names"]}
    overlap = required & advisory
    assert not overlap, f"check names claimed as both required and advisory: {overlap}"


@pytest.mark.parametrize("field", ["schema", "version", "required", "advisory"])
def test_contract_keeps_its_shape(field: str):
    assert field in _contract()
