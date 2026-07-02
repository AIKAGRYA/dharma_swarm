from __future__ import annotations

import pytest

from dharma_swarm.venture_cell import DomainCEOContractError, ProviderProof
from dharma_swarm.venture_cell.livelihood_loom import load_livelihood_loom_contract


def test_livelihood_loom_contract_loads_with_capital_firewall():
    contract = load_livelihood_loom_contract()
    assert contract.cell_id == "livelihood_loom"
    assert contract.parent_plane == "jagat_kalyan"
    assert contract.capital_boundary == "dharma_capital_read_only_aggregated_signals"
    assert "field_cartography" in contract.allowed_agent_roles
    assert "trading_alpha_extraction" in contract.external_action_policy.forbidden_actions


def test_ceo_contract_blocks_unapproved_agent_role():
    contract = load_livelihood_loom_contract()
    with pytest.raises(DomainCEOContractError, match="agent role not allowed"):
        contract.check_spawn(
            requested_role="capital_alpha_trader",
            current_children=0,
            requested_depth=1,
        )


def test_ceo_contract_enforces_child_limits():
    contract = load_livelihood_loom_contract()
    with pytest.raises(DomainCEOContractError, match="max_children"):
        contract.check_spawn(
            requested_role="field_cartography",
            current_children=contract.max_children,
            requested_depth=1,
        )
    with pytest.raises(DomainCEOContractError, match="max_depth"):
        contract.check_spawn(
            requested_role="field_cartography",
            current_children=0,
            requested_depth=contract.max_depth + 1,
        )


def test_public_payload_rejects_sensitive_or_unknown_fields():
    contract = load_livelihood_loom_contract()
    with pytest.raises(DomainCEOContractError, match="sensitive"):
        contract.data_policy.validate_public_payload(
            {
                "claim_id": "proof_1",
                "cell_id": "livelihood_loom",
                "claim_type": "aggregate_outcome",
                "aggregate_count": 12,
                "sector": "food",
                "region_level": "city",
                "evidence_refs": [],
                "audit_status": "audited",
                "outcome_metric": "income_delta",
                "outcome_value": "positive",
                "time_period": "2026-06",
                "income": "$45/day",
            }
        )
    with pytest.raises(DomainCEOContractError, match="unapproved"):
        contract.data_policy.validate_public_payload({"claim_id": "x", "free_text": "leak"})


def test_provider_green_claim_requires_complete_proof():
    contract = load_livelihood_loom_contract()
    with pytest.raises(DomainCEOContractError, match="provider cannot be green"):
        contract.assert_provider_green(ProviderProof(provider="openrouter", success=True))
    contract.assert_provider_green(
        ProviderProof(
            provider="openrouter",
            model="test/model",
            attempted_at="2026-06-29T00:00:00Z",
            success=True,
            receipt_id="rr_1",
            trace_id="trace_1",
            result_ref="artifact_1",
        )
    )
