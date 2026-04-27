"""Tests for the MCP tool registry + palace renderer with real atoms."""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.palace import (
    PILLAR_ROOMS,
    palace_summary,
    render_palace,
)
from dharma_swarm.chetana.promote import promote


def test_palace_renders_with_real_atoms(chetana_sandbox: Path, tmp_path: Path):
    # Seed a couple of atoms with pillar-affinity tags.
    for title, body, tags in [
        (
            "Strange Loops Atom",
            "Hofstadter introduces tangled hierarchies as the foundation of self-reference.",
            ["hofstadter", "consciousness"],
        ),
        (
            "Active Inference Atom",
            "Friston's free energy principle drives perception and action via prediction error.",
            ["friston", "active-inference"],
        ),
        (
            "Untagged drift atom",
            "Body has no special tags so should land in the operations room.",
            [],
        ),
    ]:
        ing = ingest(
            source=body, source_kind="note", title=title, confidence=0.6, tags=tags
        )
        promote(staged_path=ing.atoms[0], promoted_by="palace_test")

    out_path, snap = render_palace(out_path=tmp_path / "palace.canvas")
    assert out_path.exists()
    assert "hofstadter" in snap.coverage
    assert "friston" in snap.coverage
    # Total atoms placed should equal the 3 we promoted
    assert sum(v for k, v in snap.coverage.items()) == 3


def test_palace_summary_lists_all_rooms(chetana_sandbox: Path):
    _, snap = render_palace()
    text = palace_summary(snap)
    assert "Memory palace" in text
    # All 15 pillar/system rooms should appear, even at 0 atoms
    for room_meta in PILLAR_ROOMS.values():
        assert room_meta["label"] in text


def test_mcp_tool_registry_completeness():
    """Every documented MCP tool must be registered in the TOOL_REGISTRY."""
    from dharma_swarm.chetana.mcp_server import TOOL_REGISTRY

    expected = {
        "chetana_ingest",
        "chetana_promote",
        "chetana_query",
        "chetana_gap_scan",
        "chetana_decay_check",
        "chetana_palace_state",
    }
    assert set(TOOL_REGISTRY.keys()) == expected


def test_mcp_tool_ingest_actually_calls_ingest(chetana_sandbox: Path):
    from dharma_swarm.chetana.mcp_server import tool_ingest

    result = tool_ingest(
        source_text="MCP-driven ingest test", source_kind="note", title="MCP atom"
    )
    assert result["staged_count"] == 1
    assert len(result["atoms"]) == 1


def test_mcp_tool_decay_check_against_empty_corpus(chetana_sandbox: Path):
    from dharma_swarm.chetana.mcp_server import tool_decay_check

    result = tool_decay_check()
    assert result["scanned"] >= 0
    assert "stale_count" in result
    assert "stale_atoms" in result


def test_mcp_tool_palace_state_renders(chetana_sandbox: Path):
    from dharma_swarm.chetana.mcp_server import tool_palace_state

    result = tool_palace_state()
    assert "canvas_path" in result
    assert "coverage" in result
    assert Path(result["canvas_path"]).exists()
