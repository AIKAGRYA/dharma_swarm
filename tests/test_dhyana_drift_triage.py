"""Tests for Dhyana drift triage — ranking DEGRADED zones by priority."""

from __future__ import annotations

from dataclasses import dataclass

from dharma_swarm.dhyana.drift_triage import (
    DriftTriageEntry,
    triage_drifted_zones,
    _estimate_blast_radius,
    _estimate_semantic_centrality,
    _match_broken_register,
)


@dataclass
class FakeRow:
    """Mimics a control surface row for testing."""

    id: str = "row_001"
    label: str = "test_entity"
    coherence_state: str = "drifted"
    kind: str = "module"
    owner_module: str = "dharma_swarm/some_module.py"
    declared_state: str = "active"
    observed_state: str = "partial"
    next_action: str = "Investigate"


class TestDriftTriageEntry:
    def test_priority_score_computed(self) -> None:
        entry = DriftTriageEntry(
            row_id="r1",
            label="test",
            coherence_state="drifted",
            kind="module",
            owner_module="",
            declared_state="active",
            observed_state="partial",
            blast_radius=3.0,
            age_days=7.0,
            semantic_centrality=2.0,
        )
        assert entry.priority_score == 42.0  # 3.0 * 7.0 * 2.0

    def test_priority_score_explicit_overrides(self) -> None:
        entry = DriftTriageEntry(
            row_id="r1",
            label="test",
            coherence_state="drifted",
            kind="module",
            owner_module="",
            declared_state="",
            observed_state="",
            blast_radius=1.0,
            age_days=1.0,
            semantic_centrality=1.0,
            priority_score=99.0,
        )
        assert entry.priority_score == 99.0


class TestBlastRadiusEstimation:
    def test_operator_core_high(self) -> None:
        row = FakeRow(owner_module="dharma_swarm/operator_core/control_surface.py")
        assert _estimate_blast_radius(row) == 3.0

    def test_board_high(self) -> None:
        row = FakeRow(owner_module="dharma_swarm/board/facade.py")
        assert _estimate_blast_radius(row) == 3.0

    def test_leaf_module_low(self) -> None:
        row = FakeRow(owner_module="dharma_swarm/sleep_time_agent.py")
        assert _estimate_blast_radius(row) == 1.5

    def test_unknown_module(self) -> None:
        row = FakeRow(owner_module="scripts/something.py")
        assert _estimate_blast_radius(row) == 1.0


class TestSemanticCentrality:
    def test_control_surface_high(self) -> None:
        row = FakeRow(label="control_surface_projector")
        assert _estimate_semantic_centrality(row) == 2.0

    def test_organism_high(self) -> None:
        row = FakeRow(label="organism_lifecycle")
        assert _estimate_semantic_centrality(row) == 2.0

    def test_agent_medium(self) -> None:
        row = FakeRow(label="agent_pool_manager")
        assert _estimate_semantic_centrality(row) == 1.5

    def test_leaf_entity_low(self) -> None:
        row = FakeRow(label="sleep_timer_config")
        assert _estimate_semantic_centrality(row) == 1.0


class TestBrokenRegisterMatching:
    def test_evolution_matches_br003(self) -> None:
        assert "BR-003" in _match_broken_register("DarwinEngine evolution gate")

    def test_cron_matches_br004(self) -> None:
        assert "BR-004" in _match_broken_register("cron_runner scheduler")

    def test_algedonic_matches_br005(self) -> None:
        assert "BR-005" in _match_broken_register("algedonic_activation")

    def test_no_match(self) -> None:
        assert _match_broken_register("sleep_timer") == []


class TestTriageDriftedZones:
    def test_filters_non_degraded(self) -> None:
        rows = [
            FakeRow(coherence_state="bound"),
            FakeRow(coherence_state="drifted", label="a"),
            FakeRow(coherence_state="unknown"),
            FakeRow(coherence_state="declared_only", label="b"),
        ]
        entries = triage_drifted_zones(rows)
        assert len(entries) == 2
        labels = [e.label for e in entries]
        assert "a" in labels
        assert "b" in labels

    def test_sorted_by_priority(self) -> None:
        rows = [
            FakeRow(
                id="r1",
                label="leaf_thing",
                coherence_state="drifted",
                owner_module="scripts/foo.py",
            ),
            FakeRow(
                id="r2",
                label="control_surface_core",
                coherence_state="drifted",
                owner_module="dharma_swarm/operator_core/cs.py",
            ),
        ]
        entries = triage_drifted_zones(rows)
        # r2 should be first (higher blast_radius * centrality)
        assert entries[0].row_id == "r2"
        assert entries[0].priority_score > entries[1].priority_score

    def test_empty_rows(self) -> None:
        entries = triage_drifted_zones([])
        assert entries == []

    def test_all_bound_returns_empty(self) -> None:
        rows = [FakeRow(coherence_state="bound") for _ in range(5)]
        entries = triage_drifted_zones(rows)
        assert entries == []
