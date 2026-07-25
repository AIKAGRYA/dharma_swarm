"""Immutable definition for the governed n30-to-1000 campaign.

The null cumulative limits are deliberate.  The operator supplied a signed
envelope placeholder, not exact spend authority, so planning records the
request without inventing token, money, request, deadline, or host ceilings.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PROFILE = "forge-lab-n30-to-1000-v1"
CANONICAL_COMMIT = "309650d5604768a8c90d987170fccf50af6a0536"
CANONICAL_TREE = "9648611c3522be11aa69a11c590dd4d06afaec3a"
MOONSHOT_MODEL = "moonshot:kimi-k2.7-code"


_DEFINITION: dict[str, Any] = {
    "schema": "forge_lab.campaign_definition.v1",
    "campaign_name": PROFILE,
    "source": {
        "repository": "https://github.com/AmitabhainArunachala/dharma_swarm.git",
        "release_commit": CANONICAL_COMMIT,
        "release_tree": CANONICAL_TREE,
        "required_identity_hosts": ["github", "mac", "meghadharma"],
        "bootstrap_prior": {
            "run_id": "rsi-n30-20260718T131907Z",
            "type": "MostEvolvedBy",
            "metric": "maximum_generation",
            "generation": 30,
            "budget_valid_rows": 31,
            "budget_total_rows": 31,
            "complete_receipts": True,
            "evidence_scope": "bootstrap_prior_only",
        },
    },
    "bootstrap": {
        "children": 1,
        "tasks_per_generation": 3,
        "novelty_pressure": 0.7,
        "solver_model": MOONSHOT_MODEL,
        "verifier_model": MOONSHOT_MODEL,
        "mutator_model": MOONSHOT_MODEL,
        "per_candidate_token_ceiling": 300_000,
        "rng_seed": 20_260_706,
    },
    "stages": {
        "canary": {
            "primary_attempts": 1,
            "required_closeout_digest": None,
        },
        "n30_reproduction": {
            "primary_attempts": 30,
            "required_closeout_digest": None,
        },
        "primary": {
            "primary_attempts": 1_000,
            "seed_counts_as_attempt": False,
            "terminal_states": [
                "accepted",
                "rejected",
                "blocked",
                "failed",
                "quarantined",
            ],
            "terminal_requirements": [
                "parent_digest",
                "mutation_result",
                "evaluation_digest",
                "accounting",
                "terminal_receipt",
            ],
            "non_counting": [
                "retries",
                "provider_requests",
                "tasks",
                "evaluation_replicates",
            ],
        },
    },
    "limits": {
        "total_tokens": None,
        "total_usd_micros": None,
        "total_requests": None,
        "deadline_utc": None,
        "host_caps": None,
    },
    "claims": {
        "mode": "shadow",
        "evidence_class": "EXPLORE",
        "bootstrap_prior_is_fitness_evidence": False,
        "forbidden": [
            "positive_lift",
            "recursive_self_improvement",
            "promotion",
            "production_fitness",
        ],
    },
    "gates": {
        "operator_envelope_required": True,
        "exact_route": MOONSHOT_MODEL,
        "canonical_state_required": True,
        "code_identity_hosts": ["github", "mac", "meghadharma"],
        "lifecycle_required": [
            "plan",
            "run",
            "status",
            "progress",
            "pause",
            "resume",
            "stop",
            "checkpoint",
            "idempotent_resume",
            "external_watchdog",
            "reconcile",
            "cleanup",
        ],
    },
}


def campaign_definition(profile: str) -> dict[str, Any]:
    """Return a defensive copy of the only implemented governed profile."""

    if profile != PROFILE:
        raise ValueError(f"unsupported governed campaign profile: {profile!r}")
    return deepcopy(_DEFINITION)
