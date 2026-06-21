"""Self-validation for tests/evolution_gate_helpers.py.

If a Tier-C gate changes its requirements, this test fails loudly here — at the
single source of truth — instead of silently rotting across every evolution
test that depends on the helper. See
docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md.
"""
from __future__ import annotations

from pathlib import Path

from dharma_swarm.evolution import DarwinEngine, EvolutionStatus
from dharma_swarm.models import GateDecision
from tests.evolution_gate_helpers import (
    gate_compliant_description,
    gate_compliant_proposal_kwargs,
    tier_c_diff,
)


async def _gated_proposal(tmp_path: Path, **propose_kwargs):
    engine = DarwinEngine(
        archive_path=tmp_path / "archive.jsonl",
        traces_path=tmp_path / "traces",
        predictor_path=tmp_path / "predictor.jsonl",
    )
    await engine.init()
    proposal = await engine.propose(**propose_kwargs)
    await engine.gate_check(proposal)
    return proposal


async def test_compliant_proposal_clears_full_tier_c_battery(tmp_path: Path) -> None:
    """The helper's output must produce ALLOW (not a REVIEW hard-reject)."""
    proposal = await _gated_proposal(
        tmp_path,
        **gate_compliant_proposal_kwargs(component="probe.py", intent="Add a metric"),
    )
    gates = (proposal.metadata or {}).get("gate_results", {})
    failed = {
        name: verdict
        for name, verdict in gates.items()
        if str(getattr(verdict, "value", verdict)).upper() not in {"PASS", "WARN"}
    }
    assert not failed, f"Tier-C gates regressed: {failed}"
    assert proposal.gate_decision == GateDecision.ALLOW.value
    assert proposal.status != EvolutionStatus.REJECTED


async def test_terse_description_is_still_rejected(tmp_path: Path) -> None:
    """Guard the guard: a terse self-mod proposal is still hard-rejected, so the
    helper is doing real work rather than the gate having gone permissive."""
    proposal = await _gated_proposal(
        tmp_path,
        component="probe.py",
        change_type="mutation",
        description="Improve error handling",
        diff="+x",
    )
    assert proposal.status == EvolutionStatus.REJECTED


def test_helper_pieces_carry_the_required_markers() -> None:
    """Cheap, no-engine sanity: the frames clause and diff note keep their markers."""
    desc = gate_compliant_description("Refactor things").lower()
    assert "mechanism" in desc  # mechanistic frame
    assert "observer" in desc or "awareness" in desc  # phenomenological frame
    assert "feedback" in desc or "resilience" in desc  # systems frame
    diff = tier_c_diff("+code").lower()
    assert "however" in diff or "risk:" in diff  # steelman
    assert "tested" in diff or "verified" in diff  # dogma-drift evidence
