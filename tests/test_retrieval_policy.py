from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.memory_lattice import MemoryLattice, RetrievalAdmissionPolicy
from dharma_swarm.retrieval.contradiction_detector import detect_contradictions
from dharma_swarm.retrieval.retrieval_effect_logger import citation_handle_for_fact_id


def test_retrieval_policy_defaults_and_strict() -> None:
    default = RetrievalAdmissionPolicy.default()
    strict = RetrievalAdmissionPolicy.strict()

    assert default.min_truth_state == "candidate"
    assert default.min_confidence == 0.0
    assert strict.min_truth_state == "promoted"
    assert strict.min_confidence == 0.6
    assert strict.max_age_days == 90
    assert strict.as_dict()["source_scope"] == []


def test_contradiction_detector_flags_negation_flip() -> None:
    contradictions = detect_contradictions(
        [
            {"id": "a", "text": "The daemon should start archaeology when enabled."},
            {"id": "b", "text": "The daemon should not start archaeology when enabled."},
        ]
    )

    assert len(contradictions) == 1
    assert contradictions[0].reason == "negation_flip"


def test_contradiction_detector_flags_numeric_disagreement() -> None:
    contradictions = detect_contradictions(
        [
            {"id": "a", "text": "The budget limit is 100 USD for the run."},
            {"id": "b", "text": "The budget limit is 300 USD for the run."},
        ]
    )

    assert len(contradictions) == 1
    assert contradictions[0].reason == "numeric_disagreement"


def test_citation_handle_is_stable() -> None:
    handle = citation_handle_for_fact_id("fact-abc")

    assert handle == citation_handle_for_fact_id("fact-abc")
    assert handle.startswith("PR-")
    assert len(handle) == 29


@pytest.mark.asyncio
async def test_compile_memory_context_drops_low_confidence_facts(tmp_path):
    """min_confidence policy must drop facts from injected_fact_ids."""
    lattice = MemoryLattice(
        db_path=tmp_path / "runtime.db",
        event_log_dir=tmp_path / "events",
    )
    await lattice.init_db()
    keep = await lattice.record_fact(
        "high-confidence fact",
        fact_kind="membrane_rule",
        truth_state="promoted",
        confidence=0.9,
        session_id="sess-policy",
    )
    drop = await lattice.record_fact(
        "low-confidence fact",
        fact_kind="membrane_rule",
        truth_state="promoted",
        confidence=0.2,
        session_id="sess-policy",
    )
    bundle = await lattice.compile_memory_context(
        session_id="sess-policy",
        token_budget=400,
        retrieval_policy={"min_confidence": 0.5},
        retrieval_effect_path=tmp_path / "effect.jsonl",
    )
    assert keep.fact_id in bundle.metadata["retrieval_fact_ids"]
    assert drop.fact_id not in bundle.metadata["retrieval_fact_ids"]
    assert drop.fact_id in bundle.metadata["policy_dropped_fact_ids"]
    drop_reasons = {r["fact_id"]: r["reason"] for r in bundle.metadata["policy_drop_reasons"]}
    assert drop_reasons[drop.fact_id] == "min_confidence"
    await lattice.close()


@pytest.mark.asyncio
async def test_compile_memory_context_drops_out_of_scope_facts(tmp_path):
    """source_scope policy must drop facts whose fact_kind is outside the scope."""
    lattice = MemoryLattice(
        db_path=tmp_path / "runtime.db",
        event_log_dir=tmp_path / "events",
    )
    await lattice.init_db()
    in_scope = await lattice.record_fact(
        "membrane fact",
        fact_kind="membrane_rule",
        truth_state="promoted",
        confidence=0.8,
        session_id="sess-scope",
    )
    out_scope = await lattice.record_fact(
        "unrelated fact",
        fact_kind="random_kind",
        truth_state="promoted",
        confidence=0.8,
        session_id="sess-scope",
    )
    bundle = await lattice.compile_memory_context(
        session_id="sess-scope",
        token_budget=400,
        retrieval_policy={"source_scope": ["membrane_rule"]},
        retrieval_effect_path=tmp_path / "effect.jsonl",
    )
    assert in_scope.fact_id in bundle.metadata["retrieval_fact_ids"]
    assert out_scope.fact_id not in bundle.metadata["retrieval_fact_ids"]
    assert out_scope.fact_id in bundle.metadata["policy_dropped_fact_ids"]
    await lattice.close()


@pytest.mark.asyncio
async def test_compile_memory_context_marks_policy_enforcement_level(tmp_path):
    """Bundle metadata must explicitly state the enforcement level."""
    lattice = MemoryLattice(
        db_path=tmp_path / "runtime.db",
        event_log_dir=tmp_path / "events",
    )
    await lattice.init_db()
    bundle = await lattice.compile_memory_context(
        session_id="sess-honest",
        token_budget=300,
        retrieval_effect_path=tmp_path / "effect.jsonl",
    )
    assert bundle.metadata["policy_enforcement_level"] == "metadata-only-pending-render-integration"
    await lattice.close()
