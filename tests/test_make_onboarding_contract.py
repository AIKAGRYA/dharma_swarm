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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")


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


def test_closeout_recipe_evaluates_packet_exactly_once() -> None:
    recipe = _recipe("agent-build-closeout")
    assert recipe.count("run_agent_work_packet.py") == 1
    assert "--packet $(PACKET)" in recipe


def test_preflight_with_invalid_packet_fails_closed(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus-packet.json"
    bogus.write_text("{\"id\": \"nope\"}", encoding="utf-8")
    result = _make(f"PACKET={bogus}", "agent-build-preflight")
    assert result.returncode != 0, (
        "an invalid packet must fail preflight, not degrade to baseline"
    )


# --- O4-B7: the A2A identity target is untouched ------------------------------

def test_a2a_identity_target_command_is_unchanged() -> None:
    recipe = _recipe("agent-onboard")
    assert "a2a_agent_onboard.py $(ARGS)" in recipe


# --- O4-B8: ARGS forwarding and usage exits -----------------------------------

def test_make_forwards_onboard_args_and_usage_exit() -> None:
    recipe = _recipe("onboard")
    assert "agent_onboard.py $(ARGS)" in recipe
    result = _make("onboard", "ARGS=--definitely-not-a-real-flag")
    assert result.returncode == 2, (
        f"unknown onboard flags must keep exit 2, got {result.returncode}"
    )
