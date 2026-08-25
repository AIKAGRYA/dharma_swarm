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
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from dharma_swarm.forge_lab.newrun import (
    DEFAULT_DIVERSE_MUTATOR,
    DEFAULT_DIVERSE_SOLVER,
    DEFAULT_DIVERSE_VERIFIER,
    DEFAULT_FAST_MUTATOR,
    DEFAULT_FAST_SOLVER,
    DEFAULT_FAST_VERIFIER,
    _family,
)
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    provider_selftest_root,
    safe_json,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.version import (
    PACKAGE_VERSION,
    source_commit,
    source_tree_state,
)

PROVIDER_SELFTEST_SCHEMA = "rsi_lab.provider_selftest.v2"
DEFAULT_PROFILE = "frontier"
ALIAS_POLICY_VERSION = "provider_declared_successor.v1"
_ZHIPU_SUCCESSOR_RE = re.compile(r"^glm-(?P<major>[0-9]+)\.(?P<minor>[0-9]+)$")


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
        # Staged means operator-proven names, never a prose default that can
        # silently drift into authority. Values are model IDs, not secrets.
        return _dedupe(os.environ.get("RSI_LAB_STAGED_MODELS", "").split(","))
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


def _receipt_root() -> Path:
    return provider_selftest_root()


def _receipt_digest(payload: dict[str, Any]) -> str:
    unsigned = {
        key: value
        for key, value in payload.items()
        if key not in {"receipt_digest", "cached", "refresh_skipped"}
    }
    return content_digest(unsigned)


def validate_provider_receipt(
    payload: dict[str, Any],
    *,
    path: Path | None = None,
) -> list[str]:
    """Return structural/binding failures for one persisted v2 receipt."""

    failures: list[str] = []
    if payload.get("schema") != PROVIDER_SELFTEST_SCHEMA:
        failures.append("wrong_schema")
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        failures.append("policy_missing")
    elif payload.get("policy_digest") != content_digest(policy):
        failures.append("policy_digest_mismatch")
    if payload.get("receipt_digest") != _receipt_digest(payload):
        failures.append("receipt_digest_mismatch")
    if path is not None and payload.get("receipt") != str(path):
        failures.append("receipt_path_mismatch")
    return failures


def _write_live_receipt(payload: dict[str, Any]) -> Path:
    """Persist a collision-proof append-only receipt and bind its path."""

    root = _receipt_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9TZ]", "", str(payload["checked_at"]))
    suffix = payload["profile"].replace("/", "_")
    for _ in range(8):
        receipt_id = uuid4().hex
        path = root / f"{stamp}__{suffix}__{receipt_id}__provider_selftest.json"
        stored = {
            **payload,
            "receipt_id": receipt_id,
            "receipt": str(path),
            "cached": False,
        }
        stored["receipt_digest"] = _receipt_digest(stored)
        try:
            write_json_exclusive(path, stored)
        except FileExistsError:
            continue
        payload.clear()
        payload.update(stored)
        return path
    raise RuntimeError("provider_selftest_receipt_id_collision")


def _policy_payload(
    *,
    profile: str,
    current_model: str | None,
    requested_models: list[str],
    require: int,
    timeout_s: int,
    max_probes: int,
) -> dict[str, Any]:
    """Bind a live observation to source, configuration, and probe policy."""

    return {
        "source": {
            "package_version": PACKAGE_VERSION,
            "commit": source_commit(),
            "tree_state": source_tree_state(),
        },
        "configuration": {
            "profile": profile,
            "current_model": (current_model or "").strip() or None,
            "requested_models": requested_models,
        },
        "probe_policy": {
            "require_independent_routes": require,
            "timeout_s": timeout_s,
            "max_provider_calls": max_probes,
            "alias_policy": ALIAS_POLICY_VERSION,
        },
    }


def _latest_compatible_receipt(
    *,
    policy_digest: str,
    min_refresh_interval_s: int,
) -> tuple[dict[str, Any] | None, Path | None]:
    if min_refresh_interval_s <= 0:
        return None, None
    root = _receipt_root()
    if not root.is_dir():
        return None, None
    now = datetime.now(timezone.utc)
    for path in sorted(root.glob("*provider_selftest.json"), reverse=True):
        payload = safe_json(path)
        if not payload or validate_provider_receipt(payload, path=path):
            continue
        if not payload.get("live") or payload.get("policy_digest") != policy_digest:
            continue
        try:
            checked = datetime.fromisoformat(str(payload["checked_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        if (now - checked).total_seconds() <= min_refresh_interval_s:
            return payload, path
    return None, None


def _authorized_successor_alias(
    *,
    provider: str,
    requested_model: str,
    served_model: str,
) -> str | None:
    """Return the narrow host policy authorizing a declared successor alias.

    Zhipu may truthfully report the immediately succeeding GLM minor version
    while accepting the previous stable route name.  Only that one-provider,
    same-major, one-minor successor relation is admitted; arbitrary same-family
    substitutions remain mismatches and cannot become callable evidence.
    """

    if provider.strip().casefold() != "zhipu":
        return None
    requested = _ZHIPU_SUCCESSOR_RE.fullmatch(requested_model.strip().casefold())
    served = _ZHIPU_SUCCESSOR_RE.fullmatch(served_model.strip().casefold())
    if requested is None or served is None:
        return None
    requested_major = int(requested.group("major"))
    requested_minor = int(requested.group("minor"))
    served_major = int(served.group("major"))
    served_minor = int(served.group("minor"))
    if served_major == requested_major and served_minor == requested_minor + 1:
        return ALIAS_POLICY_VERSION
    return None


def _config_row(model_id: str) -> dict[str, Any]:
    from dharma_swarm.api_keys import provider_api_key_env
    from dharma_swarm.forge_v1.forge_v2.runner_slots import _slot_for_id

    slot = _slot_for_id(model_id)
    row: dict[str, Any] = {
        "model_id": model_id,
        "requested_model": model_id,
        "requested_family": _family(model_id),
        "callable": False,
        "outcome": "not_probed",
        "stage": "config",
        "live": False,
    }
    if slot is None:
        row["slot_resolved"] = False
        row["error_type"] = "unresolved_model_id"
        return row
    row["slot_resolved"] = True
    row["provider"] = getattr(slot.provider, "value", str(slot.provider))
    row["wire_model"] = str(slot.model_id)
    key_env = provider_api_key_env(slot.provider)
    row["credential_env"] = key_env
    row["credential_present"] = bool(key_env and os.environ.get(key_env, "").strip())
    row["credential_required"] = key_env is not None
    return row


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

    require = max(0, int(require_independent_routes or 0))
    timeout_s = max(1, min(int(timeout_s), 60))
    max_probes = max(1, min(int(max_probes), 8))
    model_ids = profile_model_ids(profile, current_model=current_model)
    policy = _policy_payload(
        profile=profile,
        current_model=current_model,
        requested_models=model_ids,
        require=require,
        timeout_s=timeout_s,
        max_probes=max_probes,
    )
    policy_digest = content_digest(policy)
    if live:
        cached, cached_path = _latest_compatible_receipt(
            policy_digest=policy_digest,
            min_refresh_interval_s=max(0, int(min_refresh_interval_s)),
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
        if live and require and len(_independent_routes(rows)) >= require:
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
