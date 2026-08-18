"""Tests for the target registry and the campaign runner (hermetic dry-run)."""

from __future__ import annotations

import json

import pytest

from dharma_swarm.foundry.campaign import CampaignConfig, dry_run_campaign, run_campaign
from dharma_swarm.foundry.target_ingest import TargetSpec
from dharma_swarm.foundry.targets import (
    TARGET_REGISTRY,
    ForbiddenTarget,
    assert_contributable,
    is_forbidden,
)


def test_registry_has_ai_native_first_targets():
    assert "openevolve-mlx" in TARGET_REGISTRY
    assert "flashinfer-bench" in TARGET_REGISTRY
    for spec in TARGET_REGISTRY.values():
        assert spec.ai_policy == "native"
        assert spec.license.startswith("Apache")


def test_do_not_touch_blocks_banned_repos():
    assert is_forbidden("ggml-org/llama.cpp")
    assert is_forbidden("qemu/qemu")
    assert is_forbidden("torvalds/linux")
    assert is_forbidden("openevolve-mlx") is None


def test_assert_contributable_passes_native_targets():
    assert_contributable(TARGET_REGISTRY["openevolve-mlx"])  # no raise


def test_run_campaign_refuses_forbidden_target():
    banned = TargetSpec(
        id="llama", name="llama.cpp", url="https://github.com/ggml-org/llama.cpp",
        sha="x", ai_policy="native",
    )
    with pytest.raises(ForbiddenTarget):
        run_campaign(
            banned, evaluator=None, propose_fn=lambda m, p, s: None,
            heldout_evaluators={},
        )


def test_dry_run_campaign_produces_receipts(tmp_path):
    spec = TARGET_REGISTRY["openevolve-mlx"]
    result = dry_run_campaign(
        spec, config=CampaignConfig(generations=4, per_generation=6), state_root=tmp_path
    )
    assert result.target_id == "openevolve-mlx"
    assert result.generations_run == 4
    assert result.proposed > 0
    assert result.ring1_wins > 0
    assert result.best_fitness > 0
    # ring-2 survivors mint lab-local receipts
    assert result.ring2_survivors == len(result.receipt_ids)
    if result.receipt_ids:
        receipt_file = tmp_path / "receipts" / f"{result.receipt_ids[0]}.json"
        payload = json.loads(receipt_file.read_text())
        assert payload["schema_version"] == "foundry_improvement.v1"
        # lab-local: NOT externally confirmed yet
        assert payload["externally_confirmed"] is False
        assert payload["stratified"]["domain"] == "external_code_contribution"


def test_dry_run_spend_within_budget(tmp_path):
    spec = TARGET_REGISTRY["flashinfer-bench"]
    result = dry_run_campaign(
        spec, config=CampaignConfig(generations=3, budget_cap_usd=300.0), state_root=tmp_path
    )
    assert result.spend_usd <= 300.0
