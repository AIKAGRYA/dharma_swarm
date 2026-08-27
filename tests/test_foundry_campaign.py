"""Tests for the target registry and the campaign runner (hermetic dry-run)."""

from __future__ import annotations

import pytest

from dharma_swarm.foundry.campaign import (
    CampaignConfig,
    _dry_evaluator,
    dry_run_campaign,
    run_campaign,
)
from dharma_swarm.foundry.evaluator import Candidate
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


def test_dry_run_campaign_blocks_confirmation_without_isolation_proof(tmp_path):
    spec = TARGET_REGISTRY["openevolve-mlx"]
    result = dry_run_campaign(
        spec, config=CampaignConfig(generations=4, per_generation=6), state_root=tmp_path
    )
    assert result.target_id == "openevolve-mlx"
    assert result.generations_run == 4
    assert result.proposed > 0
    assert result.ring1_wins > 0
    assert result.best_fitness > 0
    # Synthetic evaluators can exercise search, but cannot coerce a positive
    # score into a promotion or confirmation receipt.
    assert result.ring2_survivors == 0
    assert result.ring2_promotion_blocked > 0
    assert result.receipt_ids == []
    assert not (tmp_path / "receipts").exists()


def test_dry_run_spend_within_budget(tmp_path):
    spec = TARGET_REGISTRY["flashinfer-bench"]
    result = dry_run_campaign(
        spec, config=CampaignConfig(generations=3, budget_cap_usd=300.0), state_root=tmp_path
    )
    assert result.spend_usd <= 300.0


def test_campaign_requires_improvement_over_measured_baseline(tmp_path):
    spec = TARGET_REGISTRY["openevolve-mlx"]
    blocked = dry_run_campaign(
        spec,
        config=CampaignConfig(generations=3, baseline_metric=5.0),
        state_root=tmp_path,
    )
    assert blocked.ring1_wins == 0
    assert blocked.receipt_ids == []

    exploring = dry_run_campaign(
        spec,
        config=CampaignConfig(generations=3, baseline_metric=0.0),
        state_root=tmp_path,
    )
    assert exploring.ring1_wins > 0


def test_campaign_aggregates_typed_trip_reasons(tmp_path):
    spec = TARGET_REGISTRY["openevolve-mlx"]

    def noop_proposer(model, parent_id, seed):
        return Candidate(
            candidate_id=f"{model.id}-{seed}",
            target_id=spec.id,
            diff="",
            origin_model=model.id,
            parent_id=parent_id,
        )

    result = run_campaign(
        spec,
        _dry_evaluator(),
        noop_proposer,
        heldout_evaluators={},
        config=CampaignConfig(generations=2),
        state_root=tmp_path,
    )
    assert result.trip_reasons.get("no_op_diff", 0) == result.proposed
    assert result.ring1_wins == 0
