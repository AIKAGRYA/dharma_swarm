"""Secret-free provider configuration inspection and attestation façade.

Configuration inspection remains non-operational. Signed receipt contracts and
the Ed25519 trust boundary live in focused modules and are re-exported here for
backward-compatible callers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.forge_lab.provider_attestation import (
    build_provider_attestation as build_provider_attestation,
    verify_provider_attestation as verify_provider_attestation,
)
from dharma_swarm.forge_lab.provider_attestation_contract import (
    DEFAULT_ATTESTATION_TTL_SECONDS as DEFAULT_ATTESTATION_TTL_SECONDS,
    DIGEST_RE as _DIGEST_RE,
    PROVIDER_ATTESTATION_SCHEMA as PROVIDER_ATTESTATION_SCHEMA,
    PROVIDER_PROBE_AUTHORITY_SCHEMA as PROVIDER_PROBE_AUTHORITY_SCHEMA,
    PROVIDER_PROBE_TRUST_SCHEMA as PROVIDER_PROBE_TRUST_SCHEMA,
    PROVIDER_ROUTE_CONFIG_SCHEMA as PROVIDER_ROUTE_CONFIG_SCHEMA,
    UNATTENDED_MIN_INDEPENDENT_TRANSPORTS as UNATTENDED_MIN_INDEPENDENT_TRANSPORTS,
    ProviderAttestationError as ProviderAttestationError,
    attestation_policy as _attestation_policy,
    canonical_json as _canonical_json,
    definition as _definition,
    format_timestamp as _format_timestamp,
    parse_timestamp as _parse_timestamp,
    physical_transport_digest as _physical_transport_digest,
    provider_attestation_digest as provider_attestation_digest,
    provider_probe_request_nonce as provider_probe_request_nonce,
    provider_route_config_digest as provider_route_config_digest,
    role_bindings as _role_bindings,
    sha256_digest as _sha256,
    utc_now as _utc_now,
    verified_manifest_digest as _verified_manifest_digest,
)
from dharma_swarm.forge_lab.provider_probe_trust import (
    ProviderSignatureVerifier as ProviderSignatureVerifier,
    attestation_signing_bytes as _attestation_signing_bytes,
    load_trusted_provider_probe_keys as load_trusted_provider_probe_keys,
)


PROVIDER_SELFTEST_SCHEMA = "rsi_lab.provider_selftest.v1"
DEFAULT_PROFILE = "frontier"

__all__ = [
    "DEFAULT_ATTESTATION_TTL_SECONDS",
    "DEFAULT_PROFILE",
    "PROVIDER_ATTESTATION_SCHEMA",
    "PROVIDER_PROBE_AUTHORITY_SCHEMA",
    "PROVIDER_PROBE_TRUST_SCHEMA",
    "PROVIDER_ROUTE_CONFIG_SCHEMA",
    "PROVIDER_SELFTEST_SCHEMA",
    "UNATTENDED_MIN_INDEPENDENT_TRANSPORTS",
    "ProviderAttestationError",
    "ProviderSignatureVerifier",
    "_DIGEST_RE",
    "_attestation_policy",
    "_attestation_signing_bytes",
    "_canonical_json",
    "_definition",
    "_format_timestamp",
    "_parse_timestamp",
    "_physical_transport_digest",
    "_role_bindings",
    "_sha256",
    "_utc_now",
    "_verified_manifest_digest",
    "build_provider_attestation",
    "load_trusted_provider_probe_keys",
    "provider_attestation_digest",
    "provider_probe_request_nonce",
    "provider_route_config_digest",
    "verify_provider_attestation",
]


def _now() -> str:
    return _format_timestamp(_utc_now())


def _family(model_id: str) -> str:
    """Resolve the existing Forge family classifier without provider clients."""

    from dharma_swarm.forge_v1.forge_v2.critic import _family as classify

    return classify(model_id)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = (item or "").strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def profile_model_ids(profile: str, *, current_model: str | None = None) -> list[str]:
    """Return ordered model IDs for interactive configuration inspection."""

    from dharma_swarm.forge_lab.newrun import (
        DEFAULT_DIVERSE_MUTATOR,
        DEFAULT_DIVERSE_SOLVER,
        DEFAULT_DIVERSE_VERIFIER,
        DEFAULT_FAST_MUTATOR,
        DEFAULT_FAST_SOLVER,
        DEFAULT_FAST_VERIFIER,
    )

    normalized = (profile or DEFAULT_PROFILE).strip().lower()
    current = (current_model or "").strip()
    fast = [DEFAULT_FAST_SOLVER, DEFAULT_FAST_VERIFIER, DEFAULT_FAST_MUTATOR]
    diverse = [
        DEFAULT_DIVERSE_SOLVER,
        DEFAULT_DIVERSE_VERIFIER,
        DEFAULT_DIVERSE_MUTATOR,
    ]
    if normalized in {"fast", "offline"}:
        return _dedupe(fast)
    if normalized in {"current", "newrun"}:
        return _dedupe(([current] if current else []) + fast + diverse)
    if normalized == "frontier":
        try:
            from dharma_swarm.model_pool import forge_high_slot_model_ids

            high_slots = list(forge_high_slot_model_ids())
        except Exception:
            high_slots = []
        return _dedupe(fast + diverse + high_slots)
    raise ValueError(
        f"unknown provider selftest profile {profile!r}; "
        "choose frontier, fast, current, newrun, or offline"
    )


def _receipt_root() -> Path:
    """Resolve an explicit or canonical receipt root; never use HOME."""

    explicit = os.environ.get("RSI_LAB_PROVIDER_SELFTEST_ROOT", "").strip()
    if explicit:
        root = Path(explicit)
    else:
        state = os.environ.get("RSI_LAB_STATE", "").strip()
        if state:
            state_root = Path(state)
        else:
            base = os.environ.get("RSI_LAB_BASE", "").strip()
            if not base:
                raise ValueError(
                    "canonical state is unbound; set RSI_LAB_STATE, "
                    "RSI_LAB_BASE, or RSI_LAB_PROVIDER_SELFTEST_ROOT"
                )
            state_root = Path(base) / "state"
        root = state_root / ".dharma" / "forge_lab" / "provider_selftests"
    if not root.is_absolute():
        raise ValueError("provider selftest receipt root must be absolute")
    if root.is_symlink():
        raise ValueError("provider selftest receipt root must not be a symlink")
    return root


def _write_live_receipt(payload: dict[str, Any], *, root: Path | None = None) -> Path:
    """Atomically persist one redacted owner-only receipt."""

    root = root or _receipt_root()
    if root.is_symlink():
        raise ValueError("provider selftest receipt root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = str(payload["checked_at"]).replace(":", "").replace("-", "")
    suffix = str(payload["profile"]).replace("/", "_")
    path = root / f"{stamp}__{suffix}__{uuid4().hex[:8]}__provider_selftest.json"
    temporary = root / f".{path.name}.tmp-{os.getpid()}-{uuid4().hex[:8]}"
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _route_metadata(slot: object, *, timeout_s: int) -> dict[str, str]:
    from dharma_swarm.runtime_provider import (
        resolve_runtime_provider_config,
        runtime_provider_transport_identity,
    )

    provider = getattr(slot, "provider")
    model = str(getattr(slot, "model_id"))
    config = resolve_runtime_provider_config(
        provider,
        model=model,
        timeout_seconds=timeout_s,
    )
    identity = runtime_provider_transport_identity(config)
    return {
        "provider": getattr(provider, "value", str(provider)),
        "wire_model": str(config.default_model or model),
        "physical_transport_digest": _sha256(identity),
    }


def _config_row(model_id: str, *, timeout_s: int = 20) -> dict[str, Any]:
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
        row.update(slot_resolved=False, error_type="unresolved_model_id")
        return row
    row["slot_resolved"] = True
    try:
        row.update(_route_metadata(slot, timeout_s=timeout_s))
    except Exception as exc:
        row.update(
            slot_resolved=False,
            error_type=f"route_config:{type(exc).__name__}",
        )
    return row


def _live_row(model_id: str, *, timeout_s: int) -> dict[str, Any]:
    """Probe one route only when invoked by an already-governed broker."""

    from dharma_swarm.forge_v1.forge_v2.runner_slots import (
        _probe_with_receipt,
        _slot_for_id,
    )

    slot = _slot_for_id(model_id)
    base = {
        "model_id": model_id,
        "requested_model": model_id,
        "requested_family": _family(model_id),
        "live": True,
        "fallback": False,
    }
    if slot is None:
        return {
            **base,
            "callable": False,
            "outcome": "unavailable",
            "stage": "config",
            "error_type": "unresolved_model_id",
        }
    try:
        metadata = _route_metadata(slot, timeout_s=timeout_s)
    except Exception as exc:
        return {
            **base,
            "callable": False,
            "outcome": "unavailable",
            "stage": "config",
            "error_type": f"route_config:{type(exc).__name__}",
        }
    return {
        **base,
        **metadata,
        **_probe_with_receipt(slot, timeout_s=timeout_s),
    }


def _families(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("served_family") or row.get("requested_family") or "")
            for row in rows
            if row.get("callable")
        }
        - {""}
    )


def _transports(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(row.get("physical_transport_digest") or "")
            for row in rows
            if row.get("callable")
            and _DIGEST_RE.fullmatch(str(row.get("physical_transport_digest") or ""))
        }
    )


def run_provider_selftest(
    *,
    profile: str,
    live: bool,
    require_independent_routes: int | None = None,
    current_model: str | None = None,
    timeout_s: int = 20,
) -> dict[str, Any]:
    """Resolve configuration without claiming operational readiness."""

    if live:
        raise ValueError(
            "live provider selftest is disabled until a manifest-bound, signed "
            "probe authority and fenced request reservation are implemented"
        )
    if timeout_s <= 0:
        raise ValueError("provider selftest timeout must be positive")
    require = max(0, int(require_independent_routes or 0))
    model_ids = profile_model_ids(profile, current_model=current_model)
    rows = [_config_row(model_id, timeout_s=timeout_s) for model_id in model_ids]
    unresolved = [row for row in rows if row.get("slot_resolved") is not True]
    failures = [f"unresolved_routes:{len(unresolved)}/{len(rows)}"] if unresolved else []
    if require:
        failures.append("live_probe_required_for_independent_routes")
    return {
        "schema": PROVIDER_SELFTEST_SCHEMA,
        "profile": profile,
        "live": False,
        "status": "configured" if not unresolved else "blocked",
        "operational": False,
        "checked_at": _now(),
        "requested_models": model_ids,
        "probed_models": [],
        "require_independent_routes": require,
        "callable_count": 0,
        "independent_route_count": 0,
        "independent_transports": [],
        "independent_family_count": 0,
        "independent_families": [],
        "ok": not failures,
        "failures": failures,
        "rows": rows,
        "receipt": None,
    }
