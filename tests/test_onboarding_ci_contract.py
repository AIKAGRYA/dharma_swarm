"""WP-O4: CI/local admission parity for the onboarding door.

Covers O4-B5 (CI calls the same command with no weaker flags and no
continue-on-error) and the O4-B10 slice (PR CI checks out the declared head,
never the synthetic merge tree). The workflow text is the contract surface:
these tests pin the invariants a drive-by workflow edit would silently break.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github/workflows/active-track.yml"


def _job_block(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"workflow job {name!r} not found in active-track.yml"
    return match.group(0)


def test_ci_and_local_admission_command_equivalence() -> None:
    """O4-B5: the CI door is `make onboard` — the exact local command, not a
    reimplementation that can drift from it."""
    job = _job_block("onboarding-admission")
    assert "make onboard" in job
    assert "set -euo pipefail" in job


def test_ci_admission_has_no_weakening_flags() -> None:
    job = _job_block("onboarding-admission")
    assert "continue-on-error" not in job
    assert "|| true" not in job
    assert "--no-strict" not in job


def test_ci_pr_head_and_merge_group_packet_binding() -> None:
    """O4-B10 slice: the admission job checks out the DECLARED PR head SHA
    (falling back to github.sha for merge groups), never the synthetic
    merge ref, and runs on both pull_request and merge_group events."""
    job = _job_block("onboarding-admission")
    assert "github.event.pull_request.head.sha || github.sha" in job
    assert "pull_request" in job and "merge_group" in job


def test_verifier_selfcheck_propagates_onboard_failure() -> None:
    """O4-B6: the preflight dependency chain keeps verifier-selfcheck and the
    onboard door as hard prerequisites — a failure there fails the target."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^agent-build-preflight:(.*)$", makefile, re.MULTILINE)
    assert match
    prerequisites = match.group(1).split()
    assert "verifier-selfcheck" in prerequisites
    assert "onboard" in prerequisites
