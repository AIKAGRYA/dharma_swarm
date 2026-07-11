"""Governance tests for the ACTIVE_TRACK self-healing layer.

These tests guard the governance system itself \u2014 the prerequisites for
ACTIVE_TRACK.yaml, the renderer, and the track-status checker. They are
intentionally small and fast: they assert structural invariants, not the
contents of the current track.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
EVIDENCE = REPO_ROOT / "reports/governance/active_track_evidence.json"

CHECK_SCRIPT = REPO_ROOT / "scripts/governance/check_track_status.py"
RENDER_SCRIPT = REPO_ROOT / "scripts/governance/render_active_track_includes.py"
ONBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_onboard.py"

MANAGED_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs/governance/SOVEREIGN_MANIFEST.md",
    REPO_ROOT / "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
]


def _run(script: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
    )


def test_active_track_yaml_exists() -> None:
    assert ACTIVE_TRACK.exists(), "ACTIVE_TRACK.yaml is the single source of truth for the current track."


def test_active_track_loads() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import (  # type: ignore
        load_active_track, normalize_portfolio, SUPPORTED_SCHEMA_VERSIONS)

    track = load_active_track(ACTIVE_TRACK)
    assert track.get("schema_version") in SUPPORTED_SCHEMA_VERSIONS
    p = normalize_portfolio(track)
    assert p["active_tracks"], "ACTIVE_TRACK.yaml must declare at least one active track."
    for t in p["active_tracks"]:
        assert t.get("id"), "every track requires an id."
        assert t.get("status") in {"ACTIVE", "SHIPPABLE"}, \
            f"unexpected status: {t.get('status')!r}"
        assert t.get("verified_at"), f"{t.get('id')} requires verified_at."
    # v2: every active track must serve a declared spine objective.
    spine_ids = {o.get("id") for o in p["spine_objectives"]}
    if spine_ids:
        for t in p["active_tracks"]:
            assert t.get("serves") in spine_ids, \
                f"{t.get('id')} serves '{t.get('serves')}' not in spine objectives {sorted(spine_ids)}"


@pytest.mark.timeout(270)
def test_check_track_status_runs() -> None:
    """The checker runs to completion and writes evidence JSON."""
    # The checker executes every track's command_passes criteria, so its
    # wall-clock grows with the admitted portfolio: ~50s on a warm fast host
    # at 10 tracks (2026-07-11), slower on shared CI runners. The budget must
    # bound "hung", not "busy" — a tight bound here blocks unrelated PRs.
    result = _run(CHECK_SCRIPT, "--warn-only", timeout=240)
    assert result.returncode == 0, result.stderr
    assert EVIDENCE.exists(), "evidence JSON must be written"
    payload = json.loads(EVIDENCE.read_text())
    assert "active_track_id" in payload
    assert "criteria" in payload
    assert isinstance(payload["criteria"], list)


def test_managed_blocks_in_sync() -> None:
    """All managed files have the ACTIVE_TRACK block matching the YAML."""
    result = _run(RENDER_SCRIPT, "--check")
    assert result.returncode == 0, (
        "Managed governance blocks are out of sync with ACTIVE_TRACK.yaml. "
        "Run: python3 scripts/governance/render_active_track_includes.py\n\n"
        f"stderr:\n{result.stderr}"
    )


def test_managed_files_have_markers() -> None:
    for path in MANAGED_FILES:
        text = path.read_text(encoding="utf-8")
        assert "<!-- ACTIVE_TRACK:START -->" in text, \
            f"{path} missing ACTIVE_TRACK start marker"
        assert "<!-- ACTIVE_TRACK:END -->" in text, \
            f"{path} missing ACTIVE_TRACK end marker"


@pytest.mark.timeout(75)
def test_onboard_command_succeeds() -> None:
    """agent_onboard.py runs end-to-end and prints the active track section."""
    result = _run(ONBOARD_SCRIPT)
    # Return code may be 1 if prereqs fail; that's a real signal, not a test failure.
    # We just check the command produced the structural sections.
    assert "ACTIVE PORTFOLIO" in result.stdout
    assert "LIVING AXIOMS" in result.stdout
    assert "WHAT TO DO NEXT" in result.stdout


def test_underclaim_detector_flags_shipped_but_open_items() -> None:
    """A next-item whose linked evidence criterion passes must WARN track-underclaim.

    This is the inverse of the false-shippable trap: every other defense catches
    claims ahead of reality; this one catches the ledger falling behind it.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import evaluate_track  # type: ignore

    track = {
        "id": "t-underclaim",
        "status": "ACTIVE",
        "completion_criteria": [
            {"id": "shipped_thing", "kind": "file_exists",
             "file": "docs/governance/ACTIVE_TRACK.yaml"},
        ],
        "next_items": [
            # open blocker whose evidence already passes -> underclaim
            {"id": 1, "what": "(blocker) build the shipped thing",
             "kind": "code", "blocker": True,
             "evidence_criterion": "shipped_thing"},
            # reconciled in prose -> NOT an underclaim
            {"id": 2, "what": "DONE 2026-07-03: other thing", "kind": "code",
             "blocker": False, "evidence_criterion": "shipped_thing"},
            # evidence criterion does not pass -> NOT an underclaim
            {"id": 3, "what": "future thing", "kind": "code", "blocker": False,
             "evidence_criterion": "no_such_criterion"},
            # no evidence link -> NOT an underclaim (opt-in mechanism)
            {"id": 4, "what": "unlinked thing", "kind": "code", "blocker": True},
        ],
    }
    r = evaluate_track(track)
    ucs = r["underclaims"]
    assert [uc["item_id"] for uc in ucs] == [1]
    assert ucs[0]["evidence_criterion"] == "shipped_thing"
    assert ucs[0]["blocker"] is True


@pytest.mark.timeout(75)
def test_underclaims_surface_in_evidence_payload() -> None:
    """Every track payload carries the underclaims field, and any underclaim in
    the payload also surfaces as a WARN line in the checker output — the ledger
    can fall behind reality, but never silently."""
    result = _run(CHECK_SCRIPT)
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    out = result.stdout + result.stderr
    for tr in payload.get("active_tracks", []):
        assert "underclaims" in tr, f"track {tr.get('id')} missing underclaims field"
        for uc in tr["underclaims"]:
            assert f"track-underclaim:{tr['id']}:{uc['item_id']}" in out
