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


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )


def test_active_track_yaml_exists() -> None:
    assert ACTIVE_TRACK.exists(), "ACTIVE_TRACK.yaml is the single source of truth for the current track."


def test_active_track_loads() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import load_active_track  # type: ignore

    track = load_active_track(ACTIVE_TRACK)
    assert track.get("schema_version") == 2
    active_tracks = track.get("active_tracks")
    assert isinstance(active_tracks, list), "ACTIVE_TRACK.yaml must declare active_tracks as a list."
    assert 1 <= len(active_tracks) <= 10, \
        f"1-10 active tracks required, got {len(active_tracks)}."
    primaries = [t for t in active_tracks if t.get("primary")]
    assert len(primaries) == 1, \
        f"exactly one track must be marked primary, got {len(primaries)}."
    for trk in active_tracks:
        assert trk.get("id"), "each active track must have an id."
        assert trk.get("status") in {"ACTIVE", "SHIPPABLE"}, \
            f"unexpected status for {trk.get('id')!r}: {trk.get('status')!r}"
        assert trk.get("verified_at"), f"{trk.get('id')!r} must have verified_at."
    lane_policy = track.get("parallel_lane_policy")
    assert lane_policy, "ACTIVE_TRACK.yaml must declare the parallel lane policy."
    assert lane_policy.get("allowed") is True
    assert "strategic active track" in lane_policy.get("model", "")


def test_check_track_status_runs() -> None:
    """The checker runs to completion and writes evidence JSON."""
    result = _run(CHECK_SCRIPT, "--warn-only")
    assert result.returncode == 0, result.stderr
    assert EVIDENCE.exists(), "evidence JSON must be written"
    payload = json.loads(EVIDENCE.read_text())
    # Back-compat alias = primary track id.
    assert "active_track_id" in payload
    assert payload["active_track_id"], "active_track_id alias must be the primary track id"
    # New per-track array (schema v2).
    assert isinstance(payload.get("active_tracks"), list)
    assert 1 <= len(payload["active_tracks"]) <= 10
    for tr in payload["active_tracks"]:
        assert "id" in tr
        assert "shippable" in tr
        assert "prerequisites_ok" in tr
        assert "completion_progress" in tr
        assert isinstance(tr.get("criteria"), list)
    # The alias must match one of the per-track ids (the primary).
    assert payload["active_track_id"] in {tr["id"] for tr in payload["active_tracks"]}
    assert payload.get("coordination_model", {}).get("allowed") is True
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


def test_onboard_command_succeeds() -> None:
    """agent_onboard.py runs end-to-end and prints the active track section."""
    result = _run(ONBOARD_SCRIPT)
    # Return code may be 1 if prereqs fail; that's a real signal, not a test failure.
    # We just check the command produced the structural sections.
    assert "ACTIVE TRACK" in result.stdout
    assert "LIVING AXIOMS" in result.stdout
    assert "WHAT TO DO NEXT" in result.stdout
