from __future__ import annotations

from dharma_swarm.venture_cell.domain_ceo import ProviderProof
from dharma_swarm.venture_cell.livelihood_loom.status import project_readiness


def test_livelihood_readiness_refuses_green_without_provider_proof():
    readiness = project_readiness()
    assert readiness.cell_id == "livelihood_loom"
    assert readiness.overall_status.endswith("provider_blocked")
    gates = {gate.name: gate.status for gate in readiness.gates}
    assert gates["charter_contract"] == "green"
    assert gates["provider_proof"] == "red"


def test_livelihood_readiness_turns_control_plane_ready_with_complete_provider_proof():
    readiness = project_readiness(
        provider_proof=ProviderProof(
            provider="openrouter",
            model="test/model",
            attempted_at="2026-06-29T00:00:00Z",
            success=True,
            receipt_id="rr_provider",
            trace_id="trace_provider",
            result_ref="artifact_provider",
        )
    )
    assert readiness.overall_status == "control_plane_ready"
    gates = {gate.name: gate.status for gate in readiness.gates}
    assert gates["provider_proof"] == "green"
