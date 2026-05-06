from __future__ import annotations

from pathlib import Path


def test_interface_mismatch_narrative_defers_to_machine_registry() -> None:
    doc = Path("INTERFACE_MISMATCH_MAP.md").read_text(encoding="utf-8")

    assert "Current Branch Overlay" in doc
    assert "docs/interface_mismatches.yaml" in doc
    assert "MISMATCH-01" in doc
    assert "MISMATCH-02" in doc
    assert "MISMATCH-03" in doc
    assert "should not" in doc
    assert "override the machine registry" in doc


def test_cybernetic_loop_map_declares_current_proof_level() -> None:
    doc = Path("CYBERNETIC_LOOP_MAP.md").read_text(encoding="utf-8")

    assert "Current Branch Overlay" in doc
    assert "tests/test_bootstrap_loops.py" in doc
    assert "not the same as a live workload" in doc


def test_model_routing_map_names_current_bypass_inventory() -> None:
    doc = Path("MODEL_ROUTING_MAP.md").read_text(encoding="utf-8")

    assert "Current Branch Overlay" in doc
    assert "tests/test_routing_surface_inventory.py" in doc
    assert "AutonomousAgent" in doc
    assert "dashboard chat" in doc
