from __future__ import annotations

from pathlib import Path

from scripts.uplift_guards.mismatch_registry import load_mismatch_registry


def test_bootstrap_mismatches_are_no_longer_open_blockers() -> None:
    registry = load_mismatch_registry(Path("."))
    by_id = {entry.id: entry for entry in registry.entries}

    assert by_id["MISMATCH-01"].status == "resolved"
    assert by_id["MISMATCH-02"].status == "resolved"
    assert by_id["MISMATCH-03"].status == "resolved"
    assert registry.open_blockers() == []


def test_machine_registry_matches_current_loop1_code_truth() -> None:
    orchestrate_live = Path("dharma_swarm/orchestrate_live.py").read_text(encoding="utf-8")
    auto_proposer = Path("dharma_swarm/auto_proposer.py").read_text(encoding="utf-8")

    assert "role=AgentRole(outcome.child_spec.get" in orchestrate_live
    assert "provider_type=PT(outcome.child_spec.get" in orchestrate_live
    assert 'consume_events("AGENT_FITNESS"' in orchestrate_live
    assert '"AGENT_LIFECYCLE_COMPLETED", limit=20' in orchestrate_live
    assert "if self._stigmergy is None:" in auto_proposer
