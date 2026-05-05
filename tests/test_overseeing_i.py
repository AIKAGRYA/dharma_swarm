"""Tests for dharma_swarm.overseeing_i — meta-level wholistic intelligence.

Validates:
- Assessment dataclass defaults and field population
- OverseeingI._synthesize: situation, gaps, and next_move logic
- print_assessment: formatted output
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from dharma_swarm.overseeing_i import Assessment, OverseeingI


# ---------------------------------------------------------------------------
# Assessment dataclass
# ---------------------------------------------------------------------------


class TestAssessment:
    def test_defaults(self):
        a = Assessment()
        assert a.timestamp == ""
        assert a.concept_count == 0
        assert a.bridge_count == 0
        assert a.conviction == 0.0
        assert a.alive == []
        assert a.stalled == []
        assert a.gaps == []
        assert a.next_move == ""

    def test_with_data(self):
        a = Assessment(
            timestamp="2026-05-01T00:00:00Z",
            concept_count=42,
            bridge_count=500,
            objective_count=5,
            stigmergy_density=12,
            alive=["semantic(100)", "telos(5 active)"],
            stalled=["bridge(empty)"],
        )
        assert a.concept_count == 42
        assert len(a.alive) == 2


# ---------------------------------------------------------------------------
# OverseeingI._synthesize
# ---------------------------------------------------------------------------


class TestSynthesize:
    def test_situation_text(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            alive=["semantic(50)", "telos(3 active)"],
            stalled=["bridge(empty)"],
            bridge_count=100,
            objective_count=5,
            stigmergy_density=8,
        )
        oi._synthesize(a)
        assert "2 alive" in a.situation
        assert "1 stalled" in a.situation
        assert "100 bridge" in a.situation

    def test_no_bridges_gap(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(bridge_count=0)
        oi._synthesize(a)
        assert any("bridge" in g.lower() for g in a.gaps)
        assert "bridge discovery" in a.next_move.lower()
        assert a.conviction == 0.95

    def test_no_objectives_gap(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(bridge_count=10, objective_count=0)
        oi._synthesize(a)
        assert any("telos" in g.lower() for g in a.gaps)
        assert a.conviction == 0.9

    def test_no_stigmergy_gap(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(bridge_count=10, objective_count=5, stigmergy_density=0)
        oi._synthesize(a)
        assert any("stigmergy" in g.lower() for g in a.gaps)

    def test_no_traces_gap(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(bridge_count=10, objective_count=5, stigmergy_density=3, agent_traces=0)
        oi._synthesize(a)
        assert any("traces" in g.lower() for g in a.gaps)

    def test_healthy_system(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            bridge_count=500,
            objective_count=5,
            stigmergy_density=20,
            agent_traces=10,
        )
        oi._synthesize(a)
        assert a.conviction == 0.6
        assert "healthy" in a.next_move.lower()

    def test_many_gaps_addresses_first(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            bridge_count=0,
            objective_count=0,
            stigmergy_density=0,
            agent_traces=0,
        )
        oi._synthesize(a)
        assert len(a.gaps) >= 4
        # bridge_count=0 triggers the highest priority next_move
        assert a.conviction == 0.95

    def test_blast_radius_drives_next_move(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            bridge_count=50,
            objective_count=3,
            stigmergy_density=5,
            agent_traces=5,
            blast_radius_top5=[
                {"concept": "autopoiesis", "impact": 42, "files": 10, "concepts": 8, "objectives": 2},
            ],
        )
        oi._synthesize(a)
        assert "autopoiesis" in a.next_move

    def test_cross_pillar_missing_detected(self, tmp_path):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            bridge_count=50,
            objective_count=3,
            stigmergy_density=5,
            agent_traces=5,
            cross_pillar_bridges=[
                {"a": "P01 Levin", "b": "P02 Kauffman", "count": 5},
            ],
        )
        oi._synthesize(a)
        # Should detect missing pillars
        assert any("Unconnected" in g for g in a.gaps)


# ---------------------------------------------------------------------------
# print_assessment (smoke test)
# ---------------------------------------------------------------------------


class TestPrintAssessment:
    def test_prints_without_error(self, tmp_path, capsys):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            timestamp="2026-05-01T00:00:00Z",
            alive=["semantic(50)"],
            stalled=["bridge(empty)"],
            gaps=["No bridges"],
            situation="Test situation",
            next_move="Run bridge discovery",
            conviction=0.85,
            duration_seconds=1.23,
        )
        oi.print_assessment(a)
        captured = capsys.readouterr()
        assert "OVERSEEING I" in captured.out
        assert "Test situation" in captured.out
        assert "semantic(50)" in captured.out

    def test_with_telos_objectives(self, tmp_path, capsys):
        oi = OverseeingI(state_dir=tmp_path)
        a = Assessment(
            timestamp="2026-05-01T00:00:00Z",
            situation="OK",
            next_move="Nothing",
            conviction=0.5,
            duration_seconds=0.5,
            telos_objectives=[
                {"name": "Gnani MVP", "status": "active", "progress": 0.15, "priority": 9},
            ],
        )
        oi.print_assessment(a)
        captured = capsys.readouterr()
        assert "Gnani MVP" in captured.out
