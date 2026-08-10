"""Versioned governed campaign definitions.

The historical n30 profile is immutable and retains its exact Moonshot route.
The paired profile is release-relative: planning binds it to the clean Git
commit and tree that contain the controller, so source identity is never a
self-referential constant baked into that controller.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from dharma_swarm.forge_lab.version import SOURCE_CHECKOUT


PROFILE = "forge-lab-n30-to-1000-v1"
PAIRED_PROFILE = "forge-lab-paired-frozen-v1"
SUPPORTED_PROFILES = (PROFILE, PAIRED_PROFILE)
CANONICAL_COMMIT = "309650d5604768a8c90d987170fccf50af6a0536"
CANONICAL_TREE = "9648611c3522be11aa69a11c590dd4d06afaec3a"
MOONSHOT_MODEL = "moonshot:kimi-k2.7-code"
ROLE_ROUTE_BINDINGS = {
    "solver": "forge.high_slot.solver",
    "verifier": "forge.high_slot.verifier",
    "mutator": "forge.high_slot.mutator",
}
PROVIDER_ATTESTATION_POLICY = {
    "required_roles": list(ROLE_ROUTE_BINDINGS),
    "min_independent_transports": 2,
    "max_age_seconds": 300,
    "required_probe_authority": "rsi-lab-provider-probe-v1",
}

_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = "https://github.com/AmitabhainArunachala/dharma_swarm.git"
_IDENTITY_HOSTS = ["github", "mac", "meghadharma"]
_LIFECYCLE = [
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
]
_TERMINAL_STATES = ["accepted", "rejected", "blocked", "failed", "quarantined"]
_TERMINAL_REQUIREMENTS = [
    "parent_digest",
    "mutation_result",
    "evaluation_digest",
    "accounting",
    "terminal_receipt",
]
_NON_COUNTING = ["retries", "provider_requests", "tasks", "evaluation_replicates"]


class ReleaseIdentityError(ValueError):
    """A paired campaign cannot prove a clean immutable source release."""

    code = "CLEAN_RELEASE_IDENTITY_UNPROVEN"


def _git_output(checkout: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(checkout), *arguments],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReleaseIdentityError(
            f"cannot inspect source release: {type(exc).__name__}"
        ) from exc
    if result.returncode != 0:
        raise ReleaseIdentityError("Git could not prove source release identity")
    return result.stdout.strip()


def resolve_clean_release_identity(
    checkout: Path | None = None,
) -> dict[str, str]:
    """Return the clean checkout's immutable commit/tree pair or refuse."""

    source = (checkout or SOURCE_CHECKOUT).resolve()
    status_before = _git_output(
        source,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
    )
    if status_before:
        raise ReleaseIdentityError(
            "paired campaign planning requires a clean committed source tree"
        )
    commit = _git_output(source, "rev-parse", "--verify", "HEAD")
    tree = _git_output(source, "rev-parse", "--verify", f"{commit}^{{tree}}")
    status_after = _git_output(
        source,
        "status",
        "--porcelain=v1",
        "--untracked-files=normal",
    )
    commit_after = _git_output(source, "rev-parse", "--verify", "HEAD")
    if status_after or commit_after != commit:
        raise ReleaseIdentityError("source release changed while it was being bound")
    if not _HEX40_RE.fullmatch(commit) or not _HEX40_RE.fullmatch(tree):
        raise ReleaseIdentityError("Git returned a malformed release identity")
    return {
        "commit": commit,
        "tree": tree,
        "tree_state": "clean",
        "checkout": str(source),
    }


def _release_pair(identity: Mapping[str, Any]) -> tuple[str, str]:
    commit = str(identity.get("commit") or "")
    tree = str(identity.get("tree") or "")
    if (
        identity.get("tree_state") != "clean"
        or not _HEX40_RE.fullmatch(commit)
        or not _HEX40_RE.fullmatch(tree)
    ):
        raise ReleaseIdentityError(
            "paired campaign source must be a clean immutable Git commit/tree pair"
        )
    return commit, tree


_N30_DEFINITION: dict[str, Any] = {
    "schema": "forge_lab.campaign_definition.v1",
    "campaign_name": PROFILE,
    "source": {
        "repository": _REPOSITORY,
        "release_commit": CANONICAL_COMMIT,
        "release_tree": CANONICAL_TREE,
        "required_identity_hosts": list(_IDENTITY_HOSTS),
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
        "canary": {"primary_attempts": 1, "required_closeout_digest": None},
        "n30_reproduction": {
            "primary_attempts": 30,
            "required_closeout_digest": None,
        },
        "primary": {
            "primary_attempts": 1_000,
            "seed_counts_as_attempt": False,
            "terminal_states": list(_TERMINAL_STATES),
            "terminal_requirements": list(_TERMINAL_REQUIREMENTS),
            "non_counting": list(_NON_COUNTING),
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
        "code_identity_hosts": list(_IDENTITY_HOSTS),
        "lifecycle_required": list(_LIFECYCLE),
    },
}


def _paired_definition(release_commit: str, release_tree: str) -> dict[str, Any]:
    return {
        "schema": "forge_lab.campaign_definition.v1",
        "campaign_name": PAIRED_PROFILE,
        "source": {
            "repository": _REPOSITORY,
            "release_commit": release_commit,
            "release_tree": release_tree,
            "required_identity_hosts": list(_IDENTITY_HOSTS),
            "bootstrap_prior": {
                "run_id": "none",
                "type": "NoHistoricalFitnessPrior",
                "metric": "paired_task_cluster_delta",
                "generation": 0,
                "budget_valid_rows": 0,
                "budget_total_rows": 0,
                "complete_receipts": False,
                "evidence_scope": "no_fitness_prior",
            },
        },
        "bootstrap": {
            "children": 3,
            "tasks_per_generation": 3,
            "novelty_pressure": 0.7,
            "role_routes": deepcopy(ROLE_ROUTE_BINDINGS),
            "evaluation_protocol": "paired_frozen_v1",
            "paired_design": {
                "logical_splits": ["train", "explore", "confirm", "holdout"],
                "tasks_per_split": 3,
                "repeat_seeds": [104729, 130363, 155921],
                "bootstrap_samples": 2_000,
                "min_decision_tasks": 3,
                "baseline_policy": "frozen_before_dispatch",
                "winner_policy": "explore_select_confirm_holdout_once",
            },
            "per_candidate_token_ceiling": 300_000,
            "rng_seed": 20_260_810,
        },
        # The controller currently retains its proven staged lifecycle and
        # durable receipt schema. These are targets, never spend authority.
        "stages": {
            "canary": {"primary_attempts": 1, "required_closeout_digest": None},
            "n30_reproduction": {
                "primary_attempts": 30,
                "required_closeout_digest": None,
            },
            "primary": {
                "primary_attempts": 1_000,
                "seed_counts_as_attempt": False,
                "terminal_states": list(_TERMINAL_STATES),
                "terminal_requirements": list(_TERMINAL_REQUIREMENTS),
                "non_counting": list(_NON_COUNTING),
            },
        },
        # Planning is deliberately unpowered. A separate, exact, manifest-bound
        # operator envelope is required before any non-null authority can exist.
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
            "provider_attestation": deepcopy(PROVIDER_ATTESTATION_POLICY),
            "canonical_state_required": True,
            "code_identity_hosts": list(_IDENTITY_HOSTS),
            "lifecycle_required": list(_LIFECYCLE),
        },
    }


def campaign_definition(
    profile: str,
    *,
    release_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a defensive, profile-aware campaign definition.

    ``release_identity`` is an explicit test seam. Production planning never
    supplies it and therefore must prove the live checkout is clean.
    """

    if profile == PROFILE:
        return deepcopy(_N30_DEFINITION)
    if profile == PAIRED_PROFILE:
        identity = release_identity or resolve_clean_release_identity()
        commit, tree = _release_pair(identity)
        return _paired_definition(commit, tree)
    choices = ", ".join(repr(item) for item in SUPPORTED_PROFILES)
    raise ValueError(f"unsupported governed campaign profile {profile!r}; choose {choices}")


def with_exact_limits(
    definition: Mapping[str, Any],
    limits: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply a complete operator-proposed ceiling set without authorizing it."""

    result = deepcopy(dict(definition))
    if limits is None:
        return result
    if result.get("campaign_name") != PAIRED_PROFILE:
        raise ValueError("historical n30 profile limits are immutable")
    required = {
        "total_tokens",
        "total_usd_micros",
        "total_requests",
        "deadline_utc",
        "host_caps",
    }
    if set(limits) != required or any(limits[field] is None for field in required):
        raise ValueError("exact paired limits must provide every non-null ceiling")
    result["limits"] = deepcopy(dict(limits))
    return result
