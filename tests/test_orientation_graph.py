"""Tests for scripts/governance/orientation_graph.py — read-only projection."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/orientation_graph.py"

spec = importlib.util.spec_from_file_location("orientation_graph", SCRIPT)
og = importlib.util.module_from_spec(spec)
sys.modules["orientation_graph"] = og
spec.loader.exec_module(og)


def _copy_tracked_checkout(destination: Path) -> None:
    """Create a genuine clean Git checkout of the current implementation."""
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(REPO_ROOT), str(destination)],
        check=True,
        timeout=120,
    )
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    for raw_relative in listed.split(b"\0"):
        if not raw_relative:
            continue
        relative = os.fsdecode(raw_relative)
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists() and not source.is_symlink():
            target.unlink(missing_ok=True)
        elif source.is_symlink():
            target.unlink(missing_ok=True)
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
    subprocess.run(
        ["git", "-C", str(destination), "add", "-A"],
        check=True,
        timeout=60,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "-c",
            "user.name=Orientation Graph Test",
            "-c",
            "user.email=wp-o4-test@example.invalid",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "snapshot implementation under test",
        ],
        check=True,
        timeout=60,
    )
    assert not subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=destination,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout


def _tree_snapshot(root: Path) -> dict[str, tuple[object, ...]]:
    """Snapshot content, including ignored files that Git status can conceal."""
    snapshot: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            snapshot[relative] = ("symlink", os.readlink(path))
        elif path.is_file():
            snapshot[relative] = (
                "file",
                path.stat().st_mode,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return snapshot


def _clean_subprocess_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    # Prove the script's own boundary rather than inheriting the closeout
    # harness's bytecode protection.
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    env["HOME"] = str(tmp_path / "home")
    env["XDG_CACHE_HOME"] = str(tmp_path / "xdg-cache")
    return env


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


def _write_census_receipt(
    path: Path,
    *,
    generated_at: str,
    status: str = "live",
) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "surfaces": [
                    {
                        "id": "agent.example",
                        "label": "Example agent",
                        "status": status,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _current_probe(observation: str) -> dict[str, object]:
    return {
        "generated_at": "2026-08-13T12:00:00Z",
        "surfaces": [
            {
                "id": "agent.example",
                "label": "Example agent",
                "status": observation,
                "observation": observation,
                "process_observation": (
                    "positive"
                    if observation == "live"
                    else "negative"
                    if observation == "stopped"
                    else "unavailable"
                ),
                "port_observation": "not_applicable",
            }
        ],
    }


def test_liveness_stale_saved_live_is_not_promoted(monkeypatch, tmp_path: Path):
    receipt = tmp_path / "live_process_census.json"
    _write_census_receipt(
        receipt,
        generated_at="2026-08-13T09:59:59Z",
        status="live",
    )
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)
    monkeypatch.setattr(og, "_current_liveness_payload", lambda: _current_probe("unknown"))

    result = og.build_liveness(now=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc))

    assert result.receipt_freshness == "stale"
    assert result.receipt_age_seconds == 7201.0
    assert result.surfaces == [
        {
            "id": "agent.example",
            "label": "Example agent",
            "status": "stale",
            "receipt_status": "live",
            "observation": "unknown",
            "process_observation": "unavailable",
            "port_observation": "not_applicable",
        }
    ]


def test_liveness_fresh_positive_probe_reports_live(monkeypatch, tmp_path: Path):
    receipt = tmp_path / "live_process_census.json"
    _write_census_receipt(
        receipt,
        generated_at="2026-08-13T11:59:00Z",
        status="stopped",
    )
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)
    monkeypatch.setattr(og, "_current_liveness_payload", lambda: _current_probe("live"))

    result = og.build_liveness(now=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc))

    assert result.receipt_freshness == "fresh"
    assert result.observed_at == "2026-08-13T12:00:00Z"
    assert result.surfaces[0]["status"] == "live"
    assert result.surfaces[0]["receipt_status"] == "stopped"


def test_liveness_current_negative_probe_reports_stopped(monkeypatch, tmp_path: Path):
    receipt = tmp_path / "live_process_census.json"
    _write_census_receipt(
        receipt,
        generated_at="2026-08-13T11:59:00Z",
        status="live",
    )
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)
    monkeypatch.setattr(og, "_current_liveness_payload", lambda: _current_probe("stopped"))

    result = og.build_liveness(now=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc))

    assert result.surfaces[0]["status"] == "stopped"
    assert result.surfaces[0]["receipt_status"] == "live"


def test_liveness_unknown_probe_never_inherits_fresh_saved_live(
    monkeypatch,
    tmp_path: Path,
):
    receipt = tmp_path / "live_process_census.json"
    _write_census_receipt(
        receipt,
        generated_at="2026-08-13T10:00:00Z",
        status="live",
    )
    monkeypatch.setattr(og, "_census_receipt_path", lambda: receipt)
    monkeypatch.setattr(og, "_current_liveness_payload", lambda: _current_probe("unknown"))

    result = og.build_liveness(now=datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc))

    assert result.receipt_age_seconds == og.CENSUS_RECEIPT_FRESH_AFTER_SECONDS
    assert result.receipt_freshness == "fresh"
    assert result.surfaces[0]["status"] == "unknown"
    assert result.surfaces[0]["receipt_status"] == "live"


def test_orientation_graph_render_is_read_only(tmp_path):
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    before = _tree_snapshot(checkout)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/orientation_graph.py",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=180,
        env=_clean_subprocess_env(tmp_path),
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert _tree_snapshot(checkout) == before, (
        "orientation graph must not create ignored bytecode/cache files or "
        "change tracked owner files on its first import"
    )


def test_explicit_context_refresh_writes_only_two_paths(tmp_path):
    """O4-B1b: a fresh process changes exactly the two owner artifacts."""
    checkout = tmp_path / "clean-checkout"
    _copy_tracked_checkout(checkout)
    expected = {
        "reports/orientation/repo_context.json",
        "reports/orientation/repo_context.md",
    }
    for relative in expected:
        (checkout / relative).unlink()
    subprocess.run(
        ["git", "-C", str(checkout), "add", "-A"],
        check=True,
        timeout=30,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(checkout),
            "-c",
            "user.name=Orientation Graph Test",
            "-c",
            "user.email=wp-o4-test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "remove generated context before refresh",
        ],
        check=True,
        timeout=30,
    )
    before = _tree_snapshot(checkout)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/orientation_graph.py",
            "--write-context",
        ],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=180,
        env=_clean_subprocess_env(tmp_path),
    )
    assert result.returncode == 0, result.stderr[-2000:]

    after = _tree_snapshot(checkout)
    changed = {
        relative
        for relative in set(before) | set(after)
        if before.get(relative) != after.get(relative)
    }
    assert changed == expected
    assert not any(
        relative.endswith(".pyc") or "__pycache__" in relative.split("/")
        for relative in after
    ), "explicit refresh created repository bytecode/cache files"


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


def test_normalize_context_path_redacts_absolute_paths():
    home_based = str(Path.home() / ".dharma/a2a_bus")
    assert og._normalize_context_path(home_based).startswith("~/")

    repo_based = str(og.REPO_ROOT / "reports/orientation/nats_e2e_receipt.json")
    assert og._normalize_context_path(repo_based).startswith("$REPO_ROOT/")

    assert og._normalize_context_path("/opt/private/location") == "<absolute-path>"


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


def test_measure_cli_writes_receipt(tmp_path: Path):
    state_dir = tmp_path / "state"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--measure"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "DHARMA_STATE_DIR": str(state_dir)},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["event"] == "orientation_timing"
    assert payload["meets_target"] is True
    assert (state_dir / "ops/orientation_timing_receipt.json").exists()
