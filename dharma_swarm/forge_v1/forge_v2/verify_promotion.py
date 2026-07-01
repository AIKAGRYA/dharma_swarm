"""Fail-closed Forge promotion verifier.

This is the sole live-apply arbiter for Forge/DGM scaffold promotion.  It
composes the v0 statistical promotion predicate with governed-work admission,
formal telos gates, an operator lease, and signed judge receipts.  Missing or
unverifiable evidence is treated as absent, never as assumed-ok.
"""
from __future__ import annotations

import binascii
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from dharma_swarm.models import GateDecision
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkRequest,
    WorkKind,
    evaluate_governed_work_admission,
)
from dharma_swarm.telos_formal import ActionContext, FormalTelosGatekeeper

from . import promote
from .signals import canonical_sha256


@dataclass(frozen=True)
class PromotionVerification:
    schema: str = "forge_v2.promotion_verification.v1"
    decision: str = "refused"
    live_apply_allowed: bool = False
    promotion_packet: dict[str, Any] = field(default_factory=dict)
    governed_admission: dict[str, Any] = field(default_factory=dict)
    telos: dict[str, Any] = field(default_factory=dict)
    signed_receipts: dict[str, bool] = field(default_factory=dict)
    operator_lease_present: bool = False
    blockers: list[str] = field(default_factory=list)
    payload_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("payload_sha256"):
            body = {k: v for k, v in d.items() if k != "payload_sha256"}
            d["payload_sha256"] = canonical_sha256(body)
        return d


def _canonical_receipt_payload(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _normal_public_key_hex(public_key: str | bytes) -> str:
    if isinstance(public_key, bytes):
        return public_key.hex()
    return str(public_key).strip().lower()


def verify_signed_receipt(receipt: dict[str, Any]) -> bool:
    """Verify an ed25519-signed receipt payload.

    Expected shape:
    ``{"name": "...", "payload": {...}, "signature": {"scheme": "ed25519",
    "public_key": "<hex>", "signature": "<hex>"}}``.
    """
    try:
        sig = dict(receipt.get("signature", {}) or {})
        if sig.get("scheme") != "ed25519":
            return False
        payload = receipt["payload"]
        public_key = binascii.unhexlify(str(sig["public_key"]))
        signature = binascii.unhexlify(str(sig["signature"]))
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            _canonical_receipt_payload(payload),
        )
        return True
    except Exception:
        return False


def _receipt_public_key_hex(receipt: dict[str, Any]) -> str:
    try:
        sig = dict(receipt.get("signature", {}) or {})
        return _normal_public_key_hex(sig["public_key"])
    except Exception:
        return ""


def verify_trusted_signed_receipt(
    receipt: dict[str, Any],
    *,
    trusted_public_keys: Iterable[str | bytes] = (),
) -> bool:
    """Verify receipt signature and signer authority.

    A receipt signed by an arbitrary key is still worker-authorable.  It counts
    only when the signature is valid and the signer public key is explicitly
    trusted by the promotion verifier.
    """
    trusted = {_normal_public_key_hex(key) for key in trusted_public_keys}
    public_key = _receipt_public_key_hex(receipt)
    return bool(trusted and public_key in trusted and verify_signed_receipt(receipt))


def _verification_signature_payload(packet: dict[str, Any]) -> dict[str, Any]:
    body = dict(packet)
    body.pop("verification_signature", None)
    return body


def sign_promotion_verification(
    packet: dict[str, Any],
    signing_key: Any,
    *,
    key_id: str = "",
) -> dict[str, Any]:
    """Attach a judge ed25519 signature to a promotion verification packet."""
    from cryptography.hazmat.primitives import serialization

    signed = _verification_signature_payload(packet)
    body = {k: v for k, v in signed.items() if k != "payload_sha256"}
    signed["payload_sha256"] = canonical_sha256(body)
    signature = signing_key.sign(_canonical_receipt_payload(signed))
    public_key = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signed["verification_signature"] = {
        "scheme": "ed25519",
        "key_id": key_id,
        "public_key": public_key.hex(),
        "signature": signature.hex(),
    }
    return signed


def verify_promotion_verification_signature(
    packet: dict[str, Any],
    *,
    trusted_public_keys: Iterable[str | bytes] = (),
) -> bool:
    """Verify that a promotion verdict was signed by a trusted judge key."""
    try:
        trusted = {_normal_public_key_hex(key) for key in trusted_public_keys}
        if not trusted:
            return False
        sig = dict(packet.get("verification_signature", {}) or {})
        if sig.get("scheme") != "ed25519":
            return False
        public_key_hex = _normal_public_key_hex(sig["public_key"])
        if public_key_hex not in trusted:
            return False
        body = _verification_signature_payload(packet)
        body_without_hash = {k: v for k, v in body.items() if k != "payload_sha256"}
        if body.get("payload_sha256") != canonical_sha256(body_without_hash):
            return False
        public_key = binascii.unhexlify(public_key_hex)
        signature = binascii.unhexlify(str(sig["signature"]))
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            _canonical_receipt_payload(body),
        )
        return True
    except Exception:
        return False


def _receipt_map(receipts: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        name = str(receipt.get("name") or receipt.get("receipt_type") or "")
        if name:
            out[name] = dict(receipt)
    return out


def verify_promotion(
    signal: dict[str, Any],
    *,
    signed_receipts: Iterable[dict[str, Any]] = (),
    operator_lease: dict[str, Any] | None = None,
    trusted_receipt_public_keys: Iterable[str | bytes] = (),
    agent_uid: str = "forge_dgm",
    mission_contract_present: bool = True,
    mutation_budget_remaining: int | None = 1,
    admission_fn: Callable[[GovernedWorkRequest], Any] = evaluate_governed_work_admission,
    telos_gatekeeper: Any | None = None,
) -> dict[str, Any]:
    """Return the fail-closed promotion verdict for a Forge signal."""
    packet = promote.evaluate_promotion(signal)
    receipt_by_name = _receipt_map(signed_receipts)
    signed_status = {
        name: verify_trusted_signed_receipt(
            receipt_by_name[name],
            trusted_public_keys=trusted_receipt_public_keys,
        )
        if name in receipt_by_name
        else False
        for name in promote.REQUIRED_RECEIPTS_V0_ABSENT
    }

    admission = admission_fn(
        GovernedWorkRequest(
            request_id=str(signal.get("signal_key") or signal.get("run_id") or ""),
            agent_uid=agent_uid,
            work_kind=WorkKind.PROMOTION,
            intent="promote Forge/DGM scaffold candidate",
            risk_tier="Q4",
            autonomy_level="operator_lease",
            mutation_budget_remaining=mutation_budget_remaining,
            mission_contract_present=mission_contract_present,
            workspace_lease_present=bool(operator_lease),
            metadata={"signal_key": signal.get("signal_key"), "run_id": signal.get("run_id")},
        )
    )
    admission_dict = admission.model_dump() if hasattr(admission, "model_dump") else dict(admission)

    gatekeeper = telos_gatekeeper or FormalTelosGatekeeper()
    telos_decision, telos_report, keyword_payload = gatekeeper.check(
        ActionContext(
            action="forge_promotion",
            actor_id=agent_uid,
            mutates_state=True,
            measures_state=False,
            provenance_claims=[],
        ),
        content=json.dumps(
            {
                "arm": signal.get("arm"),
                "run_id": signal.get("run_id"),
                "signal_key": signal.get("signal_key"),
            },
            sort_keys=True,
            default=str,
        ),
    )
    telos_dict = {
        "decision": getattr(telos_decision, "value", str(telos_decision)),
        "receipt_sha256": getattr(telos_report, "receipt_sha256", ""),
        "keyword": dict(keyword_payload or {}),
    }

    blockers = set(packet.get("blockers", []) or [])
    blockers.update(f"promotion_packet:{name}" for name in packet.get("failed_conjuncts", []) or [])
    trusted_receipt_keys = {
        _normal_public_key_hex(key) for key in trusted_receipt_public_keys
    }
    for name, ok in signed_status.items():
        if not ok:
            if name in receipt_by_name and verify_signed_receipt(receipt_by_name[name]):
                receipt_key = _receipt_public_key_hex(receipt_by_name[name])
                if not trusted_receipt_keys or receipt_key not in trusted_receipt_keys:
                    blockers.add(f"untrusted_signed_receipt:{name}")
                else:
                    blockers.add(f"missing_or_invalid_signed_receipt:{name}")
            else:
                blockers.add(f"missing_or_invalid_signed_receipt:{name}")
    if not operator_lease:
        blockers.add("operator_lease_missing")
    if admission_dict.get("decision") != "allow":
        blockers.add(f"governed_admission_{admission_dict.get('decision', 'missing')}")
    if telos_decision != GateDecision.ALLOW:
        blockers.add(f"telos_{getattr(telos_decision, 'value', telos_decision)}")

    allowed = (
        packet.get("decision") == "promotable_candidate"
        and all(signed_status.values())
        and bool(operator_lease)
        and admission_dict.get("decision") == "allow"
        and telos_decision == GateDecision.ALLOW
        and not blockers
    )
    verification = PromotionVerification(
        decision="allow" if allowed else "refused",
        live_apply_allowed=allowed,
        promotion_packet=packet,
        governed_admission=admission_dict,
        telos=telos_dict,
        signed_receipts=signed_status,
        operator_lease_present=bool(operator_lease),
        blockers=sorted(blockers),
    )
    return verification.to_dict()


__all__ = [
    "PromotionVerification",
    "sign_promotion_verification",
    "verify_promotion",
    "verify_promotion_verification_signature",
    "verify_signed_receipt",
    "verify_trusted_signed_receipt",
]
