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

import json
import os
from datetime import datetime, timezone
from pathlib import Path
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

PROVIDER_SELFTEST_SCHEMA = "rsi_lab.provider_selftest.v1"
DEFAULT_PROFILE = "frontier"


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
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
        "choose frontier, fast, current, newrun, or offline"
    )


def _receipt_root() -> Path:
    """Resolve receipts inside explicit test or canonical RSI Lab state.

    There is deliberately no home-directory fallback: a live probe must know
    which canonical state boundary will receive its immutable evidence before
    making any provider request.
    """

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
    return root


def _write_live_receipt(
    payload: dict[str, Any],
    *,
    root: Path | None = None,
) -> Path:
    root = root or _receipt_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = payload["checked_at"].replace(":", "").replace("-", "")
    suffix = payload["profile"].replace("/", "_")
    path = root / f"{stamp}__{suffix}__provider_selftest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _config_row(model_id: str) -> dict[str, Any]:
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
    return row


def _live_row(model_id: str, *, timeout_s: int) -> dict[str, Any]:
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
        }
    receipt = _probe_with_receipt(slot, timeout_s=timeout_s)
    return {
        "model_id": model_id,
        "provider": getattr(slot.provider, "value", str(slot.provider)),
        "live": True,
        **receipt,
    }


def _families(rows: list[dict[str, Any]]) -> list[str]:
    families = {
        str(row.get("served_family") or row.get("requested_family") or "")
        for row in rows
        if row.get("callable")
    }
    return sorted(family for family in families if family)


def run_provider_selftest(
    *,
    profile: str,
    live: bool,
    require_independent_routes: int | None = None,
    current_model: str | None = None,
    timeout_s: int = 20,
) -> dict[str, Any]:
    """Run or plan a provider selftest and return a redacted result."""

    if live:
        raise ValueError(
            "live provider selftest is disabled until a manifest-bound, signed "
            "probe authority and fenced request reservation are implemented"
        )

    require = max(0, int(require_independent_routes or 0))
    model_ids = profile_model_ids(profile, current_model=current_model)
    receipt_root = None
    rows: list[dict[str, Any]] = []
    for model_id in model_ids:
        row = _live_row(model_id, timeout_s=timeout_s) if live else _config_row(model_id)
        rows.append(row)
        if live and require and len(_families(rows)) >= require:
            break

    callable_rows = [row for row in rows if row.get("callable")]
    independent = _families(rows)
    ok = True
    failures: list[str] = []
    if live and require and len(independent) < require:
        ok = False
        failures.append(
            f"independent_routes:{len(independent)}/{require}"
        )
    if not live and require:
        ok = False
        failures.append("live_probe_required_for_independent_routes")

    payload: dict[str, Any] = {
        "schema": PROVIDER_SELFTEST_SCHEMA,
        "profile": profile,
        "live": live,
        "checked_at": _now(),
        "requested_models": model_ids,
        "probed_models": [str(row.get("model_id")) for row in rows],
        "require_independent_routes": require,
        "callable_count": len(callable_rows),
        "independent_route_count": len(independent),
        "independent_families": independent,
        "ok": ok,
        "failures": failures,
        "rows": rows,
        "receipt": None,
    }
    if live:
        payload["receipt"] = str(
            _write_live_receipt(payload, root=receipt_root)
        )
    return payload
