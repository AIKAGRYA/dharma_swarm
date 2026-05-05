"""Tests for dharma_swarm.diversity_archive — MAP-Elites quality-diversity archive.

Validates:
- BehaviorDescriptor validation
- DiversityArchive bin computation, add/replace, diversity-aware sampling
- Coverage and stats queries
- best_per_dimension fallback logic
- Serialization round-trip (to_dict / from_dict)
- Async persistence (persist / load)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from dharma_swarm.diversity_archive import (
    ArchiveCell,
    BehaviorDescriptor,
    DiversityArchive,
)


# ---------------------------------------------------------------------------
# BehaviorDescriptor
# ---------------------------------------------------------------------------


class TestBehaviorDescriptor:
    def test_validate_dimensions_all_present_and_in_range(self):
        bd = BehaviorDescriptor(dimensions={"speed": 0.5, "risk": 0.0, "cost": 1.0})
        assert bd.validate_dimensions(["speed", "risk", "cost"]) is True

    def test_validate_dimensions_missing_key(self):
        bd = BehaviorDescriptor(dimensions={"speed": 0.5})
        assert bd.validate_dimensions(["speed", "risk"]) is False

    def test_validate_dimensions_out_of_range(self):
        bd = BehaviorDescriptor(dimensions={"speed": 1.5})
        assert bd.validate_dimensions(["speed"]) is False

    def test_validate_dimensions_negative(self):
        bd = BehaviorDescriptor(dimensions={"speed": -0.1})
        assert bd.validate_dimensions(["speed"]) is False

    def test_validate_dimensions_empty_expected(self):
        bd = BehaviorDescriptor(dimensions={"speed": 0.5})
        assert bd.validate_dimensions([]) is True

    def test_validate_dimensions_boundary_values(self):
        bd = BehaviorDescriptor(dimensions={"a": 0.0, "b": 1.0})
        assert bd.validate_dimensions(["a", "b"]) is True


# ---------------------------------------------------------------------------
# DiversityArchive — init and validation
# ---------------------------------------------------------------------------


class TestDiversityArchiveInit:
    def test_requires_at_least_one_dimension(self):
        with pytest.raises(ValueError, match="At least one"):
            DiversityArchive(dimensions=[])

    def test_bins_per_dimension_minimum_two(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=1)
        assert archive.bins_per_dimension == 2

    def test_default_persist_path(self):
        archive = DiversityArchive(dimensions=["x"])
        assert "diversity_archive.json" in str(archive.persist_path)

    def test_custom_persist_path(self, tmp_path):
        p = tmp_path / "custom.json"
        archive = DiversityArchive(dimensions=["x"], persist_path=p)
        assert archive.persist_path == p


# ---------------------------------------------------------------------------
# Bin computation
# ---------------------------------------------------------------------------


class TestBinComputation:
    def test_to_bin_boundaries(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        assert archive._to_bin(0.0) == 0
        assert archive._to_bin(1.0) == 4  # clamped to max bin
        assert archive._to_bin(0.5) == 2

    def test_to_bin_clamps_negative(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        assert archive._to_bin(-0.5) == 0

    def test_to_bin_clamps_above_one(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        assert archive._to_bin(1.5) == 4

    def test_descriptor_to_key_multi_dim(self):
        archive = DiversityArchive(dimensions=["a", "b"], bins_per_dimension=4)
        bd = BehaviorDescriptor(dimensions={"a": 0.0, "b": 1.0})
        key = archive._descriptor_to_key(bd)
        assert key == (0, 3)

    def test_descriptor_to_key_missing_dim_defaults_zero(self):
        archive = DiversityArchive(dimensions=["a", "b"], bins_per_dimension=4)
        bd = BehaviorDescriptor(dimensions={"a": 0.5})
        key = archive._descriptor_to_key(bd)
        assert key[1] == 0  # missing "b" defaults to 0.0 → bin 0


# ---------------------------------------------------------------------------
# Add / replace logic
# ---------------------------------------------------------------------------


class TestAddReplace:
    def test_add_to_empty_cell(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        bd = BehaviorDescriptor(dimensions={"x": 0.3})
        inserted = archive.add("c1", {"data": "hello"}, 0.8, bd, generation=1)
        assert inserted is True
        cell = archive.get_cell(bd)
        assert cell is not None
        assert cell.candidate_id == "c1"
        assert cell.fitness == 0.8
        assert cell.generation == 1

    def test_replace_with_higher_fitness(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        bd = BehaviorDescriptor(dimensions={"x": 0.3})
        archive.add("c1", {}, 0.5, bd)
        replaced = archive.add("c2", {}, 0.9, bd)
        assert replaced is True
        cell = archive.get_cell(bd)
        assert cell is not None
        assert cell.candidate_id == "c2"

    def test_no_replace_with_lower_fitness(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        bd = BehaviorDescriptor(dimensions={"x": 0.3})
        archive.add("c1", {}, 0.9, bd)
        replaced = archive.add("c2", {}, 0.5, bd)
        assert replaced is False
        cell = archive.get_cell(bd)
        assert cell is not None
        assert cell.candidate_id == "c1"

    def test_no_replace_with_equal_fitness(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        bd = BehaviorDescriptor(dimensions={"x": 0.3})
        archive.add("c1", {}, 0.7, bd)
        replaced = archive.add("c2", {}, 0.7, bd)
        assert replaced is False

    def test_different_bins_independent(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        bd1 = BehaviorDescriptor(dimensions={"x": 0.1})
        bd2 = BehaviorDescriptor(dimensions={"x": 0.9})
        archive.add("c1", {}, 0.5, bd1)
        archive.add("c2", {}, 0.5, bd2)
        assert archive.get_cell(bd1).candidate_id == "c1"
        assert archive.get_cell(bd2).candidate_id == "c2"

    def test_get_cell_returns_none_for_empty(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        bd = BehaviorDescriptor(dimensions={"x": 0.5})
        assert archive.get_cell(bd) is None


# ---------------------------------------------------------------------------
# Diversity-aware sampling
# ---------------------------------------------------------------------------


class TestDiverseSampling:
    def test_sample_empty_archive(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        assert archive.sample_diverse(3) == []

    def test_sample_more_than_available(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        bd = BehaviorDescriptor(dimensions={"x": 0.5})
        archive.add("c1", {}, 0.8, bd)
        result = archive.sample_diverse(10)
        assert len(result) == 1

    def test_sample_starts_with_fittest(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=10, seed=42)
        archive.add("low", {}, 0.2, BehaviorDescriptor(dimensions={"x": 0.1}))
        archive.add("high", {}, 0.9, BehaviorDescriptor(dimensions={"x": 0.5}))
        archive.add("mid", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.9}))
        result = archive.sample_diverse(3)
        assert result[0].candidate_id == "high"

    def test_sample_maximizes_spread(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=10, seed=42)
        archive.add("a", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.0}))
        archive.add("b", {}, 0.9, BehaviorDescriptor(dimensions={"x": 0.5}))
        archive.add("c", {}, 0.5, BehaviorDescriptor(dimensions={"x": 1.0}))
        result = archive.sample_diverse(3)
        assert len(result) == 3
        ids = {r.candidate_id for r in result}
        assert ids == {"a", "b", "c"}

    def test_sample_zero_returns_empty(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("c1", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.5}))
        assert archive.sample_diverse(0) == []


# ---------------------------------------------------------------------------
# Bin distance
# ---------------------------------------------------------------------------


class TestBinDistance:
    def test_same_point(self):
        assert DiversityArchive._bin_distance((0, 0), (0, 0)) == 0.0

    def test_unit_distance(self):
        assert DiversityArchive._bin_distance((0,), (1,)) == 1.0

    def test_euclidean_2d(self):
        dist = DiversityArchive._bin_distance((0, 0), (3, 4))
        assert math.isclose(dist, 5.0)


# ---------------------------------------------------------------------------
# Coverage and stats
# ---------------------------------------------------------------------------


class TestCoverageAndStats:
    def test_coverage_empty(self):
        archive = DiversityArchive(dimensions=["x", "y"], bins_per_dimension=3)
        assert archive.coverage() == 0.0

    def test_coverage_partial(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("c1", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.1}))
        archive.add("c2", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.9}))
        assert archive.coverage() == 2.0 / 5.0

    def test_stats_empty(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        s = archive.stats()
        assert s["occupied"] == 0
        assert s["mean_fitness"] == 0.0
        assert s["diversity_score"] == 0.0

    def test_stats_populated(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("c1", {}, 0.4, BehaviorDescriptor(dimensions={"x": 0.1}))
        archive.add("c2", {}, 0.8, BehaviorDescriptor(dimensions={"x": 0.9}))
        s = archive.stats()
        assert s["occupied"] == 2
        assert s["max_fitness"] == 0.8
        assert s["min_fitness"] == 0.4
        assert s["diversity_score"] > 0.0


# ---------------------------------------------------------------------------
# best_per_dimension
# ---------------------------------------------------------------------------


class TestBestPerDimension:
    def test_unknown_dimension_raises(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        with pytest.raises(ValueError, match="Unknown dimension"):
            archive.best_per_dimension("y")

    def test_best_at_max_bin(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("low_x", {}, 0.3, BehaviorDescriptor(dimensions={"x": 0.1}))
        archive.add("high_x", {}, 0.9, BehaviorDescriptor(dimensions={"x": 0.95}))
        best = archive.best_per_dimension("x")
        assert best is not None
        assert best.candidate_id == "high_x"

    def test_fallback_to_highest_occupied_bin(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("mid", {}, 0.7, BehaviorDescriptor(dimensions={"x": 0.5}))
        best = archive.best_per_dimension("x")
        assert best is not None
        assert best.candidate_id == "mid"

    def test_empty_archive_returns_none(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5)
        assert archive.best_per_dimension("x") is None


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_and_from_dict_round_trip(self):
        archive = DiversityArchive(
            dimensions=["speed", "risk"],
            bins_per_dimension=4,
            seed=42,
        )
        archive.add(
            "c1", {"code": "v1"}, 0.75,
            BehaviorDescriptor(dimensions={"speed": 0.3, "risk": 0.8}),
            generation=5,
        )
        archive.add(
            "c2", {"code": "v2"}, 0.6,
            BehaviorDescriptor(dimensions={"speed": 0.9, "risk": 0.1}),
            generation=7,
        )

        data = archive.to_dict()
        restored = DiversityArchive.from_dict(data, seed=42)

        assert restored.dimensions == ["speed", "risk"]
        assert restored.bins_per_dimension == 4
        assert len(restored._grid) == 2

        cell = restored.get_cell(BehaviorDescriptor(dimensions={"speed": 0.3, "risk": 0.8}))
        assert cell is not None
        assert cell.candidate_id == "c1"
        assert cell.fitness == 0.75

    def test_to_dict_empty(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=3)
        data = archive.to_dict()
        assert data["grid"] == {}

    def test_from_dict_empty_grid(self):
        data = {"dimensions": ["x"], "bins_per_dimension": 3, "grid": {}}
        archive = DiversityArchive.from_dict(data)
        assert len(archive._grid) == 0


# ---------------------------------------------------------------------------
# Async persistence
# ---------------------------------------------------------------------------


class TestAsyncPersistence:
    async def test_persist_and_load(self, tmp_path):
        path = tmp_path / "archive.json"
        archive = DiversityArchive(
            dimensions=["a", "b"],
            bins_per_dimension=3,
            persist_path=path,
            seed=42,
        )
        archive.add("c1", {"v": 1}, 0.8, BehaviorDescriptor(dimensions={"a": 0.5, "b": 0.5}))

        saved_path = await archive.persist()
        assert saved_path == path
        assert path.exists()

        loaded = await DiversityArchive.load(
            dimensions=["a", "b"],
            bins_per_dimension=3,
            persist_path=path,
            seed=42,
        )
        assert len(loaded._grid) == 1
        cell = loaded.get_cell(BehaviorDescriptor(dimensions={"a": 0.5, "b": 0.5}))
        assert cell is not None
        assert cell.candidate_id == "c1"

    async def test_load_nonexistent_creates_empty(self, tmp_path):
        path = tmp_path / "missing.json"
        archive = await DiversityArchive.load(
            dimensions=["x"],
            bins_per_dimension=5,
            persist_path=path,
        )
        assert len(archive._grid) == 0
        assert archive.persist_path == path


# ---------------------------------------------------------------------------
# Diversity score computation
# ---------------------------------------------------------------------------


class TestDiversityScore:
    def test_single_cell_returns_zero(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("c1", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.5}))
        assert archive._compute_diversity_score() == 0.0

    def test_two_distant_cells_positive(self):
        archive = DiversityArchive(dimensions=["x"], bins_per_dimension=5, seed=42)
        archive.add("c1", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.0}))
        archive.add("c2", {}, 0.5, BehaviorDescriptor(dimensions={"x": 1.0}))
        score = archive._compute_diversity_score()
        assert score > 0.0

    def test_two_adjacent_cells_lower_than_distant(self):
        archive_close = DiversityArchive(dimensions=["x"], bins_per_dimension=10, seed=42)
        archive_close.add("c1", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.0}))
        archive_close.add("c2", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.1}))

        archive_far = DiversityArchive(dimensions=["x"], bins_per_dimension=10, seed=42)
        archive_far.add("c1", {}, 0.5, BehaviorDescriptor(dimensions={"x": 0.0}))
        archive_far.add("c2", {}, 0.5, BehaviorDescriptor(dimensions={"x": 1.0}))

        assert archive_close._compute_diversity_score() < archive_far._compute_diversity_score()
