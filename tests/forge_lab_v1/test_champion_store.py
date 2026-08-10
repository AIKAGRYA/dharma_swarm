from __future__ import annotations

import json

import pytest

from dharma_swarm.forge_lab.campaign_budget import CampaignBudgetLedger
from dharma_swarm.forge_lab.champion_store import (
    ChampionConflict,
    ChampionStore,
    ChampionStoreError,
    build_shadow_champion,
    validate_shadow_champion,
)
from dharma_swarm.forge_lab.genome_spec import merged_with_defaults
from dharma_swarm.forge_lab.ids import candidate_id, content_digest, genome_digest, phenotype_id
from dharma_swarm.forge_lab.paired_evaluation import AGGREGATE_SCHEMA


def _stats(candidate: str, baseline: str, score: float = 0.1) -> dict:
    result = {}
    for split in ("train", "explore", "confirm", "holdout"):
        result[split] = {
            "schema": AGGREGATE_SCHEMA,
            "protocol_sha256": "b" * 64,
            "baseline_candidate_id": baseline,
            "candidate_id": candidate,
            "split": split,
            "complete": True,
            "plan_bound": True,
            "budget_valid": True,
            "selection_eligible": split == "explore",
            "decision_eligible": split in {"confirm", "holdout"},
            "expected_baseline_eval_ids": [f"eval_{split}_baseline"],
            "expected_candidate_eval_ids": [f"eval_{split}_candidate"],
            "expected_eval_ids": [f"eval_{split}_baseline", f"eval_{split}_candidate"],
            "repeat_seeds": [3, 7],
            "seed_support": "unsupported",
            "positive_lift_claimed": False,
            "clustered_ci": {"mean": score, "lower": -0.1, "upper": 0.3},
        }
    return result


def _champion(
    candidate: str | None = None,
    score: float = 0.1,
    baseline: str = "cand_baseline000000",
) -> dict:
    genome = merged_with_defaults(
        {"generator_model": "unit-model", "extra_instruction": candidate or "first"}
    )
    resolved_candidate = candidate_id(genome)
    stats = _stats(resolved_candidate, baseline, score)
    budget = CampaignBudgetLedger(cap_tokens=1_000)
    budget.reserve("mutation", max_tokens=0, operation_id="mutation")
    budget.settle("mutation", actual_tokens=0)
    for split, split_stats in stats.items():
        for eval_id in split_stats["expected_eval_ids"]:
            if split in {"confirm", "holdout"}:
                component = f"{split}_eval"
            elif eval_id in split_stats["expected_baseline_eval_ids"]:
                component = "baseline_eval"
            else:
                component = "candidate_eval"
            budget.reserve(component, max_tokens=10, operation_id=eval_id)
            budget.settle(eval_id, actual_tokens=1)
    return build_shadow_champion(
        category="agent_evolution",
        candidate_id=resolved_candidate,
        phenotype_id=phenotype_id(genome),
        genome=genome,
        genome_sha256=genome_digest(genome),
        experiment_id="exp-unit",
        source_base_sha="abc1234",
        evaluation_plan_sha256="b" * 64,
        baseline_candidate_id=baseline,
        paired_stats=stats,
        repeat_seeds=[3, 7],
        seed_support="unsupported",
        campaign_budget=budget.to_dict(),
        selection_score=score,
        selection_rule="paired_mean_then_tokens_then_candidate_id",
        tie_break={"tokens": 42, "candidate_id": resolved_candidate},
        created_at="2026-08-10T01:00:00Z",
    )


def test_store_persists_atomic_state_history_and_idempotent_retry(tmp_path) -> None:
    store = ChampionStore(tmp_path, category="agent_evolution")
    assert store.load()["revision"] == 0
    champion = _champion()

    state = store.compare_and_swap(expected_revision=0, champion=champion)
    retry = store.compare_and_swap(expected_revision=0, champion=champion)

    assert state == retry
    assert state["revision"] == 1
    assert ChampionStore(tmp_path, category="agent_evolution").load() == state
    history = store.history()
    assert len(history) == 1
    assert history[0]["from_revision"] == 0
    assert history[0]["to_revision"] == 1
    assert history[0]["champion"]["candidate_id"] == champion["candidate_id"]
    assert json.loads(store.state_path.read_text())["state_sha256"] == state["state_sha256"]


def test_stale_campaign_cannot_overwrite_new_incumbent(tmp_path) -> None:
    store = ChampionStore(tmp_path, category="agent_evolution")
    first = _champion()
    store.compare_and_swap(expected_revision=0, champion=first)
    challenger = _champion("third", score=0.2)

    with pytest.raises(ChampionConflict, match="expected=0 actual=1"):
        store.compare_and_swap(expected_revision=0, champion=challenger)

    assert store.load()["champion"]["candidate_id"] == first["candidate_id"]


def test_next_revision_must_be_paired_against_current_incumbent(tmp_path) -> None:
    store = ChampionStore(tmp_path, category="agent_evolution")
    first = _champion()
    store.compare_and_swap(expected_revision=0, champion=first)

    wrong_baseline = _champion("third", score=0.2)
    with pytest.raises(ChampionConflict, match="not paired"):
        store.compare_and_swap(expected_revision=1, champion=wrong_baseline)

    next_champion = _champion(
        "third",
        score=0.2,
        baseline=first["candidate_id"],
    )
    state = store.compare_and_swap(expected_revision=1, champion=next_champion)
    assert state["revision"] == 2
    assert [row["to_revision"] for row in store.history()] == [1, 2]


def test_idempotent_retry_repairs_history_after_state_first_failure(tmp_path, monkeypatch) -> None:
    store = ChampionStore(tmp_path, category="agent_evolution")
    champion = _champion()
    append = store._append_history_row
    monkeypatch.setattr(store, "_append_history_row", lambda row: (_ for _ in ()).throw(OSError("disk")))

    with pytest.raises(OSError, match="disk"):
        store.compare_and_swap(expected_revision=0, champion=champion)
    assert store.load()["revision"] == 1

    monkeypatch.setattr(store, "_append_history_row", append)
    repaired = store.compare_and_swap(expected_revision=0, champion=champion)
    assert repaired["revision"] == 1
    assert len(store.history()) == 1


def test_next_transition_repairs_prior_history_before_advancing(tmp_path, monkeypatch) -> None:
    store = ChampionStore(tmp_path, category="agent_evolution")
    first = _champion()
    append = store._append_history_row
    monkeypatch.setattr(store, "_append_history_row", lambda row: (_ for _ in ()).throw(OSError("disk")))

    with pytest.raises(OSError, match="disk"):
        store.compare_and_swap(expected_revision=0, champion=first)

    monkeypatch.setattr(store, "_append_history_row", append)
    second = _champion("second", score=0.2, baseline=first["candidate_id"])
    state = store.compare_and_swap(expected_revision=1, champion=second)

    assert state["revision"] == 2
    assert [row["to_revision"] for row in store.history()] == [1, 2]


def test_incomplete_or_budget_invalid_evidence_is_rejected() -> None:
    champion = _champion()
    incomplete = json.loads(json.dumps(champion))
    incomplete["paired_stats"]["explore"]["complete"] = False
    with pytest.raises(ChampionStoreError, match="EXPLORE"):
        validate_shadow_champion(incomplete)

    with pytest.raises(ChampionStoreError, match="budget-valid"):
        valid = _champion()
        invalid_budget = CampaignBudgetLedger(cap_tokens=100).to_dict()
        invalid_budget["valid"] = False
        build_shadow_champion(
            category="agent_evolution",
            candidate_id=valid["candidate_id"],
            phenotype_id=valid["phenotype_id"],
            genome=valid["genome"],
            genome_sha256=valid["genome_sha256"],
            experiment_id="exp-unit",
            source_base_sha="abc1234",
            evaluation_plan_sha256="b" * 64,
            baseline_candidate_id="cand_baseline000000",
            paired_stats=valid["paired_stats"],
            repeat_seeds=[1],
            seed_support="unsupported",
            campaign_budget=invalid_budget,
            selection_score=0.0,
            selection_rule="rule",
            tie_break={},
        )


def test_shadow_metadata_cannot_claim_positive_lift_or_production() -> None:
    champion = _champion()
    champion["claims"]["positive_lift_claimed"] = True
    with pytest.raises(ChampionStoreError, match="research-only"):
        validate_shadow_champion(champion)


def test_cancelled_or_wrong_component_eval_cannot_back_champion() -> None:
    champion = _champion()
    target = champion["paired_stats"]["explore"]["expected_baseline_eval_ids"][0]
    wrong_budget = CampaignBudgetLedger(cap_tokens=1_000)
    for row in champion["campaign_budget"]["reservations"]:
        component = "candidate_eval" if row["reservation_id"] == target else row["component"]
        wrong_budget.reserve(
            component,
            max_tokens=row["max_tokens"],
            max_usd=row["max_usd"],
            operation_id=row["reservation_id"],
        )
        wrong_budget.settle(
            row["reservation_id"],
            actual_tokens=row["actual_tokens"],
            actual_usd=row["actual_usd"],
        )
    champion["campaign_budget"] = wrong_budget.to_dict()
    champion_unsigned = dict(champion)
    champion_unsigned.pop("metadata_sha256")
    champion["metadata_sha256"] = content_digest(champion_unsigned)

    with pytest.raises(ChampionStoreError, match="settled budget dispatches"):
        validate_shadow_champion(champion)
