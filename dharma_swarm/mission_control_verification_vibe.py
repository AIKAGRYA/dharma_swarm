"""Closed-shape, independently signed Vibe Halt evidence classification."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.mission_control_verification import (
    CURRENT_VIBE_SCHEMA,
    PATCH_VIBE_SCHEMA,
    SIGNED_VIBE_BINDING_SCHEMA,
    _ED25519_SIGNATURE_RE,
    _SHA256_RE,
    ExpectedPromotionBindings,
    InconclusiveCapability,
    RejectedCapability,
    VerifiedVibeHalt,
    VibeHaltCapability,
)

_PATCH_VIBE_KEYS = frozenset(
    """schema candidate_digest diff_sha256 verifier ran reported_outcome
    diff_bound calibration_only process findings errors blockers payload_sha256
    signature""".split()
)
_SIGNATURE_KEYS = frozenset("scheme key_id public_key signature".split())


def _mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return dict(value)
    except Exception:
        return None


def _receipt_sha256(receipt: Mapping[str, Any]) -> str | None:
    try:
        return canonical_sha256(dict(receipt))
    except Exception:
        return None


def _signature_public_key(signature: Any) -> str | None:
    data = _mapping(signature)
    if data is None or frozenset(data) != _SIGNATURE_KEYS:
        return None
    public_key = data.get("public_key")
    raw_signature = data.get("signature")
    if (
        data.get("scheme") != "ed25519"
        or not isinstance(data.get("key_id"), str)
        or not isinstance(public_key, str)
        or _SHA256_RE.fullmatch(public_key) is None
        or not isinstance(raw_signature, str)
        or _ED25519_SIGNATURE_RE.fullmatch(raw_signature) is None
    ):
        return None
    return public_key


def _signed_payload_valid(packet: dict[str, Any], *, signature_field: str) -> bool:
    """Verify one self-hashed Ed25519 mapping with an exact signature block."""
    try:
        signature = _mapping(packet.get(signature_field))
        public_key = _signature_public_key(signature)
        if signature is None or public_key is None:
            return False
        signed = {key: value for key, value in packet.items() if key != signature_field}
        body = {key: value for key, value in signed.items() if key != "payload_sha256"}
        payload_sha256 = signed.get("payload_sha256")
        if (
            not isinstance(payload_sha256, str)
            or _SHA256_RE.fullmatch(payload_sha256) is None
            or canonical_sha256(body) != payload_sha256
        ):
            return False
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
            bytes.fromhex(signature["signature"]),
            json.dumps(
                signed,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8"),
        )
        return True
    except Exception:
        return False


def _signed_packet_shape_valid(packet: Mapping[str, Any]) -> bool:
    return _signature_public_key(packet.get("verification_signature")) is not None


def expected_vibe_halt_binding(
    receipt: Mapping[str, Any],
    *,
    expected: ExpectedPromotionBindings,
) -> dict[str, Any] | None:
    """Return the signed coverage block for one complete Vibe Halt receipt."""
    digest = _receipt_sha256(receipt)
    if digest is None:
        return None
    return {
        "schema": SIGNED_VIBE_BINDING_SCHEMA,
        "candidate_digest": expected.candidate_digest,
        "diff_sha256": expected.diff_sha256,
        "verifier_agent_uid": expected.vibe_verifier.agent_uid,
        "verifier_run_id": expected.vibe_verifier.run_id,
        "verifier_parent_run_id": expected.executor_run_id,
        "verifier_signer_public_key": expected.vibe_verifier.signer_public_key,
        "receipt_sha256": digest,
    }


def _evaluate_vibe_halt(
    receipt: Mapping[str, Any] | None,
    *,
    expected: ExpectedPromotionBindings,
    signed_identity_coverage: Mapping[str, Any] | None = None,
    trusted_vibe_public_keys: frozenset[str] = frozenset(),
    trusted_judge_public_keys: frozenset[str] = frozenset(),
    remember_capability: Any | None = None,
) -> VibeHaltCapability:
    data = _mapping(receipt)
    if data is None:
        return InconclusiveCapability("missing_or_malformed")
    schema = data.get("schema")
    outcome = data.get("reported_outcome")
    if schema == CURRENT_VIBE_SCHEMA:
        if outcome == "findings":
            return RejectedCapability("findings")
        if outcome == "clean":
            return InconclusiveCapability("not_candidate_bound")
        return InconclusiveCapability(str(outcome or data.get("mode") or "unchecked"))
    if schema != PATCH_VIBE_SCHEMA:
        return InconclusiveCapability("unsupported_or_malformed_schema")
    if frozenset(data) != _PATCH_VIBE_KEYS:
        return InconclusiveCapability("malformed_candidate_bound_receipt")

    verifier = _mapping(data.get("verifier"))
    process = _mapping(data.get("process"))
    if (
        verifier is None
        or frozenset(verifier) != {"agent_uid", "run_id", "parent_run_id"}
        or process is None
        or frozenset(process) != {"exit_code", "timed_out", "output_limited"}
    ):
        return InconclusiveCapability("malformed_candidate_bound_receipt")
    exact_identity = (
        data.get("candidate_digest") == expected.candidate_digest
        and data.get("diff_sha256") == expected.diff_sha256
        and verifier
        == {
            "agent_uid": expected.vibe_verifier.agent_uid,
            "run_id": expected.vibe_verifier.run_id,
            "parent_run_id": expected.executor_run_id,
        }
        and expected.vibe_verifier.agent_uid != expected.executor_agent_uid
        and expected.vibe_verifier.run_id != expected.executor_run_id
    )
    if not exact_identity:
        return InconclusiveCapability("candidate_or_verifier_binding_mismatch")
    coverage = _mapping(signed_identity_coverage)
    expected_coverage = expected_vibe_halt_binding(data, expected=expected)
    if coverage is None or expected_coverage is None or coverage != expected_coverage:
        return InconclusiveCapability("identity_not_covered_by_judge_signature")
    signature = _mapping(data.get("signature"))
    verifier_public_key = _signature_public_key(signature)
    if verifier_public_key is None:
        return InconclusiveCapability("malformed_verifier_signature")
    if verifier_public_key != expected.vibe_verifier.signer_public_key:
        return InconclusiveCapability("verifier_signer_binding_mismatch")
    if remember_capability is None or not trusted_vibe_public_keys:
        return InconclusiveCapability("trusted_verifier_signature_required")
    if verifier_public_key not in trusted_vibe_public_keys:
        return InconclusiveCapability("untrusted_verifier_signature")
    if verifier_public_key in trusted_judge_public_keys:
        return InconclusiveCapability("verifier_key_not_independent")
    if not _signed_payload_valid(data, signature_field="signature"):
        return InconclusiveCapability("invalid_verifier_signature")
    if data.get("diff_bound") is not True or data.get("calibration_only") is not False:
        return InconclusiveCapability("not_candidate_bound")
    if data.get("ran") is not True:
        return InconclusiveCapability("unchecked")
    exit_code = process.get("exit_code")
    if (
        type(exit_code) is not int
        or exit_code != 0
        or process.get("timed_out") is not False
        or process.get("output_limited") is not False
    ):
        return InconclusiveCapability("incomplete_or_limited_execution")
    findings = data.get("findings")
    errors = data.get("errors")
    capability_blockers = data.get("blockers")
    if not isinstance(findings, list) or errors != [] or capability_blockers != []:
        return InconclusiveCapability("contradictory_capability_output")
    if outcome == "findings":
        if findings:
            return RejectedCapability("findings")
        return InconclusiveCapability("findings_without_evidence")
    if outcome != "clean":
        return InconclusiveCapability(str(outcome or "unchecked"))
    if findings:
        return InconclusiveCapability("clean_with_findings")
    receipt_sha256 = expected_coverage["receipt_sha256"]
    verified = VerifiedVibeHalt(
        candidate_digest=expected.candidate_digest,
        diff_sha256=expected.diff_sha256,
        verifier_agent_uid=expected.vibe_verifier.agent_uid,
        verifier_run_id=expected.vibe_verifier.run_id,
        verifier_public_key=verifier_public_key,
        receipt_sha256=receipt_sha256,
    )
    return remember_capability(verified, "vibe")


def evaluate_vibe_halt(
    receipt: Mapping[str, Any] | None,
    *,
    expected: ExpectedPromotionBindings,
    signed_identity_coverage: Mapping[str, Any] | None = None,
) -> VibeHaltCapability:
    """Classify Vibe evidence; public callers can never mint authority."""
    return _evaluate_vibe_halt(
        receipt,
        expected=expected,
        signed_identity_coverage=signed_identity_coverage,
    )


__all__ = ["evaluate_vibe_halt", "expected_vibe_halt_binding"]
