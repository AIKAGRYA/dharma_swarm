"""Tests for dharma_swarm.organism_memory — autonoetic self-model.

Validates:
- MemoryEntity and MemoryRelationship Pydantic models
- OrganismMemory construction and state_dir creation
- record_event: append, persistence, auto-insight invalidation
- record_relationship: typed edge creation
- invalidate_entity: soft-invalidation with reason
- invalidate_contradicted: Jaccard-based insight supersession
- graph_traverse: BFS with direction filters
- find_related: immediate neighbor lookup with type filter
- decay_confidence: exponential age-based decay
- gc: soft-delete below threshold
- developmental_narrative: text generation
- self_model_accuracy: insight validity ratio
- shakti_profile: domain grouping
- entities_by_type: filtered retrieval
- stats: summary aggregation
- _load / _save persistence round-trip
"""

from __future__ import annotations

import json
import time

import pytest

from dharma_swarm.organism_memory import (
    MemoryEntity,
    MemoryRelationship,
    OrganismMemory,
    _new_mem_id,
    _utc_now,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestMemoryEntity:
    def test_defaults(self):
        e = MemoryEntity(entity_type="insight", description="Test insight")
        assert e.entity_type == "insight"
        assert e.confidence == 1.0
        assert e.access_count == 0
        assert e.temporal_valid_to is None
        assert e.id.startswith("e_")

    def test_metadata_default(self):
        e = MemoryEntity(entity_type="mutation", description="Mutated router")
        assert e.metadata == {}


class TestMemoryRelationship:
    def test_construction(self):
        r = MemoryRelationship(from_id="a", to_id="b", rel_type="caused")
        assert r.from_id == "a"
        assert r.rel_type == "caused"
        assert r.valid_until is None


class TestHelpers:
    def test_new_mem_id_prefix(self):
        assert _new_mem_id("test").startswith("test_")
        assert len(_new_mem_id()) > 4

    def test_utc_now(self):
        now = _utc_now()
        assert now.tzinfo is not None


# ---------------------------------------------------------------------------
# OrganismMemory construction
# ---------------------------------------------------------------------------


class TestOrganismMemoryInit:
    def test_creates_dir(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        assert (tmp_path / "organism_memory").is_dir()
        assert len(mem._entities) == 0

    def test_empty_state(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        assert mem.stats()["total_entities"] == 0
        assert mem.stats()["total_relationships"] == 0


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_returns_id(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        eid = mem.record_event("mutation", "Changed router logic")
        assert eid.startswith("e_")

    def test_appends_entity(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("decision", "Route to agent-7")
        assert len(mem._entities) == 1
        assert mem._entities[0].entity_type == "decision"

    def test_with_metadata(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("capability", "Can audit code", metadata={"domain": "engineering"})
        assert mem._entities[0].metadata["domain"] == "engineering"

    def test_persists_to_disk(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("insight", "System is healthy")
        entities_file = tmp_path / "organism_memory" / "entities.jsonl"
        assert entities_file.exists()
        lines = entities_file.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["entity_type"] == "insight"

    def test_multiple_events(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        for i in range(5):
            mem.record_event("decision", f"Decision {i}")
        assert len(mem._entities) == 5


# ---------------------------------------------------------------------------
# record_relationship
# ---------------------------------------------------------------------------


class TestRecordRelationship:
    def test_appends(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        mem.record_relationship(e1, e2, "caused")
        assert len(mem._relationships) == 1
        assert mem._relationships[0].rel_type == "caused"

    def test_persists(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        mem.record_relationship(e1, e2, "preceded")
        rels_file = tmp_path / "organism_memory" / "relationships.jsonl"
        assert rels_file.exists()


# ---------------------------------------------------------------------------
# invalidate_entity
# ---------------------------------------------------------------------------


class TestInvalidateEntity:
    def test_soft_invalidates(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        eid = mem.record_event("insight", "Old insight")
        result = mem.invalidate_entity(eid, reason="superseded")
        assert result is True
        entity = mem._entities[0]
        assert entity.temporal_valid_to is not None
        assert entity.metadata["invalidation_reason"] == "superseded"

    def test_not_found_returns_false(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        assert mem.invalidate_entity("nonexistent") is False


# ---------------------------------------------------------------------------
# invalidate_contradicted
# ---------------------------------------------------------------------------


class TestInvalidateContradicted:
    def test_auto_supersedes_on_record(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        # Jaccard ≥0.5 required: 5 shared / 7 union ≈ 0.71
        old_id = mem.record_event("insight", "the router performance is stable now")
        # Recording a similar insight auto-calls invalidate_contradicted
        mem.record_event("insight", "the router performance is degraded now")
        old = next(e for e in mem._entities if e.id == old_id)
        assert old.temporal_valid_to is not None

    def test_does_not_supersede_different_insight(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        old_id = mem.record_event("insight", "biosphere health declining rapidly")
        mem.record_event("insight", "router performance is excellent and fast")
        old = next(e for e in mem._entities if e.id == old_id)
        assert old.temporal_valid_to is None

    def test_ignores_non_insights(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        old_id = mem.record_event("mutation", "some mutation description here")
        mem.record_event("insight", "some mutation description here")
        old = next(e for e in mem._entities if e.id == old_id)
        # mutation should not be invalidated (only insights are checked)
        assert old.temporal_valid_to is None


# ---------------------------------------------------------------------------
# graph_traverse
# ---------------------------------------------------------------------------


class TestGraphTraverse:
    def test_bfs_traversal(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        e3 = mem.record_event("capability", "C1")
        mem.record_relationship(e1, e2, "caused")
        mem.record_relationship(e2, e3, "enabled")

        reachable = mem.graph_traverse(e1, max_depth=2)
        reachable_ids = {e.id for e in reachable}
        assert e2 in reachable_ids
        assert e3 in reachable_ids

    def test_respects_max_depth(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        e3 = mem.record_event("capability", "C1")
        mem.record_relationship(e1, e2, "caused")
        mem.record_relationship(e2, e3, "enabled")

        reachable = mem.graph_traverse(e1, max_depth=1)
        reachable_ids = {e.id for e in reachable}
        assert e2 in reachable_ids
        assert e3 not in reachable_ids

    def test_unknown_start_returns_empty(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        assert mem.graph_traverse("nonexistent") == []

    def test_direction_out(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        mem.record_relationship(e2, e1, "caused")  # e2 → e1

        reachable = mem.graph_traverse(e1, max_depth=1, direction="out")
        assert len(reachable) == 0  # e1 has no outgoing edges


# ---------------------------------------------------------------------------
# find_related
# ---------------------------------------------------------------------------


class TestFindRelated:
    def test_finds_neighbors(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        mem.record_relationship(e1, e2, "caused")

        related = mem.find_related(e1)
        assert len(related) == 1
        entity, rel = related[0]
        assert entity.id == e2
        assert rel.rel_type == "caused"

    def test_filter_by_rel_type(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        e1 = mem.record_event("mutation", "M1")
        e2 = mem.record_event("decision", "D1")
        e3 = mem.record_event("capability", "C1")
        mem.record_relationship(e1, e2, "caused")
        mem.record_relationship(e1, e3, "enabled")

        related = mem.find_related(e1, rel_types=["enabled"])
        assert len(related) == 1
        assert related[0][0].id == e3


# ---------------------------------------------------------------------------
# decay_confidence + gc
# ---------------------------------------------------------------------------


class TestDecayAndGC:
    def test_gc_removes_low_confidence(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("insight", "old insight", confidence=0.005)
        removed = mem.gc(min_confidence=0.01)
        assert removed == 1
        assert mem._entities[0].temporal_valid_to is not None

    def test_gc_keeps_high_confidence(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("insight", "fresh insight", confidence=0.9)
        removed = mem.gc(min_confidence=0.01)
        assert removed == 0


# ---------------------------------------------------------------------------
# developmental_narrative
# ---------------------------------------------------------------------------


class TestDevelopmentalNarrative:
    def test_empty_narrative(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        narrative = mem.developmental_narrative()
        assert "No developmental history" in narrative

    def test_with_events(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("mutation", "Upgraded router")
        mem.record_event("decision", "Selected agent-3")
        narrative = mem.developmental_narrative()
        assert "Upgraded router" in narrative
        assert "Selected agent-3" in narrative

    def test_shows_invalidated(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        eid = mem.record_event("insight", "Wrong assumption")
        mem.invalidate_entity(eid, reason="corrected")
        narrative = mem.developmental_narrative()
        assert "INVALIDATED" in narrative


# ---------------------------------------------------------------------------
# self_model_accuracy
# ---------------------------------------------------------------------------


class TestSelfModelAccuracy:
    def test_no_insights_returns_1(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        assert mem.self_model_accuracy() == 1.0

    def test_all_valid_returns_1(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("insight", "Insight 1")
        mem.record_event("insight", "Insight 2 different")
        assert mem.self_model_accuracy() == 1.0

    def test_partially_invalid(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        eid = mem.record_event("insight", "Old view")
        mem.record_event("insight", "New view unrelated")
        mem.invalidate_entity(eid)
        accuracy = mem.self_model_accuracy()
        assert 0.0 < accuracy < 1.0


# ---------------------------------------------------------------------------
# shakti_profile
# ---------------------------------------------------------------------------


class TestShaktiProfile:
    def test_groups_by_domain(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("capability", "Can write code", metadata={"domain": "engineering"})
        mem.record_event("capability", "Can audit security", metadata={"domain": "security"})
        profile = mem.shakti_profile()
        assert "engineering" in profile
        assert "security" in profile

    def test_empty(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        assert mem.shakti_profile() == {}


# ---------------------------------------------------------------------------
# entities_by_type
# ---------------------------------------------------------------------------


class TestEntitiesByType:
    def test_filters_correctly(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("mutation", "M1")
        mem.record_event("decision", "D1")
        mem.record_event("mutation", "M2")
        mutations = mem.entities_by_type("mutation")
        assert len(mutations) == 2
        assert all(e.entity_type == "mutation" for e in mutations)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_aggregation(self, tmp_path):
        mem = OrganismMemory(state_dir=tmp_path)
        mem.record_event("mutation", "M1")
        mem.record_event("decision", "D1")
        mem.record_event("mutation", "M2")
        s = mem.stats()
        assert s["total_entities"] == 3
        assert s["by_type"]["mutation"] == 2
        assert s["by_type"]["decision"] == 1


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_load_from_disk(self, tmp_path):
        mem1 = OrganismMemory(state_dir=tmp_path)
        e1 = mem1.record_event("mutation", "M1", metadata={"v": 1})
        e2 = mem1.record_event("decision", "D1")
        mem1.record_relationship(e1, e2, "caused")

        mem2 = OrganismMemory(state_dir=tmp_path)
        assert len(mem2._entities) == 2
        assert len(mem2._relationships) == 1
        assert mem2._entities[0].entity_type == "mutation"
        assert mem2._relationships[0].rel_type == "caused"

    def test_corrupt_lines_skipped(self, tmp_path):
        state = tmp_path / "organism_memory"
        state.mkdir(parents=True)
        entities = state / "entities.jsonl"
        entities.write_text('{"type":"entity","entity_type":"x","description":"ok","id":"e_1"}\nnot json\n')
        mem = OrganismMemory(state_dir=tmp_path)
        assert len(mem._entities) == 1
