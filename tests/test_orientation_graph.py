"""Tests for scripts/governance/orientation_graph.py — read-only projection."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/orientation_graph.py"

spec = importlib.util.spec_from_file_location("orientation_graph", SCRIPT)
og = importlib.util.module_from_spec(spec)
sys.modules["orientation_graph"] = og
spec.loader.exec_module(og)


def test_packet_has_all_axes():
    packet = og.build_packet()
    data = og.asdict(packet)
    assert set(data) == {"identity", "organs", "tracks", "custody",
                         "liveness", "broken", "loop_closure"}


def test_loop_closure_axis_reads_committed_report(tmp_path):
    report = {
        "provider": "ollama",
        "tasks_requested": 2,
        "tasks_completed": 2,
        "dispatch_dropoffs": 0,
        "evidence_receipts": {"r1": "ok", "r2": "ok"},
    }
    run_dir = tmp_path / "2026-06-11"
    run_dir.mkdir()
    (run_dir / "loop1_closure_run.json").write_text(json.dumps(report))
    original = og.LOOP_CLOSURE_DIR
    og.LOOP_CLOSURE_DIR = tmp_path
    try:
        closure = og.build_loop_closure()
    finally:
        og.LOOP_CLOSURE_DIR = original
    assert closure is not None
    assert closure.closed
    assert closure.tasks_completed == 2
    assert closure.evidence_receipts == 2


def test_identity_serves_the_one_line():
    identity = og.build_identity()
    assert "dharma_swarm" in identity.one_line
    assert "foundations/THE_ORGANISM.md" in identity.read_first
    assert "docs/vision_maps/NORTH_STAR.md" in identity.read_first


def test_organs_project_from_portfolio_owner():
    organs = og.build_organs()
    assert organs, "portfolio owner should yield at least one organ"
    ids = {o.id for o in organs}
    assert "darshan-publication" in ids


def test_tracks_project_from_active_track_owner():
    tracks = og.build_tracks()
    assert tracks, "ACTIVE_TRACK.yaml should yield at least one active track"
    assert all(t.serves for t in tracks)


def test_custody_counts_registered_canon():
    custody = og.build_custody()
    assert custody.registered_total > 0
    assert custody.present + len(custody.missing) == custody.registered_total


def test_orientation_graph_render_is_read_only(tmp_path):
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True).stdout
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert result.returncode == 0
    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True).stdout
    assert before == after, "orientation graph must not write owner files"


def test_json_mode_is_machine_parseable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"], cwd=REPO_ROOT,
        capture_output=True, text=True)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "identity" in payload and "organs" in payload
