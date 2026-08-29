"""Provider-route selftest for Forge/RSI Lab high-slot runs.

The command has two levels:

* config mode (default): resolves the candidate model ids without calling any
  provider. This is safe for CI and cheap operator inspection.
* live mode (``--live``): sends a tiny exact-identity probe through each route
  until the requested number of independent callable families is reached, then
  writes a redacted receipt under the lab state directory.

No secret values are printed or persisted. A callable row means the provider
returned non-empty content and the served model identity matched the requested
route according to the Forge runner's exact-route probe.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from dharma_swarm.forge_lab.newrun import (
    DEFAULT_DIVERSE_MUTATOR,
    DEFAULT_DIVERSE_SOLVER,
    DEFAULT_DIVERSE_VERIFIER,
    DEFAULT_FAST_MUTATOR,
    DEFAULT_FAST_SOLVER,
    DEFAULT_FAST_VERIFIER,
    _family,
)
from dharma_swarm.forge_lab.provider_receipt_policy import (
    ALIAS_POLICY_VERSION as ALIAS_POLICY_VERSION,
    PROVIDER_SELFTEST_SCHEMA as PROVIDER_SELFTEST_SCHEMA,
    _authorized_successor_alias,
    _config_row,
    _latest_compatible_receipt,
    _policy_payload,
    _receipt_digest as _receipt_digest,
    _receipt_root as _receipt_root,
    _write_live_receipt,
    validate_provider_receipt as validate_provider_receipt,
)
from dharma_swarm.forge_lab.state_io import content_digest

DEFAULT_PROFILE = "frontier"
STAGED_FALLBACK_MODELS = (DEFAULT_FAST_VERIFIER, DEFAULT_DIVERSE_SOLVER)


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = (item or "").strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def profile_model_ids(profile: str, *, current_model: str | None = None) -> list[str]:
    """Return ordered model ids for a provider selftest profile."""

    profile = (profile or DEFAULT_PROFILE).strip().lower()
    current = (current_model or "").strip()
    fast = [DEFAULT_FAST_SOLVER, DEFAULT_FAST_VERIFIER, DEFAULT_FAST_MUTATOR]
    diverse = [DEFAULT_DIVERSE_SOLVER, DEFAULT_DIVERSE_VERIFIER, DEFAULT_DIVERSE_MUTATOR]
    if profile in {"fast", "offline"}:
        return _dedupe(fast)
    if profile == "staged":
        # An explicit process-local override remains useful for bounded probes.
        # Otherwise consume the active, state-owned role profile.  The final
        # fallback is a source-reviewed two-provider pair so a fresh host can
        # establish evidence before its first activation; it grants no role or
        # run authority by itself.
        override = _dedupe(os.environ.get("RSI_LAB_STAGED_MODELS", "").split(","))
        if override:
            return override
        try:
            from dharma_swarm.forge_lab.model_onboarding import activation_status

            activation = activation_status()
        except Exception:
            activation = {}
        if activation.get("active") and activation.get("staged_models"):
            return _dedupe(list(activation["staged_models"]))
        return list(STAGED_FALLBACK_MODELS)
    if profile in {"current", "newrun"}:
        return _dedupe(([current] if current else []) + fast + diverse)
    if profile == "frontier":
        try:
            from dharma_swarm.model_pool import forge_high_slot_model_ids

            high_slots = list(forge_high_slot_model_ids())
        except Exception:
            high_slots = []
        return _dedupe(fast + diverse + high_slots)
    raise ValueError(
        f"unknown provider selftest profile {profile!r}; "
        "choose staged, frontier, fast, current, newrun, or offline"
    )


def _model_selection_context(
    profile: str,
    *,
    requested_models: list[str],
) -> dict[str, Any]:
    """Describe the authority that selected a profile's exact model IDs.

    This context is part of the live probe policy digest.  Changing only role
    assignments therefore invalidates a cached receipt even when the set of
    model IDs happens to remain identical.
    """

    if (profile or "").strip().casefold() != "staged":
        return {"source": "source_profile"}
    override = _dedupe(os.environ.get("RSI_LAB_STAGED_MODELS", "").split(","))
    if override and override == requested_models:
        return {
            "source": "environment_override",
            "activation_profile_digest": None,
            "role_bindings": [],
        }
    try:
        from dharma_swarm.forge_lab.model_onboarding import activation_status

        activation = activation_status()
    except Exception:
        activation = {}
    if (
        activation.get("active")
        and _dedupe(list(activation.get("staged_models") or [])) == requested_models
    ):
        return {
            "source": "active_model_role_profile",
            "activation_profile_digest": activation.get("current_profile_digest"),
            "role_bindings": activation.get("role_bindings") or [],
        }
    if requested_models == list(STAGED_FALLBACK_MODELS):
        return {
            "source": "source_reviewed_bootstrap_fallback",
            "activation_profile_digest": None,
            "role_bindings": [],
        }
    # This can occur in tests or an embedding that overrides the resolver.  It
    # is truthfully bound but cannot authorize unattended role consumption.
    return {
        "source": "custom_profile_resolver",
        "activation_profile_digest": None,
        "role_bindings": [],
    }


def _live_row(
    model_id: str,
    *,
    timeout_s: int,
    remaining_probe_calls: int,
) -> dict[str, Any]:
    from dharma_swarm.forge_v1.forge_v2.runner_slots import (
        _probe_with_receipt,
        _slot_for_id,
    )

    slot = _slot_for_id(model_id)
    if slot is None:
        return {
            "model_id": model_id,
            "requested_model": model_id,
            "requested_family": _family(model_id),
            "callable": False,
            "outcome": "unavailable",
            "stage": "config",
            "error_type": "unresolved_model_id",
            "live": True,
            "probe_calls": 0,
        }
    provider = getattr(slot.provider, "value", str(slot.provider))
    receipt = _probe_with_receipt(slot, timeout_s=timeout_s)
    row = {
        "model_id": model_id,
        "provider": provider,
        "live": True,
        "probe_calls": 1,
        **receipt,
    }
    alias_policy = _authorized_successor_alias(
        provider=str(provider),
        requested_model=str(receipt.get("requested_model") or slot.model_id),
        served_model=str(receipt.get("served_model") or ""),
    )
    if receipt.get("error_type") != "served_model_mismatch" or alias_policy is None:
        return row
    row["identity_relation"] = "authorized_successor_alias"
    row["alias_policy"] = alias_policy
    if remaining_probe_calls < 2:
        row["outcome"] = "authorized_alias_confirmation_not_run"
        row["error_type"] = "alias_confirmation_probe_budget_exhausted"
        return row

    # The first probe proves the vendor-declared identity relation but the
    # underlying runner checks identity before content. A second, bounded probe
    # against the declared served ID is therefore required before the route can
    # count as callable evidence.
    alias_slot = SimpleNamespace(
        model_id=str(receipt["served_model"]),
        provider=slot.provider,
        tier=getattr(slot, "tier", "frontier"),
    )
    confirmation = _probe_with_receipt(alias_slot, timeout_s=timeout_s)
    row["probe_calls"] = 2
    row["alias_confirmation"] = {
        key: value
        for key, value in confirmation.items()
        if key
        in {
            "outcome",
            "callable",
            "requested_model",
            "requested_family",
            "served_model",
            "served_family",
            "stage",
            "error_type",
            "latency_ms",
        }
    }
    if not confirmation.get("callable"):
        row["outcome"] = "authorized_alias_confirmation_failed"
        row["error_type"] = "alias_confirmation_failed"
        return row
    row.update(
        {
            "outcome": "callable_authorized_successor_alias",
            "callable": True,
            "stage": "complete",
            "error_type": None,
            "served_model": confirmation.get("served_model"),
            "served_family": confirmation.get("served_family"),
        }
    )
    return row


def _families(rows: list[dict[str, Any]]) -> list[str]:
    families = {
        str(row.get("served_family") or row.get("requested_family") or "")
        for row in rows
        if row.get("callable")
    }
    return sorted(family for family in families if family)


def _independent_routes(rows: list[dict[str, Any]]) -> list[str]:
    """Count distinct attested provider entitlements, not model-family labels."""

    routes = {
        str(row.get("provider") or "").strip().lower()
        for row in rows
        if row.get("callable") and str(row.get("provider") or "").strip()
    }
    return sorted(routes)


def run_provider_selftest(
    *,
    profile: str,
    live: bool,
    require_independent_routes: int | None = None,
    current_model: str | None = None,
    timeout_s: int = 20,
    max_probes: int = 4,
    min_refresh_interval_s: int = 0,
) -> dict[str, Any]:
    """Run or plan a provider selftest and return a redacted result."""

    profile = (profile or DEFAULT_PROFILE).strip().casefold()
    require = int(require_independent_routes or 0)
    timeout_s = int(timeout_s)
    max_probes = int(max_probes)
    min_refresh_interval_s = int(min_refresh_interval_s)
    if not 0 <= require <= 8:
        raise ValueError("require_independent_routes must be between 0 and 8")
    if not 1 <= timeout_s <= 60:
        raise ValueError("timeout_s must be between 1 and 60")
    if not 1 <= max_probes <= 8:
        raise ValueError("max_probes must be between 1 and 8")
    if min_refresh_interval_s < 0:
        raise ValueError("min_refresh_interval_s must be non-negative")
    model_ids = profile_model_ids(profile, current_model=current_model)
    model_selection = _model_selection_context(
        profile,
        requested_models=model_ids,
    )
    require_all_profile_routes = bool(
        profile == "staged"
        and model_selection.get("source") == "active_model_role_profile"
    )
    policy = _policy_payload(
        profile=profile,
        current_model=current_model,
        requested_models=model_ids,
        require=require,
        timeout_s=timeout_s,
        max_probes=max_probes,
        model_selection=model_selection,
        require_all_profile_routes=require_all_profile_routes,
    )
    policy_digest = content_digest(policy)
    if live:
        cached, cached_path = _latest_compatible_receipt(
            policy_digest=policy_digest,
            min_refresh_interval_s=min_refresh_interval_s,
        )
        if cached is not None:
            return {
                **cached,
                "cached": True,
                "receipt": str(cached_path),
                "refresh_skipped": "minimum_refresh_interval",
            }
    rows: list[dict[str, Any]] = []
    # Configuration inspection is free and should report every configured
    # route. The spend bound applies only to network-capable live probes.
    probe_call_count = 0
    for model_id in model_ids:
        if live and probe_call_count >= max_probes:
            break
        row = (
            _live_row(
                model_id,
                timeout_s=timeout_s,
                remaining_probe_calls=max_probes - probe_call_count,
            )
            if live
            else _config_row(model_id)
        )
        rows.append(row)
        probe_call_count += int(row.get("probe_calls") or 0)
        if (
            live
            and require
            and len(_independent_routes(rows)) >= require
            and (not require_all_profile_routes or len(rows) == len(model_ids))
        ):
            break

    callable_rows = [row for row in rows if row.get("callable")]
    independent = _independent_routes(rows)
    families = _families(rows)
    ok = bool(live and callable_rows)
    failures: list[str] = []
    if not model_ids:
        failures.append("zero_profile_targets")
    if not live:
        failures.append("config_only_no_callable_route_attestation")
    if live and not callable_rows:
        failures.append("zero_callable_routes")
    if live and require and len(independent) < require:
        ok = False
        failures.append(
            f"independent_routes:{len(independent)}/{require}"
        )
    if live and require_all_profile_routes:
        callable_models = {
            str(row.get("model_id") or "") for row in rows if row.get("callable")
        }
        missing_models = [model for model in model_ids if model not in callable_models]
        if missing_models:
            ok = False
            failures.append(
                f"callable_profile_routes:{len(model_ids) - len(missing_models)}/{len(model_ids)}"
            )
    if not live and require:
        failures.append("live_probe_required_for_independent_routes")
    unresolved = [row for row in rows if not row.get("slot_resolved", True)]
    if unresolved:
        failures.append(f"unresolved_targets:{len(unresolved)}")
    if failures:
        ok = False

    payload: dict[str, Any] = {
        "schema": PROVIDER_SELFTEST_SCHEMA,
        "profile": profile,
        "live": live,
        "checked_at": _now(),
        "requested_models": model_ids,
        "probed_models": [str(row.get("model_id")) for row in rows],
        "max_probes": max_probes,
        "probe_call_count": probe_call_count,
        "require_independent_routes": require,
        "require_all_profile_routes": require_all_profile_routes,
        "callable_count": len(callable_rows),
        "independent_route_count": len(independent),
        "independent_routes": independent,
        "independent_families": families,
        "ok": ok,
        "failures": failures,
        "rows": rows,
        "policy": policy,
        "policy_digest": policy_digest,
        "receipt": None,
        "cached": False,
    }
    if live:
        payload["receipt"] = str(_write_live_receipt(payload))
    return payload
