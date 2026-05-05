"""Tests for dharma_swarm.gnani_lodestone — boot-time Gnani seeder.

Validates:
- _GNANI_MARKS: 5 marks, all gnani channel, high salience, correct agent
- _GNANI_CONCEPTS: 6 concept nodes with required fields
- _GNANI_TELOS_OBJECTIVES: 4 objectives with priority/progress
- _GNANI_TASK_SEEDS: 4 tasks with research tags
- GnaniLodestone construction
- seed_all structure (result keys)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.gnani_lodestone import (
    GnaniLodestone,
    _GNANI_CONCEPTS,
    _GNANI_MARKS,
    _GNANI_TASK_SEEDS,
    _GNANI_TELOS_OBJECTIVES,
)


# ---------------------------------------------------------------------------
# Static data validation
# ---------------------------------------------------------------------------


class TestGnaniMarks:
    def test_count(self):
        assert len(_GNANI_MARKS) == 5

    def test_all_gnani_channel(self):
        for mark in _GNANI_MARKS:
            assert mark["channel"] == "gnani"

    def test_high_salience(self):
        for mark in _GNANI_MARKS:
            assert mark["salience"] >= 0.90

    def test_agent_is_gnani_lodestone(self):
        for mark in _GNANI_MARKS:
            assert mark["agent"] == "gnani-lodestone"

    def test_unique_ids(self):
        ids = [m["id"] for m in _GNANI_MARKS]
        assert len(ids) == len(set(ids))

    def test_all_have_observation(self):
        for mark in _GNANI_MARKS:
            assert len(mark["observation"]) > 50

    def test_all_have_file_path(self):
        for mark in _GNANI_MARKS:
            assert mark["file_path"]


class TestGnaniConcepts:
    def test_count(self):
        assert len(_GNANI_CONCEPTS) == 6

    def test_required_fields(self):
        for concept in _GNANI_CONCEPTS:
            assert "id" in concept
            assert "name" in concept
            assert "description" in concept
            assert "salience" in concept
            assert "tags" in concept

    def test_unique_ids(self):
        ids = [c["id"] for c in _GNANI_CONCEPTS]
        assert len(ids) == len(set(ids))

    def test_all_have_pillar(self):
        for concept in _GNANI_CONCEPTS:
            assert "pillar" in concept

    def test_key_concepts_present(self):
        ids = {c["id"] for c in _GNANI_CONCEPTS}
        assert "gnani_layer" in ids
        assert "witness_upstream" in ids
        assert "samyak_darshan" in ids
        assert "strange_loop_aware" in ids
        assert "bija_seed" in ids
        assert "kriya_without_drashti" in ids


class TestGnaniTelosObjectives:
    def test_count(self):
        assert len(_GNANI_TELOS_OBJECTIVES) == 4

    def test_required_fields(self):
        for obj in _GNANI_TELOS_OBJECTIVES:
            assert "name" in obj
            assert "priority" in obj
            assert "progress" in obj
            assert "description" in obj

    def test_priorities_high(self):
        for obj in _GNANI_TELOS_OBJECTIVES:
            assert obj["priority"] >= 7

    def test_progress_below_1(self):
        for obj in _GNANI_TELOS_OBJECTIVES:
            assert 0.0 <= obj["progress"] < 1.0


class TestGnaniTaskSeeds:
    def test_count(self):
        assert len(_GNANI_TASK_SEEDS) == 4

    def test_required_fields(self):
        for task in _GNANI_TASK_SEEDS:
            assert "title" in task
            assert "description" in task
            assert "priority" in task
            assert "tags" in task

    def test_all_have_gnani_tag(self):
        for task in _GNANI_TASK_SEEDS:
            assert "gnani" in task["tags"]

    def test_descriptions_substantial(self):
        for task in _GNANI_TASK_SEEDS:
            assert len(task["description"]) > 100


# ---------------------------------------------------------------------------
# GnaniLodestone class
# ---------------------------------------------------------------------------


class TestGnaniLodestone:
    def test_construction(self, tmp_path):
        lodestone = GnaniLodestone(state_dir=tmp_path)
        assert lodestone._state_dir == tmp_path

    def test_default_state_dir(self):
        lodestone = GnaniLodestone()
        assert lodestone._state_dir is not None
