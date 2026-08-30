"""Receipt persistence, policy binding, and config-row probes for the
provider-route selftest.

Split out of ``provider_selftest`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.forge_lab.newrun import _family
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
ALIAS_POLICY_VERSION = "provider_declared_successor.v1"
_ZHIPU_SUCCESSOR_RE = re.compile(r"^glm-(?P<major>[0-9]+)\.(?P<minor>[0-9]+)$")


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
    model_selection: dict[str, Any],
    require_all_profile_routes: bool,
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
            "model_selection": model_selection,
        },
        "probe_policy": {
            "require_independent_routes": require,
            "timeout_s": timeout_s,
            "max_provider_calls": max_probes,
            "require_all_profile_routes": require_all_profile_routes,
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
        age_seconds = (now - checked).total_seconds()
        if 0 <= age_seconds <= min_refresh_interval_s:
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
