"""Tests for the target registry and the campaign runner (hermetic dry-run)."""

from __future__ import annotations

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
    assert (
        TARGET_REGISTRY["openevolve-circle-packing"].sha
        == "411fb59c886c18704caaffb611e17cf9e7d824d2"
    )


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


def test_dry_run_campaign_blocks_confirmation_receipts_without_isolation_proof(tmp_path):
    spec = TARGET_REGISTRY["openevolve-mlx"]
    result = dry_run_campaign(
        spec, config=CampaignConfig(generations=4, per_generation=6), state_root=tmp_path
    )
    assert result.target_id == "openevolve-mlx"
    assert result.generations_run == 4
    assert result.proposed > 0
    assert result.ring1_wins > 0
    assert result.best_fitness > 0
    # Synthetic evaluators can exercise the search, but cannot coerce their
    # positive score into a ring-2 confirmation receipt.
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


def test_win_floor_blocks_baseline_reproduction(tmp_path):
    # The deepseek-v4-flash-8000 lesson: reproducing the original program
    # (score == baseline) must not mint a receipt.
    from dharma_swarm.foundry.campaign import CampaignConfig, dry_run_campaign
    from dharma_swarm.foundry.targets import T0_OPENEVOLVE_CPU

    # Dry evaluator scores diffs 0.6..2.2; set the floor above the whole range.
    config = CampaignConfig(generations=3, baseline_metric=5.0)
    result = dry_run_campaign(T0_OPENEVOLVE_CPU, config=config, state_root=tmp_path)
    assert result.ring1_wins == 0
    assert result.receipt_ids == []
    # ...and with the floor below the range, wins flow again.
    config2 = CampaignConfig(generations=3, baseline_metric=0.0)
    result2 = dry_run_campaign(T0_OPENEVOLVE_CPU, config=config2, state_root=tmp_path)
    assert result2.ring1_wins > 0


def test_unproven_survivors_cannot_persist_promotion_artifacts(tmp_path):
    from dharma_swarm.foundry.campaign import CampaignConfig, dry_run_campaign
    from dharma_swarm.foundry.targets import T0_OPENEVOLVE_CPU

    result = dry_run_campaign(T0_OPENEVOLVE_CPU,
                              config=CampaignConfig(generations=3),
                              state_root=tmp_path)
    assert result.ring2_promotion_blocked > 0
    assert result.ring2_survivors == 0
    assert result.artifact_paths == []


def test_trip_reasons_aggregated(tmp_path):
    from dharma_swarm.foundry.campaign import CampaignConfig, run_campaign, _dry_evaluator
    from dharma_swarm.foundry.evaluator import Candidate
    from dharma_swarm.foundry.targets import T0_OPENEVOLVE_CPU

    def noop_proposer(model, parent_id, seed):
        return Candidate(candidate_id=f"{model.id}-{seed}",
                         target_id=T0_OPENEVOLVE_CPU.id, diff="",
                         origin_model=model.id)

    result = run_campaign(
        T0_OPENEVOLVE_CPU, _dry_evaluator(), noop_proposer,
        heldout_evaluators={}, config=CampaignConfig(generations=2),
        state_root=tmp_path, isolation_level="hermetic_dry",
    )
    assert result.trip_reasons.get("no_op_diff", 0) == result.proposed
