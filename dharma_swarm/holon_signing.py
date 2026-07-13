"""Signed capability leases for the sovereign holon authority envelope.

A lease is a signed, scoped, TTL-bound grant: it names a holon, an issuer, the set
of action classes the holder may perform, and an expiry. The signature is ed25519
over the canonical JSON of every field except ``signature`` itself, so any auditor
re-derives the signing bytes deterministically and a tampered lease fails closed.

This is the store the H4 authority probe validates and the PEP (``holon_pep``)
enforces. Seats may self-sign read-only / reply / model-probe leases; anything that
mutates outside the seat requires an operator signer (the live_mutation ceremony),
so operator-only actions are fail-closed until that key exists.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

LEASE_SCHEMA = "dharma.holon.lease.v1"

READ_ONLY = "read_only"
REPLY_ONLY = "reply_only"
LIVE_MODEL_PROBE = "live_model_probe"
SUBPROCESS_EXEC = "subprocess_exec"
GIT_PUSH = "git_push"
LIVE_MUTATION = "live_mutation"

ACTION_CLASSES = frozenset(
    {READ_ONLY, REPLY_ONLY, LIVE_MODEL_PROBE, SUBPROCESS_EXEC, GIT_PUSH, LIVE_MUTATION}
)
# Classes a seat may sign for itself; everything else needs an operator signer.
SEAT_SELF_SIGNABLE = frozenset({READ_ONLY, REPLY_ONLY, LIVE_MODEL_PROBE})
OPERATOR_ONLY = ACTION_CLASSES - SEAT_SELF_SIGNABLE

_REQUIRED = frozenset(
    {"schema_version", "lease_id", "holon", "issuer", "scope",
     "issued_at", "expires_at", "signer_pubkey", "signature"}
)


class LeaseError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _canonical_bytes(lease: dict[str, Any]) -> bytes:
    """Deterministic signing bytes: every field except the signature, sorted."""
    payload = {k: v for k, v in lease.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_private_key(pem_path: Path):
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_private_key(Path(pem_path).read_bytes(), password=None)


def _pubkey_hex(priv) -> str:
    from cryptography.hazmat.primitives import serialization
    return priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def sign_lease(lease: dict[str, Any], private_key_pem: Path) -> dict[str, Any]:
    priv = _load_private_key(private_key_pem)
    body = dict(lease)
    body["signer_pubkey"] = _pubkey_hex(priv)
    body.pop("signature", None)
    body["signature"] = priv.sign(_canonical_bytes(body)).hex()
    return body


def verify_lease(
    lease: dict[str, Any],
    allowed_signers: set[str] | None = None,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Verify signature, signer membership, expiry, and scope.

    ``allowed_signers=None`` skips the membership check (signature still verified);
    a set — even an empty one — requires the signer to be a member, so an empty set
    is fail-closed by construction.
    """
    missing = _REQUIRED - set(lease)
    if missing:
        return False, f"missing fields: {sorted(missing)}"
    if lease["schema_version"] != LEASE_SCHEMA:
        return False, f"unknown schema {lease['schema_version']}"
    signer = str(lease["signer_pubkey"])
    if allowed_signers is not None and signer not in allowed_signers:
        return False, "signer not authorized"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer))
        pub.verify(bytes.fromhex(str(lease["signature"])), _canonical_bytes(lease))
    except Exception as exc:
        return False, f"signature invalid ({type(exc).__name__})"
    try:
        exp = _parse_iso(str(lease["expires_at"]))
    except Exception:
        return False, "unparseable expires_at"
    if (now or _now()) >= exp:
        return False, "expired"
    scope = lease["scope"]
    if not isinstance(scope, list) or not scope:
        return False, "empty scope"
    bad = set(scope) - ACTION_CLASSES
    if bad:
        return False, f"unknown action classes {sorted(bad)}"
    return True, "valid"


def issue_lease(
    *,
    holon: str,
    scope: list[str],
    ttl_s: int,
    signer_key_pem: Path,
    issuer: str,
    purpose: str = "",
    session_id: str | None = None,
) -> dict[str, Any]:
    scope = list(scope)
    bad = set(scope) - ACTION_CLASSES
    if bad:
        raise LeaseError(f"unknown action classes {sorted(bad)}")
    now = _now()
    lease = {
        "schema_version": LEASE_SCHEMA,
        "lease_id": f"lease:{issuer}:{_iso(now)}:{uuid.uuid4().hex[:8]}",
        "holon": holon,
        "issuer": issuer,
        "scope": scope,
        "purpose": purpose,
        "session_id": session_id or f"{holon}-{_iso(now)}",
        "issued_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=int(ttl_s))),
    }
    return sign_lease(lease, signer_key_pem)


def leases_dir(holon: str, agents_root: Path | None = None) -> Path:
    root = agents_root or (Path.home() / ".dharma" / "agents")
    return root / holon / "leases"


def write_lease(lease: dict[str, Any], agents_root: Path | None = None) -> Path:
    d = leases_dir(lease["holon"], agents_root)
    d.mkdir(parents=True, exist_ok=True)
    lid = str(lease["lease_id"]).replace(":", "_").replace("/", "_")
    path = d / f"{lid}.json"
    path.write_text(json.dumps(lease, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_leases(holon: str, agents_root: Path | None = None) -> list[dict[str, Any]]:
    """All lease JSONs in the seat's store (non-recursive — refusals/ is skipped)."""
    d = leases_dir(holon, agents_root)
    if not d.exists():
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out
