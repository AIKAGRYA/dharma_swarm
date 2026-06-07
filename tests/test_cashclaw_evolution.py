"""Tests for CashClaw Evolution Engine — variant management and fitness tracking."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dharma_swarm.revenue.cashclaw_evolution import (
    CashClawEvolutionDB,
    CycleResult,
    FitnessScore,
    Variant,
    _short_hash,
)


@pytest.fixture
def db(tmp_path: Path) -> CashClawEvolutionDB:
    return CashClawEvolutionDB(db_path=tmp_path / "test_evolution.db")


def _make_variant(vid: str = "v0-test-abcd1234", **kw) -> Variant:
    defaults = dict(variant_id=vid, generation=0)
    defaults.update(kw)
    return Variant(**defaults)


def _make_result(rid: str = "r1", vid: str = "v0-test-abcd1234", **kw) -> CycleResult:
    defaults = dict(result_id=rid, variant_id=vid)
    defaults.update(kw)
    return CycleResult(**defaults)


class TestVariant:
    def test_default_weights(self):
        v = Variant(variant_id="test")
        assert v.cash_speed_weight == 20
        assert v.min_score_threshold == 75
        assert v.source_query_bias == "broad"

    def test_custom_weights(self):
        v = Variant(variant_id="test", cash_speed_weight=35, min_score_threshold=90)
        assert v.cash_speed_weight == 35
        assert v.min_score_threshold == 90


class TestEvolutionDB:
    def test_upsert_and_get_variant(self, db: CashClawEvolutionDB):
        v = _make_variant()
        db.upsert_variant(v)
        active = db.get_active_variants()
        assert len(active) == 1
        assert active[0].variant_id == "v0-test-abcd1234"

    def test_deactivate_variant(self, db: CashClawEvolutionDB):
        v = _make_variant()
        db.upsert_variant(v)
        v.active = False
        db.upsert_variant(v)
        assert db.get_active_variants() == []

    def test_record_result_and_fitness(self, db: CashClawEvolutionDB):
        v = _make_variant()
        db.upsert_variant(v)
        db.record_result(_make_result(opportunities_found=15, avg_score=82.5, revenue_earned_cents=50000))
        db.record_result(_make_result(rid="r2", opportunities_found=10, avg_score=78.0, revenue_earned_cents=30000, opportunities_submitted=2))
        f = db.get_fitness("v0-test-abcd1234")
        assert f.total_cycles == 2
        assert f.total_revenue_cents == 80000
        assert f.total_opportunities_found == 25
        assert f.total_opportunities_submitted == 2
        assert f.avg_score_per_cycle == pytest.approx(80.25, abs=0.1)

    def test_fitness_zero_cycles(self, db: CashClawEvolutionDB):
        f = db.get_fitness("nonexistent")
        assert f.total_cycles == 0
        assert f.fitness == 0.0

    def test_leaderboard(self, db: CashClawEvolutionDB):
        v1 = _make_variant("v1")
        v2 = _make_variant("v2")
        db.upsert_variant(v1)
        db.upsert_variant(v2)
        db.record_result(_make_result("r1", "v1", revenue_earned_cents=100000, opportunities_found=20, opportunities_submitted=5, avg_score=90.0))
        db.record_result(_make_result("r2", "v2", revenue_earned_cents=10000, opportunities_found=5, opportunities_submitted=0, avg_score=60.0))
        lb = db.get_leaderboard(limit=5)
        assert len(lb) == 2
        assert lb[0]["variant_id"] == "v1"
        assert lb[0]["fitness"] > lb[1]["fitness"]

    def test_seed_initial_variants(self, db: CashClawEvolutionDB):
        variants = db.seed_initial_variants()
        assert len(variants) == 6
        assert all(v.generation == 0 for v in variants)
        biases = {v.source_query_bias for v in variants}
        assert len(biases) == 6

    def test_seed_idempotent(self, db: CashClawEvolutionDB):
        v1 = db.seed_initial_variants()
        v2 = db.seed_initial_variants()
        assert len(v1) == len(v2)


class TestCycleResult:
    def test_defaults(self):
        r = CycleResult(result_id="test", variant_id="v0")
        assert r.opportunities_found == 0
        assert r.revenue_earned_cents == 0

    def test_serialization(self):
        r = _make_result(opportunities_found=42)
        data = r.model_dump()
        assert data["opportunities_found"] == 42
