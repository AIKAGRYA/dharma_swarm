"""Exact blocked-receipt construction and replay validation."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

from dharma_swarm.forge_lab.campaign_contract import canonical_json


BLOCKED_SCHEMA = "forge_lab.blocked_receipt.v1"
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CLEARED_LEASE = {
    "fencing_token": None,
    "holder": None,
    "mode": None,
    "expires_at": None,
}


class BlockedReceiptError(RuntimeError):
    """Receipt bytes cannot truthfully attest the requested terminal state."""


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_blocked_receipt(
    manifest: dict[str, Any],
    *,
    campaign_id: str,
    request_id: str,
    gates: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers = [
        {"gate": gate["name"], "code": gate["code"], "detail": gate.get("detail")}
        for gate in gates
        if not gate["passed"]
    ]
    payload: dict[str, Any] = {
        "schema": BLOCKED_SCHEMA,
        "campaign_id": campaign_id,
        "campaign_name": manifest["campaign_name"],
        "manifest_digest": manifest["manifest_digest"],
        "request_id": request_id,
        "recorded_at": _now(),
        "lifecycle_state": "FAILED",
        "disposition": "BLOCKED",
        "technical_disposition": "blocked_with_evidence",
        "gates": gates,
        "blockers": blockers,
        "authority": {
            "prompt_is_spend_authority": False,
            "operator_envelope_verified": False,
            "dispatch_enabled": False,
        },
        "progress": {
            "target_primary_attempts": 1_000,
            "terminal_primary_attempts": 0,
            "seed_counted": False,
        },
        "provider_effects": {
            "requests_dispatched_by_campaign": 0,
            "paid_calls_authorized": 0,
            "ambient_incident_status": "unknown_not_attributed_to_campaign",
        },
        "stages": {
            "canary": "not_started",
            "n30_reproduction": "not_started",
            "primary": "not_started",
        },
        "cleanup": {
            "scratch_created": False,
            "state": "not_required",
            "residuals": [],
        },
        "claim_boundary": manifest["claims"],
        "supersedes_digest": None,
    }
    payload["receipt_digest"] = (
        f"sha256:{sha256(canonical_json(payload)).hexdigest()}"
    )
    return payload


def validate_blocked_receipt(
    receipt: Any,
    *,
    campaign_id: str,
    manifest_digest: str,
    request_id: str,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise BlockedReceiptError("blocked receipt must be a JSON object")
    unsigned = dict(receipt)
    declared = unsigned.pop("receipt_digest", None)
    if not isinstance(declared, str) or not _DIGEST_RE.fullmatch(declared):
        raise BlockedReceiptError("blocked receipt has no valid self-digest")
    try:
        computed = f"sha256:{sha256(canonical_json(unsigned)).hexdigest()}"
    except (TypeError, ValueError) as exc:
        raise BlockedReceiptError(
            f"blocked receipt cannot be canonicalized: {exc}"
        ) from exc
    if declared != computed:
        raise BlockedReceiptError(
            "blocked receipt self-digest does not match its canonical bytes"
        )
    expected = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_id,
        "manifest_digest": manifest_digest,
        "request_id": request_id,
    }
    mismatched = [
        field for field, value in expected.items() if receipt.get(field) != value
    ]
    if mismatched:
        raise BlockedReceiptError(
            "blocked receipt identity mismatch: " + ", ".join(mismatched)
        )
    if (
        receipt.get("schema") != BLOCKED_SCHEMA
        or receipt.get("lifecycle_state") != "FAILED"
        or receipt.get("disposition") != "BLOCKED"
        or receipt.get("technical_disposition") != "blocked_with_evidence"
    ):
        raise BlockedReceiptError(
            "blocked receipt does not declare exact terminal blocked semantics"
        )
    return receipt


def terminal_state_problem(
    status: Any,
    *,
    campaign_id: str,
    manifest_digest: str,
) -> str | None:
    if not isinstance(status, dict):
        return "canonical campaign status is not an object"
    if status.get("campaign") != campaign_id:
        return "canonical campaign identity does not match the receipt"
    if status.get("manifest_digest") != manifest_digest:
        return "canonical manifest identity does not match the receipt"
    if status.get("state") != "FAILED":
        return "canonical campaign state is not FAILED"
    if status.get("lease") != _CLEARED_LEASE:
        return "canonical campaign lease is not fully cleared"
    return None
