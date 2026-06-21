"""Stage 2: Shakti reads the world, hands still down. Corroborated world receipts
become ADVISORY warrant-pressure (data objects); refuted/insufficient/quarantined
produce none; dispatch authority stays False; the adapter mutates no owner.
"""
from __future__ import annotations

from dharma_swarm.world_radar.frontier_council import (
    CORROBORATED,
    EvidenceRef,
    FrontierCouncilInput,
    evaluate_boundary_signal,
)
from dharma_swarm.world_radar.warrant_handoff import (
    WorldWarrantPressure,
    world_warrant_pressure,
)


def _receipt(verdict_refs, instruction_risk="low", safe=True):
    return evaluate_boundary_signal(
        FrontierCouncilInput(
            claim="signal",
            input_signal_hash="sha256:s",
            evidence_refs=verdict_refs,
            safe=safe,
            instruction_risk=instruction_risk,
        )
    )


_CORROBORATED = [EvidenceRef("arxiv", True, 0.8), EvidenceRef("repro", True, 0.7)]
_REFUTED = [EvidenceRef("audit", False, 0.9)]
_INSUFFICIENT = [EvidenceRef("blog", True, 0.95), EvidenceRef("blog", True, 0.95)]


def test_corroborated_receipt_yields_one_advisory_pressure():
    r = _receipt(_CORROBORATED)
    assert r.verdict == CORROBORATED
    pressures = world_warrant_pressure([r])
    assert len(pressures) == 1
    p = pressures[0]
    assert isinstance(p, WorldWarrantPressure)
    assert p.is_advisory is True
    assert p.no_action_authority is True
    assert p.dispatch_authority is False
    assert p.source_receipt_id == r.receipt_id
    assert 0.0 < p.pressure_weight <= 1.0


def test_non_corroborated_receipts_produce_no_pressure():
    assert world_warrant_pressure([_receipt(_REFUTED)]) == []
    assert world_warrant_pressure([_receipt(_INSUFFICIENT)]) == []
    assert world_warrant_pressure([_receipt(_CORROBORATED, instruction_risk="high")]) == []  # quarantined
    assert world_warrant_pressure([_receipt(_CORROBORATED, safe=False)]) == []  # quarantined


def test_a_receipt_claiming_authority_is_defensively_dropped():
    r = _receipt(_CORROBORATED)
    poisoned = {**r.__dict__, "dispatch_authority": True}
    assert world_warrant_pressure([poisoned]) == []
    no_auth_flag = {**r.__dict__, "no_action_authority": False}
    assert world_warrant_pressure([no_auth_flag]) == []


def test_accepts_json_dicts_and_pressure_weight_is_bounded():
    import json

    blob = json.loads(_receipt(_CORROBORATED).to_json())
    pressures = world_warrant_pressure([blob])
    assert len(pressures) == 1
    assert 0.0 <= pressures[0].pressure_weight <= 1.0


def test_adapter_is_pure_and_mutates_no_owner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    world_warrant_pressure([_receipt(_CORROBORATED)])
    assert set(tmp_path.iterdir()) == before  # no files written
