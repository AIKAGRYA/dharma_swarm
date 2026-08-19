"""Bounded, non-authoritative loop kill-switch observation for session status.

Why this exists
---------------
The kill-switch lives at `docs/ops/loop_control/KILLSWITCH` on the dedicated
`loop-control` branch -- NOT on `main` (docs/ops/loop_control/README.md). Every
guarded workflow asks GitHub for it directly at job start:

    repos/<owner>/<repo>/contents/docs/ops/loop_control/KILLSWITCH?ref=loop-control

An agent working inside a checkout has no such step. The obvious local check --
does the path exist in my working tree -- answers a DIFFERENT question and
always says "absent", because the file is never on `main` or on any feature
branch. A session can therefore run for hours believing the loops are running
while every guarded workflow is halting. That happened; this module is the fix.

Scope, stated so the reading is not mistaken for the ruling
----------------------------------------------------------
This is an OBSERVATION, never an admission. It reads the local
remote-tracking ref only -- no network, no fetch, no write -- so it is cheap
enough for session status and correct offline. The authority remains the
GitHub query each guarded workflow performs for itself at job start.

Because the local ref can be stale, "I could not read the ref" is a distinct
outcome from "the switch is clear". Collapsing them would make an unfetched
checkout report CLEAR while the switch is ENGAGED -- the hygiene catalogue
files that shape as AI-N1 (unreadable input reported as a definite value), and
it is the exact failure this module exists to prevent.
"""

from __future__ import annotations

import subprocess
from typing import Any

SCHEMA = "dharma_swarm.onboard_loop_killswitch.v1"
SPEC_PATH = "docs/ops/loop_control/README.md"
KILLSWITCH_REF = "refs/remotes/origin/loop-control"
KILLSWITCH_PATH = "docs/ops/loop_control/KILLSWITCH"
PROBE_SCOPE = "local_remote_tracking_ref_only"
PROBE_TIMEOUT_SECONDS = 5

# States. UNKNOWN is load-bearing: it is what an unfetched or fetch-less
# checkout must report, and it must never be rendered as if it were CLEAR.
STATE_ENGAGED = "ENGAGED"
STATE_CLEAR = "CLEAR"
STATE_UNKNOWN = "UNKNOWN"

# This reading does not gate anything and does not stand in for the workflow's
# own query, in either direction.
OBSERVATION_IS_ADMISSION = False

REFRESH_COMMAND = "git fetch origin loop-control"
AUTHORITY_COMMAND = (
    "gh api repos/{owner}/{repo}/contents/"
    "docs/ops/loop_control/KILLSWITCH?ref=loop-control"
)


def _git(args: list[str]) -> subprocess.CompletedProcess:
    """Read-only git, with both fail-closed arms the runner needs.

    `subprocess.run` raises rather than returning for a missing binary or an
    exceeded budget; either exception escaping here would take down session
    status over an observation that is allowed to be unknown.
    """
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            errors="surrogateescape",
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(args, 1, "", "")


def collect_killswitch_status() -> dict[str, Any]:
    """One read of the local `origin/loop-control` ref. Never raises."""
    projection: dict[str, Any] = {
        "schema": SCHEMA,
        "spec_path": SPEC_PATH,
        "probe_scope": PROBE_SCOPE,
        "ref": KILLSWITCH_REF,
        "path": KILLSWITCH_PATH,
        "observation_is_admission": OBSERVATION_IS_ADMISSION,
        "authority_command": AUTHORITY_COMMAND,
        "refresh_command": REFRESH_COMMAND,
        "state": STATE_UNKNOWN,
        "detail": "",
        "stamp": "",
    }

    ref_present = _git(["rev-parse", "--verify", "--quiet", KILLSWITCH_REF])
    if ref_present.returncode != 0 or not ref_present.stdout.strip():
        projection["detail"] = (
            "no local origin/loop-control ref; this checkout has never fetched "
            "the branch the switch lives on"
        )
        return projection

    # `cat-file -e` answers presence without materialising the blob. Exit 0 =
    # present, non-zero = absent OR unreadable -- so a second read is needed
    # before either is reported as a state.
    blob = f"{KILLSWITCH_REF}:{KILLSWITCH_PATH}"
    present = _git(["cat-file", "-e", blob])
    if present.returncode == 0:
        projection["state"] = STATE_ENGAGED
        contents = _git(["cat-file", "-p", blob])
        if contents.returncode == 0:
            first_line = contents.stdout.strip().splitlines()
            projection["stamp"] = first_line[0][:200] if first_line else ""
        projection["detail"] = (
            "guarded workflows halt at job start while this file is present; "
            "red-while-halted is deliberate signal"
        )
        return projection

    # Absent from a ref we could read is a real CLEAR. Distinguish it from a
    # ref we could not read at all by re-asking for the tree.
    tree = _git(["ls-tree", "--name-only", KILLSWITCH_REF, "docs/ops/loop_control/"])
    if tree.returncode != 0:
        projection["detail"] = (
            "origin/loop-control exists but its tree could not be read; "
            "refusing to report CLEAR from a read that failed"
        )
        return projection

    projection["state"] = STATE_CLEAR
    projection["detail"] = "no KILLSWITCH file on the local origin/loop-control ref"
    return projection
