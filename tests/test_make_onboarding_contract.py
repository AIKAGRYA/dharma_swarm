"""WP-O4: the Make-level onboarding contract.

Covers O4-B1 (make orient is deep/read-only under a write-attempt guard;
only the explicit owner command writes context), O4-B2 (preflight consumes
the packet evaluator exactly once, fail-closed), O4-B7 (`make agent-onboard`
unchanged), and O4-B8 (Make forwards documented ARGS; unknown flags keep
exit 2).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
RUNNER = "scripts/governance/run_agent_work_packet.py"


def _recipe(target: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n|ifdef .*\n|endif\n)*)",
        MAKEFILE,
        re.MULTILINE,
    )
    assert match, f"Makefile target {target!r} not found"
    return match.group(0)


def _make(*args: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "-s", *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
    )


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--ignored=matching"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    ).stdout


# --- O4-B1: orient is mutation-free ------------------------------------------

def test_orient_recipe_never_writes_context() -> None:
    recipe = _recipe("orient")
    assert "--write-context" not in recipe, (
        "make orient must be a mutation-free projection; context refresh "
        "belongs only to the explicit owner command (spec §2.1)"
    )


@pytest.mark.timeout(180)
def test_make_orient_attempts_no_repository_write() -> None:
    before = _porcelain()
    result = _make("orient")
    assert result.returncode == 0, result.stderr[-2000:]
    assert _porcelain() == before, "make orient dirtied the worktree"


def test_explicit_context_refresh_command_is_documented() -> None:
    """The owner command stays discoverable next to the read-only target."""
    assert "orientation_graph.py --write-context" in MAKEFILE


# --- O4-B2: preflight consumes the packet evaluator --------------------------

def test_preflight_recipe_evaluates_packet_exactly_once() -> None:
    recipe = _recipe("agent-build-preflight")
    assert recipe.count("run_agent_work_packet.py") == 1
    assert "--packet $(PACKET)" in recipe
    assert "--dry-run" in recipe


def test_closeout_does_not_run_the_broken_dry_run_packet_eval() -> None:
    """--dry-run is the WRONG closeout mode: it requires HEAD == base_ref, so
    it fails against the very packet whose work has been committed, and for
    legacy packets it returns before running gates. Correct post-edit packet
    re-evaluation is WP-O4-B3 (declared next slice); closeout must not claim
    it by wiring the broken command (Codex P2 on #897)."""
    recipe = _recipe("agent-build-closeout")
    assert "run_agent_work_packet.py" not in recipe
    assert "governance-all" in recipe


def test_preflight_packet_evaluation_fails_closed(tmp_path: Path) -> None:
    """The exact command the Makefile preflight runs for PACKET
    (`run_agent_work_packet.py --packet <p> --dry-run`) must fail closed on an
    invalid packet. Exercised directly, not through `make agent-build-preflight`
    — that target chains verifier-selfcheck/onboard/hygiene-check, minutes of
    unrelated work that flapped the 30s per-test budget on CI (#897)."""
    bogus = tmp_path / "bogus-packet.json"
    bogus.write_text('{"id": "nope"}', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, RUNNER, "--packet", str(bogus), "--dry-run"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode != 0, (
        "an invalid packet must fail the preflight evaluator, not pass"
    )


# --- O4-B7: the A2A identity target is untouched ------------------------------

def test_a2a_identity_target_command_is_unchanged() -> None:
    recipe = _recipe("agent-onboard")
    assert "a2a_agent_onboard.py $(ARGS)" in recipe


# --- O4-B8: ARGS forwarding and usage exits -----------------------------------

@pytest.mark.timeout(120)
def test_make_forwards_onboard_args_and_usage_exit() -> None:
    recipe = _recipe("onboard")
    assert "agent_onboard.py $(ARGS)" in recipe
    result = _make("onboard", "ARGS=--definitely-not-a-real-flag")
    assert result.returncode == 2, (
        f"unknown onboard flags must keep exit 2, got {result.returncode}"
    )
