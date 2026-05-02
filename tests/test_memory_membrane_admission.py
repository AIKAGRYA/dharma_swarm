from __future__ import annotations

from types import SimpleNamespace

import pytest

from dharma_swarm import register_disciplines as rd
from dharma_swarm.chetana.provenance import GateCheckRecord
from dharma_swarm.memory_lattice import MemoryLattice
from dharma_swarm.policy_compiler import PolicyDecision
from dharma_swarm.runtime_state import MemoryEdge, MemoryFact


class BlockingPolicy:
    def check_action(self, action: str, context: str = "", action_metadata=None):
        return PolicyDecision(allowed=False, reason=f"blocked {action}")


@pytest.mark.asyncio
async def test_admit_memory_fact_records_admission_provenance_and_recalls(tmp_path):
    lattice = MemoryLattice(
        db_path=tmp_path / "runtime.db",
        event_log_dir=tmp_path / "events",
    )
    await lattice.init_db()
    fact = MemoryFact(
        fact_id=lattice.runtime_state.new_fact_id(),
        fact_kind="operator_decision",
        truth_state="candidate",
        text="The membrane admission facade owns new fact writes.",
        confidence=0.9,
        session_id="sess-membrane",
        task_id="task-membrane",
    )

    result = await lattice.admit_memory_fact(fact, metadata={"caller": "test"})
    saved = await lattice.runtime_state.get_memory_fact(fact.fact_id)
    hits = await lattice.recall(
        "membrane admission facade",
        session_id="sess-membrane",
    )

    assert result.accepted is True
    assert result.object_id == fact.fact_id
    assert saved is not None
    assert saved.provenance["admission"]["admitter"] == "MemoryLattice.admit_memory_fact"
    assert saved.provenance["admission"]["gate_result"] == "ALLOW"
    assert hits

    await lattice.close()


@pytest.mark.asyncio
async def test_admit_memory_fact_policy_block_does_not_write(tmp_path):
    lattice = MemoryLattice(db_path=tmp_path / "runtime.db")
    await lattice.init_db()
    fact = MemoryFact(
        fact_id=lattice.runtime_state.new_fact_id(),
        fact_kind="blocked",
        truth_state="candidate",
        text="This write should be blocked.",
    )

    result = await lattice.admit_memory_fact(
        fact,
        context={"policy": BlockingPolicy()},
    )

    assert result.accepted is False
    assert result.object_id is None
    assert result.gate_check.result == "BLOCK"
    assert await lattice.runtime_state.get_memory_fact(fact.fact_id) is None

    await lattice.close()


@pytest.mark.asyncio
async def test_admit_memory_edge_records_admission_metadata(tmp_path):
    lattice = MemoryLattice(db_path=tmp_path / "runtime.db")
    await lattice.init_db()
    edge = MemoryEdge(
        edge_id=lattice.runtime_state.new_edge_id(),
        from_fact_id="fact-a",
        to_fact_id="fact-b",
        relation="supports",
        weight=0.7,
    )

    result = await lattice.admit_memory_edge(edge)

    assert result.accepted is True
    assert result.object_kind == "edge"
    assert result.object_id == edge.edge_id
    assert result.gate_check.result == "ALLOW"

    await lattice.close()


@pytest.mark.asyncio
async def test_admit_register_mark_respects_canonical_flag(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    lattice = MemoryLattice(db_path=tmp_path / "runtime.db")
    log = tmp_path / "stigmergy" / "register_marks.jsonl"
    monkeypatch.setattr(rd, "DEFAULT_REGISTER_LOG", log)
    monkeypatch.delenv("DHARMA_CHETANA_ENABLED", raising=False)
    rd.reset_suppressed_register_mark_count()

    blocked = await lattice.admit_register_mark(
        discipline="membrane_canary",
        subject_id="subject-1",
        severity="warn",
        rationale="flag off canary",
    )

    monkeypatch.setenv("DHARMA_CHETANA_ENABLED", "1")
    allowed = await lattice.admit_register_mark(
        discipline="membrane_canary",
        subject_id="subject-2",
        severity="warn",
        rationale="flag on canary",
    )

    assert blocked.accepted is False
    assert blocked.object_id is None
    assert allowed.accepted is True
    assert allowed.object_id is not None
    assert rd.get_suppressed_register_mark_count() == 1
    assert log.exists()

    await lattice.close()


@pytest.mark.asyncio
async def test_admit_chetana_atom_uses_existing_gate(monkeypatch, tmp_path):
    lattice = MemoryLattice(db_path=tmp_path / "runtime.db")
    calls = []

    def fake_gate_check_atom(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            can_promote=True,
            record=GateCheckRecord(
                result="ALLOW",
                gates_passed=["fake"],
                checked_at="2026-05-02T00:00:00+00:00",
            ),
        )

    monkeypatch.setattr("dharma_swarm.memory_lattice.gate_check_atom", fake_gate_check_atom)

    result = await lattice.admit_chetana_atom(
        "body",
        "Atom Title",
        requested_action="chetana.promote",
        metadata={"atom_id": "atom-123"},
    )

    assert result.accepted is True
    assert result.object_kind == "atom"
    assert result.object_id == "atom-123"
    assert calls[0]["requested_action"] == "chetana.promote"
