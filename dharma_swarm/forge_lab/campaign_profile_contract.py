"""Exact invariants for versioned Forge Lab campaign profiles."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


Bad = Callable[[str, str], None]


def validate_n30_exact(value: Mapping[str, Any], bad: Bad) -> None:
    source, bootstrap, stages, gates = (
        value["source"],
        value["bootstrap"],
        value["stages"],
        value["gates"],
    )
    if source["release_commit"] != "309650d5604768a8c90d987170fccf50af6a0536":
        bad("INVALID_N30_PROFILE", "campaign release commit is not canonical")
    if source["bootstrap_prior"] != {
        "run_id": "rsi-n30-20260718T131907Z",
        "type": "MostEvolvedBy",
        "metric": "maximum_generation",
        "generation": 30,
        "budget_valid_rows": 31,
        "budget_total_rows": 31,
        "complete_receipts": True,
        "evidence_scope": "bootstrap_prior_only",
    }:
        bad("INVALID_N30_PROFILE", "historical prior is not properly bounded")
    if bootstrap != {
        "children": 1,
        "tasks_per_generation": 3,
        "novelty_pressure": 0.7,
        "solver_model": "moonshot:kimi-k2.7-code",
        "verifier_model": "moonshot:kimi-k2.7-code",
        "mutator_model": "moonshot:kimi-k2.7-code",
        "per_candidate_token_ceiling": 300000,
        "rng_seed": 20260706,
    }:
        bad("INVALID_N30_PROFILE", "bootstrap reproducibility inputs drifted")
    if stages["canary"]["primary_attempts"] != 1:
        bad("INVALID_N30_PROFILE", "canary must contain one primary attempt")
    if stages["n30_reproduction"]["primary_attempts"] != 30:
        bad("INVALID_N30_PROFILE", "n30 reproduction must contain 30 attempts")
    if stages["primary"]["primary_attempts"] != 1000:
        bad("INVALID_N30_PROFILE", "primary campaign must contain 1000 attempts")
    if stages["primary"]["seed_counts_as_attempt"] is not False:
        bad("INVALID_N30_PROFILE", "seed baseline cannot count as an attempt")
    if gates["exact_route"] != "moonshot:kimi-k2.7-code":
        bad("INVALID_N30_PROFILE", "exact Moonshot route gate is required")


def validate_paired_exact(value: Mapping[str, Any], bad: Bad) -> None:
    source, bootstrap, stages, gates = (
        value["source"],
        value["bootstrap"],
        value["stages"],
        value["gates"],
    )
    if source["bootstrap_prior"] != {
        "run_id": "none",
        "type": "NoHistoricalFitnessPrior",
        "metric": "paired_task_cluster_delta",
        "generation": 0,
        "budget_valid_rows": 0,
        "budget_total_rows": 0,
        "complete_receipts": False,
        "evidence_scope": "no_fitness_prior",
    }:
        bad("INVALID_PAIRED_PROFILE", "paired profile cannot import a fitness prior")
    if bootstrap != {
        "children": 3,
        "tasks_per_generation": 3,
        "novelty_pressure": 0.7,
        "role_routes": {
            "solver": "forge.high_slot.solver",
            "verifier": "forge.high_slot.verifier",
            "mutator": "forge.high_slot.mutator",
        },
        "evaluation_protocol": "paired_frozen_v1",
        "paired_design": {
            "logical_splits": ["train", "explore", "confirm", "holdout"],
            "tasks_per_split": 3,
            "repeat_seeds": [104729, 130363, 155921],
            "bootstrap_samples": 2000,
            "min_decision_tasks": 3,
            "baseline_policy": "frozen_before_dispatch",
            "winner_policy": "explore_select_confirm_holdout_once",
        },
        "per_candidate_token_ceiling": 300000,
        "rng_seed": 20260810,
    }:
        bad("INVALID_PAIRED_PROFILE", "paired scientific design drifted")
    if stages["canary"]["primary_attempts"] != 1:
        bad("INVALID_PAIRED_PROFILE", "paired canary must contain one attempt")
    if stages["n30_reproduction"]["primary_attempts"] != 30:
        bad("INVALID_PAIRED_PROFILE", "paired calibration must contain 30 attempts")
    if stages["primary"]["primary_attempts"] != 1000:
        bad("INVALID_PAIRED_PROFILE", "paired target must contain 1000 attempts")
    if stages["primary"]["seed_counts_as_attempt"] is not False:
        bad("INVALID_PAIRED_PROFILE", "paired baseline cannot count as an attempt")
    if gates["provider_attestation"] != {
        "required_roles": ["solver", "verifier", "mutator"],
        "min_independent_transports": 2,
        "max_age_seconds": 300,
        "required_probe_authority": "rsi-lab-provider-probe-v1",
    }:
        bad("INVALID_PAIRED_PROFILE", "provider attestation policy drifted")


def validate_profile_exact(name: str, value: Mapping[str, Any], bad: Bad) -> None:
    if name == "forge-lab-n30-to-1000-v1":
        validate_n30_exact(value, bad)
    elif name == "forge-lab-paired-frozen-v1":
        validate_paired_exact(value, bad)
