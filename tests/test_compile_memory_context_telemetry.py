from __future__ import annotations

import json

import pytest

from dharma_swarm.memory_lattice import MemoryLattice


@pytest.mark.asyncio
async def test_compile_memory_context_logs_retrieval_effect(tmp_path) -> None:
    lattice = MemoryLattice(
        db_path=tmp_path / "runtime.db",
        event_log_dir=tmp_path / "events",
    )
    await lattice.init_db()
    fact = await lattice.record_fact(
        "The memory membrane records retrieval effects.",
        fact_kind="membrane_rule",
        truth_state="promoted",
        confidence=0.9,
        session_id="sess-retrieval",
        task_id="task-retrieval",
    )
    effect_path = tmp_path / "retrieval" / "effect.jsonl"

    bundle = await lattice.compile_memory_context(
        session_id="sess-retrieval",
        task_id="task-retrieval",
        task_description="membrane",
        token_budget=300,
        retrieval_effect_path=effect_path,
    )

    rows = [
        json.loads(line)
        for line in effect_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert rows
    assert rows[0]["session_id"] == "sess-retrieval"
    assert fact.fact_id in rows[0]["injected_fact_ids"]
    assert bundle.metadata["retrieval_effect_id"] == rows[0]["effect_id"]
    assert bundle.metadata["retrieval_fact_ids"] == [fact.fact_id]
    assert "Durable Facts" in bundle.rendered_text

    await lattice.close()


@pytest.mark.asyncio
async def test_compile_memory_context_strict_policy_caps_token_budget(tmp_path) -> None:
    lattice = MemoryLattice(db_path=tmp_path / "runtime.db", event_log_dir=tmp_path / "events")
    await lattice.init_db()
    effect_path = tmp_path / "effect.jsonl"

    bundle = await lattice.compile_memory_context(
        session_id="sess-strict",
        token_budget=500,
        membrane_policy="strict",
        retrieval_policy={"max_tokens": 120, "min_truth_state": "promoted"},
        retrieval_effect_path=effect_path,
    )

    assert bundle.token_budget == 120
    assert bundle.metadata["retrieval_policy"]["min_truth_state"] == "promoted"

    await lattice.close()


@pytest.mark.asyncio
async def test_log_effect_suppresses_canonical_default_when_flag_off(
    tmp_path, monkeypatch
) -> None:
    """The retrieval-effect JSONL must not write to its canonical default path
    unless DHARMA_CHETANA_ENABLED=1, mirroring the register-mark gate."""
    from dharma_swarm.retrieval import retrieval_effect_logger as logger_mod

    monkeypatch.delenv("DHARMA_CHETANA_ENABLED", raising=False)
    canonical = tmp_path / "retrieval" / "effect.jsonl"
    monkeypatch.setattr(logger_mod, "DEFAULT_RETRIEVAL_EFFECT_LOG", canonical)
    logger_mod.reset_suppressed_retrieval_effect_count()

    effect = logger_mod.RetrievalEffect(
        effect_id=logger_mod.new_effect_id(),
        session_id="s",
        task_id="t",
        injected_fact_ids=[],
        citation_handles=[],
        policy_used={},
        token_budget=0,
        actual_tokens=0,
        contradictions_dropped=[],
        ts=logger_mod.now_iso(),
    )

    # Default-path call: suppressed
    assert logger_mod.log_effect(effect) is False
    assert logger_mod.get_suppressed_retrieval_effect_count() == 1
    assert not canonical.exists()

    # Explicit non-canonical path: writes through
    other = tmp_path / "explicit.jsonl"
    assert logger_mod.log_effect(effect, path=other) is True
    assert other.exists()

    # Master flag flips → canonical default writes through
    monkeypatch.setenv("DHARMA_CHETANA_ENABLED", "1")
    assert logger_mod.log_effect(effect) is True
    assert canonical.exists()
