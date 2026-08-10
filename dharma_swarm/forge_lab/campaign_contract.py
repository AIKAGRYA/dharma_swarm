"""Fail-closed contracts for content-addressed Forge Lab campaigns.

This module deliberately has no provider imports.  Planning may describe an
unpowered campaign with explicit null ceilings, but only a trusted Ed25519
operator envelope can turn exact, manifest-bound ceilings into authority.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFINITION_SCHEMA = "forge_lab.campaign_definition.v1"
MANIFEST_SCHEMA = "forge_lab.campaign_manifest.v1"
ENVELOPE_SCHEMA = "forge_lab.operator_envelope.v1"
CANONICAL_REPOSITORY = "https://github.com/AmitabhainArunachala/dharma_swarm.git"
N30_CAMPAIGN = "forge-lab-n30-to-1000-v1"
N30_RELEASE = "309650d5604768a8c90d987170fccf50af6a0536"
PAIRED_CAMPAIGN = "forge-lab-paired-frozen-v1"

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,95}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_UTC_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

_TOP_KEYS = {
    "schema",
    "campaign_name",
    "source",
    "bootstrap",
    "stages",
    "limits",
    "claims",
    "gates",
}
_TERMINAL_STATES = ["accepted", "rejected", "blocked", "failed", "quarantined"]
_TERMINAL_REQUIREMENTS = [
    "parent_digest",
    "mutation_result",
    "evaluation_digest",
    "accounting",
    "terminal_receipt",
]
_NON_COUNTING = ["retries", "provider_requests", "tasks", "evaluation_replicates"]
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


class CampaignContractError(RuntimeError):
    """A stable, machine-classifiable campaign contract refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON after rejecting non-JSON/NaN values."""

    _validate_json_value(value, "$")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def content_digest(value: Any) -> str:
    return f"sha256:{sha256(canonical_json(value)).hexdigest()}"


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Digest a manifest without its recursive ``manifest_digest`` field."""

    if not isinstance(manifest, Mapping):
        raise CampaignContractError("INVALID_MANIFEST", "manifest must be an object")
    payload = dict(manifest)
    payload.pop("manifest_digest", None)
    return content_digest(payload)


def resolve_state_root(env: Mapping[str, str] | None = None) -> Path:
    """Resolve only canonical RSI Lab state; HOME is intentionally ignored."""

    values = os.environ if env is None else env
    configured = values.get("RSI_LAB_STATE")
    if configured:
        root = Path(configured)
    else:
        base = values.get("RSI_LAB_BASE")
        if not base:
            raise CampaignContractError(
                "STATE_ROOT_UNBOUND",
                "set RSI_LAB_STATE or RSI_LAB_BASE; HOME state is forbidden",
            )
        root = Path(base) / "state"
    if not root.is_absolute():
        raise CampaignContractError(
            "STATE_ROOT_NOT_ABSOLUTE", "canonical RSI Lab state must be absolute"
        )
    return root


def build_manifest(definition: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a strict definition and return its content-addressed manifest."""

    if not isinstance(definition, Mapping):
        raise CampaignContractError("INVALID_DEFINITION", "definition must be an object")
    value = dict(definition)
    _exact_keys(value, _TOP_KEYS, "definition")
    if value["schema"] != DEFINITION_SCHEMA:
        _bad("INVALID_SCHEMA", f"definition.schema must be {DEFINITION_SCHEMA}")
    name = _safe_name(value["campaign_name"], "campaign_name")
    _validate_source(value["source"])
    _validate_bootstrap(value["bootstrap"], campaign_name=name)
    _validate_stages(value["stages"])
    _validate_limits(value["limits"])
    _validate_claims(value["claims"])
    _validate_gates(value["gates"], campaign_name=name)
    from dharma_swarm.forge_lab.campaign_profile_contract import validate_profile_exact

    validate_profile_exact(name, value, _bad)

    manifest = dict(value)
    manifest["schema"] = MANIFEST_SCHEMA
    manifest["definition_schema"] = DEFINITION_SCHEMA
    manifest["manifest_digest"] = manifest_digest(manifest)
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Revalidate a stored manifest and its self-declared digest."""

    if not isinstance(manifest, Mapping):
        raise CampaignContractError("INVALID_MANIFEST", "manifest must be an object")
    value = dict(manifest)
    declared = value.pop("manifest_digest", None)
    definition_schema = value.pop("definition_schema", None)
    if value.get("schema") != MANIFEST_SCHEMA or definition_schema != DEFINITION_SCHEMA:
        _bad("INVALID_SCHEMA", "not a Forge campaign manifest v1")
    value["schema"] = DEFINITION_SCHEMA
    rebuilt = build_manifest(value)
    if declared != rebuilt["manifest_digest"]:
        _bad("MANIFEST_DIGEST_MISMATCH", "manifest bytes do not match declared digest")
    return dict(manifest)


def verify_operator_envelope(
    envelope: Mapping[str, Any] | str | None,
    manifest: Mapping[str, Any],
    *,
    trusted_public_keys: Mapping[str, str | bytes] | Iterable[str | bytes],
    expected_host: str,
    now: datetime | str | None = None,
) -> dict[str, Any]:
    """Verify a manifest-bound envelope without importing providers."""
    from .campaign_envelope import verify_operator_envelope as verify

    return verify(
        envelope,
        manifest,
        trusted_public_keys=trusted_public_keys,
        expected_host=expected_host,
        now=now,
    )


def _validate_source(value: Any) -> None:
    keys = {
        "repository",
        "release_commit",
        "release_tree",
        "required_identity_hosts",
        "bootstrap_prior",
    }
    _exact_keys(value, keys, "source")
    if value["repository"] != CANONICAL_REPOSITORY:
        _bad("INVALID_SOURCE", "source repository is not canonical")
    _hex40(value["release_commit"], "source.release_commit")
    _hex40(value["release_tree"], "source.release_tree")
    if value["required_identity_hosts"] != ["github", "mac", "meghadharma"]:
        _bad("INVALID_SOURCE", "all three canonical identity hosts are required")
    prior = value["bootstrap_prior"]
    _exact_keys(
        prior,
        {
            "run_id",
            "type",
            "metric",
            "generation",
            "budget_valid_rows",
            "budget_total_rows",
            "complete_receipts",
            "evidence_scope",
        },
        "source.bootstrap_prior",
    )


def _validate_bootstrap(value: Any, *, campaign_name: str) -> None:
    common = {
        "children",
        "tasks_per_generation",
        "novelty_pressure",
        "per_candidate_token_ceiling",
        "rng_seed",
    }
    if campaign_name == N30_CAMPAIGN:
        _exact_keys(
            value,
            common | {"solver_model", "verifier_model", "mutator_model"},
            "bootstrap",
        )
    else:
        _exact_keys(
            value,
            common | {"role_routes", "evaluation_protocol", "paired_design"},
            "bootstrap",
        )
    for field in ("children", "tasks_per_generation", "per_candidate_token_ceiling"):
        _positive_int(value[field], f"bootstrap.{field}")
    if not isinstance(value["novelty_pressure"], (int, float)) or isinstance(
        value["novelty_pressure"], bool
    ):
        _bad("INVALID_BOOTSTRAP", "novelty_pressure must be numeric")
    if not math.isfinite(float(value["novelty_pressure"])):
        _bad("INVALID_BOOTSTRAP", "novelty_pressure must be finite")
    if not isinstance(value["rng_seed"], int) or isinstance(value["rng_seed"], bool):
        _bad("INVALID_BOOTSTRAP", "rng_seed must be an integer")
    if campaign_name == N30_CAMPAIGN:
        for role in ("solver_model", "verifier_model", "mutator_model"):
            if not isinstance(value[role], str) or not value[role]:
                _bad("INVALID_BOOTSTRAP", f"{role} must be a model route string")
        return

    routes = value["role_routes"]
    _exact_keys(routes, {"solver", "verifier", "mutator"}, "bootstrap.role_routes")
    for role, route in routes.items():
        if not isinstance(route, str) or not re.fullmatch(r"forge\.[a-z0-9_.-]+", route):
            _bad(
                "INVALID_BOOTSTRAP",
                f"bootstrap.role_routes.{role} must be a governed semantic route",
            )
    if value["evaluation_protocol"] != "paired_frozen_v1":
        _bad("INVALID_BOOTSTRAP", "paired campaign protocol must be paired_frozen_v1")
    design = value["paired_design"]
    _exact_keys(
        design,
        {
            "logical_splits",
            "tasks_per_split",
            "repeat_seeds",
            "bootstrap_samples",
            "min_decision_tasks",
            "baseline_policy",
            "winner_policy",
        },
        "bootstrap.paired_design",
    )
    if design["logical_splits"] != ["train", "explore", "confirm", "holdout"]:
        _bad("INVALID_BOOTSTRAP", "paired logical splits must remain four-way and frozen")
    for field in ("tasks_per_split", "bootstrap_samples", "min_decision_tasks"):
        _positive_int(design[field], f"bootstrap.paired_design.{field}")
    seeds = design["repeat_seeds"]
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        _bad("INVALID_BOOTSTRAP", "paired repeat seeds must be unique integers")
    if design["min_decision_tasks"] > design["tasks_per_split"]:
        _bad("INVALID_BOOTSTRAP", "paired decision minimum exceeds tasks per split")
    if design["baseline_policy"] != "frozen_before_dispatch":
        _bad("INVALID_BOOTSTRAP", "paired baseline must freeze before dispatch")
    if design["winner_policy"] != "explore_select_confirm_holdout_once":
        _bad("INVALID_BOOTSTRAP", "paired winner policy is not confirm/holdout safe")


def _validate_stages(value: Any) -> None:
    _exact_keys(value, {"canary", "n30_reproduction", "primary"}, "stages")
    for name in ("canary", "n30_reproduction"):
        _exact_keys(
            value[name],
            {"primary_attempts", "required_closeout_digest"},
            f"stages.{name}",
        )
        _positive_int(value[name]["primary_attempts"], f"stages.{name}.primary_attempts")
        digest = value[name]["required_closeout_digest"]
        if digest is not None and not _DIGEST_RE.fullmatch(str(digest)):
            _bad("INVALID_STAGE", f"stages.{name}.required_closeout_digest is invalid")
    primary = value["primary"]
    _exact_keys(
        primary,
        {
            "primary_attempts",
            "seed_counts_as_attempt",
            "terminal_states",
            "terminal_requirements",
            "non_counting",
        },
        "stages.primary",
    )
    _positive_int(primary["primary_attempts"], "stages.primary.primary_attempts")
    if not isinstance(primary["seed_counts_as_attempt"], bool):
        _bad("INVALID_STAGE", "seed_counts_as_attempt must be boolean")
    if primary["terminal_states"] != _TERMINAL_STATES:
        _bad("INVALID_STAGE", "terminal states do not match the v1 contract")
    if primary["terminal_requirements"] != _TERMINAL_REQUIREMENTS:
        _bad("INVALID_STAGE", "terminal requirements do not match the v1 contract")
    if primary["non_counting"] != _NON_COUNTING:
        _bad("INVALID_STAGE", "non-counting work classes do not match the v1 contract")


def _validate_limits(value: Any) -> None:
    fields = {
        "total_tokens",
        "total_usd_micros",
        "total_requests",
        "deadline_utc",
        "host_caps",
    }
    _exact_keys(value, fields, "limits")
    for field in ("total_tokens", "total_usd_micros", "total_requests"):
        if value[field] is not None:
            _positive_int(value[field], f"limits.{field}")
    if value["deadline_utc"] is not None:
        _parse_utc(value["deadline_utc"], "limits.deadline_utc")
    caps = value["host_caps"]
    if caps is not None:
        if not isinstance(caps, Mapping) or not caps or not isinstance(caps.get("host"), str):
            _bad("INVALID_LIMITS", "host_caps must be a nonempty object with host")
        _validate_json_value(caps, "limits.host_caps")


def _validate_claims(value: Any) -> None:
    _exact_keys(
        value,
        {"mode", "evidence_class", "bootstrap_prior_is_fitness_evidence", "forbidden"},
        "claims",
    )
    if value["mode"] != "shadow" or value["evidence_class"] != "EXPLORE":
        _bad("INVALID_CLAIM_BOUNDARY", "campaign must remain shadow EXPLORE")
    if value["bootstrap_prior_is_fitness_evidence"] is not False:
        _bad("INVALID_CLAIM_BOUNDARY", "bootstrap prior cannot be fitness evidence")
    if value["forbidden"] != [
        "positive_lift",
        "recursive_self_improvement",
        "promotion",
        "production_fitness",
    ]:
        _bad("INVALID_CLAIM_BOUNDARY", "forbidden claims are incomplete")


def _validate_gates(value: Any, *, campaign_name: str) -> None:
    common = {
        "operator_envelope_required",
        "canonical_state_required",
        "code_identity_hosts",
        "lifecycle_required",
    }
    if campaign_name == N30_CAMPAIGN:
        _exact_keys(value, common | {"exact_route"}, "gates")
    else:
        _exact_keys(value, common | {"provider_attestation"}, "gates")
    if value["operator_envelope_required"] is not True:
        _bad("INVALID_GATE", "operator envelope must be required")
    if campaign_name == N30_CAMPAIGN:
        if not isinstance(value["exact_route"], str) or not value["exact_route"]:
            _bad("INVALID_GATE", "historical campaign requires an exact route")
    else:
        attestation = value["provider_attestation"]
        _exact_keys(
            attestation,
            {
                "required_roles",
                "min_independent_transports",
                "max_age_seconds",
                "required_probe_authority",
            },
            "gates.provider_attestation",
        )
        if attestation["required_roles"] != ["solver", "verifier", "mutator"]:
            _bad("INVALID_GATE", "provider attestation must cover every execution role")
        if _positive_int(
            attestation["min_independent_transports"],
            "gates.provider_attestation.min_independent_transports",
        ) < 2:
            _bad(
                "INVALID_GATE",
                "unattended campaigns require two independent transports",
            )
        max_age = _positive_int(
            attestation["max_age_seconds"],
            "gates.provider_attestation.max_age_seconds",
        )
        if max_age > 3600:
            _bad("INVALID_GATE", "provider attestation cannot be older than one hour")
        if attestation["required_probe_authority"] != "rsi-lab-provider-probe-v1":
            _bad("INVALID_GATE", "provider probe authority is not the governed broker")
    if value["canonical_state_required"] is not True:
        _bad("INVALID_GATE", "canonical state must be required")
    if value["code_identity_hosts"] != ["github", "mac", "meghadharma"]:
        _bad("INVALID_GATE", "three-way code identity is required")
    if value["lifecycle_required"] != _LIFECYCLE:
        _bad("INVALID_GATE", "complete governed lifecycle proof is required")


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _bad("NON_CANONICAL_JSON", f"{path} contains NaN or infinity")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _bad("NON_CANONICAL_JSON", f"{path} has a non-string key")
            _validate_json_value(item, f"{path}.{key}")
        return
    _bad("NON_CANONICAL_JSON", f"{path} contains unsupported type {type(value).__name__}")


def _exact_keys(value: Any, keys: set[str], path: str) -> None:
    if not isinstance(value, Mapping):
        _bad("INVALID_SHAPE", f"{path} must be an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        _bad("INVALID_SHAPE", f"{path} missing={missing} unknown={unknown}")


def _positive_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _bad("INVALID_INTEGER", f"{path} must be a positive integer")
    return value


def _safe_name(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.fullmatch(value):
        _bad("INVALID_NAME", f"{path} must be a safe lowercase campaign name")
    return value


def _hex40(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _HEX40_RE.fullmatch(value):
        _bad("INVALID_SOURCE", f"{path} must be a lowercase 40-character Git object")
    return value


def _parse_utc(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not _UTC_RE.fullmatch(value):
        _bad("INVALID_TIMESTAMP", f"{path} must be second-precision RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CampaignContractError("INVALID_TIMESTAMP", f"{path} is invalid") from exc


def _bad(code: str, message: str) -> None:
    raise CampaignContractError(code, message)
