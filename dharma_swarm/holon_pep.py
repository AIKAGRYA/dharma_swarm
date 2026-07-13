"""Policy Enforcement Point for holon capability leases.

``enforce_lease(uid, action_class)`` is the gate: it admits an action only if the
seat holds a valid, signed, non-expired lease whose scope covers that action and
whose signer is authorized for it. Otherwise it writes a refusal receipt and raises
``LeaseDenied`` — the observed refusal that proves the gate is real, not merely
declared. This is the in-process PEP; the out-of-process external gate (F5) is a
later rung on the frontier ladder.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm import holon_signing as hs

REFUSAL_SCHEMA = "dharma.holon.lease_refusal.v1"

# Operator signer pubkeys authorized for OPERATOR_ONLY action classes. Empty until
# the operator-key ceremony (frontier F-tier); until then operator-only actions are
# fail-closed by construction — no seat can self-grant them.
_OPERATOR_SIGNERS: set[str] = set()


class LeaseDenied(Exception):
    pass


def register_operator_signer(pubkey_hex: str) -> None:
    _OPERATOR_SIGNERS.add(pubkey_hex.strip().lower())


def operator_signers() -> set[str]:
    return set(_OPERATOR_SIGNERS)


def _seat_pubkey(uid: str, agents_root: Path | None) -> str | None:
    root = agents_root or (Path.home() / ".dharma" / "agents")
    try:
        return str(json.loads((root / uid / "identity.json").read_text())["public_key"])
    except Exception:
        return None


def _allowed_signers(uid: str, action_class: str, agents_root: Path | None) -> set[str]:
    signers = set(_OPERATOR_SIGNERS)
    if action_class in hs.SEAT_SELF_SIGNABLE:
        pk = _seat_pubkey(uid, agents_root)
        if pk:
            signers.add(pk)
    return signers


def _write_refusal(
    uid: str, action_class: str, reason: str, checked: list[str], agents_root: Path | None
) -> Path:
    d = hs.leases_dir(uid, agents_root) / "refusals"
    d.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    rec = {
        "schema_version": REFUSAL_SCHEMA,
        "holon": uid,
        "action_class": action_class,
        "decision": "refused",
        "reason": reason,
        "checked_lease_ids": checked,
        "enforced_by": "holon_pep",
        "decided_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = d / f"refusal_{action_class}_{stamp}.json"
    i = 0
    while path.exists():
        i += 1
        path = d / f"refusal_{action_class}_{stamp}_{i}.json"
    path.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    return path


def check_lease(
    uid: str, action_class: str, agents_root: Path | None = None
) -> tuple[bool, str, list[str]]:
    """Non-mutating decision: (allowed, lease_id_or_reason, checked_lease_ids)."""
    if action_class not in hs.ACTION_CLASSES:
        return False, f"unknown action class {action_class}", []
    allowed = _allowed_signers(uid, action_class, agents_root)
    checked: list[str] = []
    for lease in hs.load_leases(uid, agents_root):
        lid = str(lease.get("lease_id", "?"))
        checked.append(lid)
        try:
            ok, _why = hs.verify_lease(lease, allowed_signers=allowed)
        except Exception:  # a malformed lease must not crash the gate — treat as invalid
            ok = False
        if ok and action_class in lease.get("scope", []):
            return True, lid, checked
    return False, "no valid lease covers this action", checked


def enforce_lease(
    uid: str, action_class: str, agents_root: Path | None = None
) -> dict[str, Any]:
    """Admit the action or write a refusal receipt and raise LeaseDenied."""
    ok, detail, checked = check_lease(uid, action_class, agents_root)
    if ok:
        return {"decision": "granted", "lease_id": detail, "action_class": action_class}
    path = _write_refusal(uid, action_class, detail, checked, agents_root)
    raise LeaseDenied(f"{uid} denied '{action_class}': {detail} (receipt {path})")
