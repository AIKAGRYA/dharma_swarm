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
    assert set(data) == {
        "identity",
        "organs",
        "tracks",
        "custody",
        "liveness",
        "broken",
        "loop1",
        "lanes",
        "agents",
        "receipts_tail",
        "a2a_bus",
        "body",
        "context_hash",
    }


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
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0
    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    assert before == after, "orientation graph must not write owner files"


def test_json_mode_is_machine_parseable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "identity" in payload and "organs" in payload


# ── Graph-shaped query tests ──────────────────────────────────────────


def test_build_graph_has_typed_nodes_and_edges():
    packet = og.build_packet()
    graph = og.build_graph(packet)
    kinds = {n.kind for n in graph.nodes}
    assert "track" in kinds
    assert "surface" in kinds
    assert len(graph.edges) > 0
    relations = {e.relation for e in graph.edges}
    assert "serves" in relations
    assert "owns_surface" in relations


def test_graph_tracks_carry_complement_edges():
    packet = og.build_packet()
    graph = og.build_graph(packet)
    complement_edges = [e for e in graph.edges if e.relation == "complements"]
    assert complement_edges, "active tracks declare complement edges"


def test_query_subgraph_returns_reachable_nodes():
    packet = og.build_packet()
    graph = og.build_graph(packet)
    track_nodes = [n for n in graph.nodes if n.kind == "track"]
    assert track_nodes, "need at least one track"
    sub = og.query_subgraph(graph, track_nodes[0].id)
    assert len(sub.nodes) >= 1
    sub_ids = {n.id for n in sub.nodes}
    assert track_nodes[0].id in sub_ids


def test_query_neighbors_filters_by_relation():
    packet = og.build_packet()
    graph = og.build_graph(packet)
    track_nodes = [n for n in graph.nodes if n.kind == "track"]
    assert track_nodes
    surfaces = og.query_neighbors(graph, track_nodes[0].id, relation="owns_surface")
    for edge, node in surfaces:
        assert edge.relation == "owns_surface"
        assert node.kind == "surface"


def test_surface_liveness_probes_are_populated():
    packet = og.build_packet()
    graph = og.build_graph(packet)
    assert graph.surface_liveness, "should have at least one surface probe"
    live = [sl for sl in graph.surface_liveness if sl.exists]
    assert live, "at least some surfaces should be live in the worktree"


def test_graph_json_mode_is_machine_parseable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--graph-json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "nodes" in payload and "edges" in payload
    assert "surface_liveness" in payload


def test_graph_mode_is_read_only(tmp_path):
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--graph"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    assert before == after, "graph mode must not write owner files"


# ── Time-to-orientation tests ─────────────────────────────────────────


def test_measure_orientation_under_target():
    receipt = og.measure_orientation(write_receipt=False)
    assert receipt["meets_target"], (
        f"orientation took {receipt['total_s']}s, target is {receipt['target_s']}s"
    )
    assert receipt["total_s"] < receipt["target_s"]
    assert receipt["node_count"] > 0
    assert receipt["edge_count"] > 0


def test_measure_cli_writes_receipt():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--measure"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["event"] == "orientation_timing"
    assert payload["meets_target"] is True
