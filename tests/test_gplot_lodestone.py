"""Tests for dharma_swarm.gplot_lodestone — boot-time GPLOT seeder.

Validates:
- _GPLOT_MARKS: 5 marks, all gplot channel, high salience, correct agent
- _GPLOT_CONCEPTS: 9 concept nodes with required fields (invariance pillar)
- _GPLOT_TELOS_OBJECTIVES: 6 objectives with priority/progress
- _GPLOT_TASK_SEEDS: 5 tasks with gplot tags
- GplotLodestone construction
- seed_all returns expected result keys

Peer test to test_gnani_lodestone.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.gplot_lodestone import (
    GplotLodestone,
    _GPLOT_CONCEPTS,
    _GPLOT_MARKS,
    _GPLOT_TASK_SEEDS,
    _GPLOT_TELOS_OBJECTIVES,
)


# ---------------------------------------------------------------------------
# Static data validation — stigmergy marks
# ---------------------------------------------------------------------------


class TestGplotMarks:
    def test_count(self):
        assert len(_GPLOT_MARKS) == 5

    def test_all_gplot_channel(self):
        for mark in _GPLOT_MARKS:
            assert mark["channel"] == "gplot"

    def test_high_salience(self):
        for mark in _GPLOT_MARKS:
            assert mark["salience"] >= 0.92

    def test_agent_is_gplot_lodestone(self):
        for mark in _GPLOT_MARKS:
            assert mark["agent"] == "gplot-lodestone"

    def test_unique_ids(self):
        ids = [m["id"] for m in _GPLOT_MARKS]
        assert len(ids) == len(set(ids))

    def test_observations_substantial(self):
        for mark in _GPLOT_MARKS:
            assert len(mark["observation"]) >= 200


# ---------------------------------------------------------------------------
# Static data validation — concept nodes
# ---------------------------------------------------------------------------


class TestGplotConcepts:
    def test_count(self):
        assert len(_GPLOT_CONCEPTS) == 9

    def test_unique_ids(self):
        ids = [c["id"] for c in _GPLOT_CONCEPTS]
        assert len(ids) == len(set(ids))

    def test_required_fields(self):
        for concept in _GPLOT_CONCEPTS:
            assert "id" in concept
            assert "name" in concept
            assert "description" in concept
            assert "salience" in concept

    def test_invariance_pillar_default(self):
        for concept in _GPLOT_CONCEPTS:
            # Either explicit invariance pillar or no pillar (defaulted by seeder)
            assert concept.get("pillar", "invariance") == "invariance"

    def test_core_ids_present(self):
        ids = {c["id"] for c in _GPLOT_CONCEPTS}
        # The conceptual backbone of the GPLOT direction
        assert "invariant_observatory" in ids
        assert "persistent_homology" in ids
        assert "takens_embedding" in ids
        assert "gap_as_topological_invariant" in ids
        assert "hofstadter_spectrum" in ids
        assert "gplot_lodestone" in ids
        assert "synoptic_attractor_candidate" in ids
        assert "topological_governance" in ids
        assert "chern_number_v2" in ids

    def test_salience_in_unit_interval(self):
        for concept in _GPLOT_CONCEPTS:
            assert 0.0 <= concept["salience"] <= 1.0


# ---------------------------------------------------------------------------
# Static data validation — telos objectives
# ---------------------------------------------------------------------------


class TestGplotTelosObjectives:
    def test_count(self):
        assert len(_GPLOT_TELOS_OBJECTIVES) == 6

    def test_required_fields(self):
        for obj in _GPLOT_TELOS_OBJECTIVES:
            assert "name" in obj
            assert "priority" in obj
            assert "progress" in obj
            assert "description" in obj
            assert "perspective" in obj

    def test_priorities_high(self):
        for obj in _GPLOT_TELOS_OBJECTIVES:
            assert obj["priority"] >= 6

    def test_progress_below_1(self):
        for obj in _GPLOT_TELOS_OBJECTIVES:
            assert 0.0 <= obj["progress"] < 1.0

    def test_v1_is_top_priority(self):
        v1 = [o for o in _GPLOT_TELOS_OBJECTIVES if "v1" in o["name"].lower()]
        assert len(v1) >= 1
        # v1 (Takens MVP) should be the highest priority
        v1_mvp = [o for o in v1 if "MVP" in o["name"]]
        assert len(v1_mvp) == 1
        assert v1_mvp[0]["priority"] == 9

    def test_gplot_metadata_domain(self):
        for obj in _GPLOT_TELOS_OBJECTIVES:
            md = obj.get("metadata", {})
            assert md.get("domain") == "gplot"
            assert md.get("pillar") == "invariance"


# ---------------------------------------------------------------------------
# Static data validation — task seeds
# ---------------------------------------------------------------------------


class TestGplotTaskSeeds:
    def test_count(self):
        assert len(_GPLOT_TASK_SEEDS) == 5

    def test_required_fields(self):
        for task in _GPLOT_TASK_SEEDS:
            assert "title" in task
            assert "description" in task
            assert "priority" in task
            assert "tags" in task

    def test_all_have_gplot_tag(self):
        for task in _GPLOT_TASK_SEEDS:
            assert "gplot" in task["tags"]

    def test_descriptions_substantial(self):
        for task in _GPLOT_TASK_SEEDS:
            assert len(task["description"]) > 100

    def test_first_artifact_is_build_task(self):
        # The v1 build task must be present and high-priority
        build_tasks = [t for t in _GPLOT_TASK_SEEDS
                       if "invariant_observatory.py" in t["title"]]
        assert len(build_tasks) == 1
        assert build_tasks[0]["priority"] >= 8


# ---------------------------------------------------------------------------
# GplotLodestone class
# ---------------------------------------------------------------------------


class TestGplotLodestone:
    def test_construction(self, tmp_path):
        lodestone = GplotLodestone(state_dir=tmp_path)
        assert lodestone._state_dir == tmp_path

    def test_default_state_dir(self):
        lodestone = GplotLodestone()
        assert lodestone._state_dir is not None

    @pytest.mark.asyncio
    async def test_seed_all_returns_expected_keys(self, tmp_path):
        """seed_all returns the expected result-shape dict even if every
        substrate call fails (each helper swallows exceptions and returns 0).
        """
        lodestone = GplotLodestone(state_dir=tmp_path)
        result = await lodestone.seed_all()
        assert set(result.keys()) == {
            "stigmergy_marks",
            "concept_nodes",
            "telos_objectives",
            "task_seeds",
        }
        for v in result.values():
            assert isinstance(v, int)
            assert v >= 0
