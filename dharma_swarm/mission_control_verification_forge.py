"""Canonical Forge envelope validation and projection-only warrant minting."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from dharma_swarm.forge_v1.forge_v2.promote import REQUIRED_RECEIPTS_V0_ABSENT
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    verify_promotion_verification_signature,
)
from dharma_swarm.mission_control_verification import (
    CANONICAL_PROMOTION_SAFETY,
    PATCH_VERIFICATION_SCHEMA,
    REQUIRED_PROMOTION_PREDICATES,
    _FOUNDRY_DIGEST_RE,
    _GIT_SHA_RE,
    _SHA256_RE,
    ExpectedPromotionBindings,
    PatchPromotionVerifier,
    PatchPromotionWarrant,
    PromotionEvaluation,
    PromotionRefusal,
    VerifiedVibeHalt,
)
from dharma_swarm.mission_control_verification_vibe import (
    _evaluate_vibe_halt,
    _mapping,
    _signed_packet_shape_valid,
    expected_vibe_halt_binding,
)

_PATCH_VERIFICATION_KEYS = frozenset(
    "schema forge_verification a2a_binding vibe_halt_binding payload_sha256 verification_signature".split()
)
_FORGE_PACKET_KEYS = frozenset(
    """schema decision live_apply_allowed promotion_packet governed_admission
    telos signed_receipts operator_lease_present authorized_source_files
    blockers payload_sha256 verification_signature""".split()
)
_PROMOTION_PACKET_KEYS = frozenset(
    """schema decision arm taskbed mission_class run_id signal_key epoch_id
    evidence_strength predicate failed_conjuncts blockers
    report_positive_promotion_allowed safety payload_sha256""".split()
)
_ADMISSION_KEYS = frozenset(
    "request_id decision reasons required_receipts reduced_authority".split()
)
_REDUCED_AUTHORITY_KEYS = frozenset(
    "work_kind risk_tier allowed_files forbidden_files autonomy_level".split()
)
_TELOS_KEYS = frozenset("decision receipt_sha256 keyword".split())
_TELOS_KEYWORD_KEYS = frozenset("decision gate reason".split())


def _expected_blockers(expected: ExpectedPromotionBindings) -> list[str]:
    blockers: list[str] = []
    scalar_names = (
        "mission_id", "task_id", "attempt_id", "lease_id", "packet_id",
        "correlation_id", "delivery_id", "proposal_id", "candidate_digest",
        "diff_sha256", "base_sha", "artifact_sha256", "lineage_digest",
        "command_digest", "output_digest", "isolation_digest", "executor_agent_uid",
        "executor_run_id", "verifier_agent_uid", "verifier_run_id",
        "verifier_parent_run_id",
    )
    for name in scalar_names:
        value = getattr(expected, name, None)
        if not isinstance(value, str) or not value or value != value.strip():
            blockers.append(f"invalid_expected:{name}")
    for name in ("diff_sha256", "artifact_sha256"):
        value = getattr(expected, name, None)
        if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
            blockers.append(f"invalid_expected:{name}_shape")
    for name in (
        "candidate_digest", "lineage_digest", "command_digest", "output_digest",
        "isolation_digest",
    ):
        value = getattr(expected, name, None)
        if not isinstance(value, str) or _FOUNDRY_DIGEST_RE.fullmatch(value) is None:
            blockers.append(f"invalid_expected:{name}_shape")
    if (
        not isinstance(getattr(expected, "base_sha", None), str)
        or _GIT_SHA_RE.fullmatch(expected.base_sha) is None
    ):
        blockers.append("invalid_expected:base_sha_shape")
    files = getattr(expected, "authorized_source_files", None)
    if not isinstance(files, tuple) or not files:
        blockers.append("invalid_expected:authorized_source_files")
    else:
        if len(set(files)) != len(files):
            blockers.append("invalid_expected:duplicate_authorized_source_files")
        for path in files:
            parts = path.split("/") if isinstance(path, str) else []
            if (
                not isinstance(path, str)
                or not path
                or path != path.strip()
                or path.startswith("/")
                or any(part in {"", ".", ".."} for part in parts)
            ):
                blockers.append("invalid_expected:authorized_source_file")
                break
    if expected.attempt_id != expected.packet_id:
        blockers.append("native_attempt_not_packet_bound")
    if expected.lease_id != expected.delivery_id:
        blockers.append("native_lease_not_delivery_bound")
    if expected.correlation_id != f"a2a_send:{expected.executor_agent_uid}:{expected.packet_id}":
        blockers.append("correlation_not_executor_packet_bound")
    if expected.executor_agent_uid == expected.verifier_agent_uid:
        blockers.append("verifier_agent_not_independent")
    if expected.executor_run_id == expected.verifier_run_id:
        blockers.append("verifier_run_not_independent")
    if expected.verifier_parent_run_id != expected.executor_run_id:
        blockers.append("verifier_parent_not_executor_run")
    return blockers


def _forge_blockers(
    packet: dict[str, Any],
    *,
    expected: ExpectedPromotionBindings,
    trusted_judge_public_keys: Iterable[str | bytes],
) -> tuple[list[str], bool]:
    blockers: list[str] = []
    signature_shape_valid = _signed_packet_shape_valid(packet)
    signature_valid = signature_shape_valid and verify_promotion_verification_signature(
        packet, trusted_public_keys=trusted_judge_public_keys
    )
    if not signature_shape_valid:
        blockers.append("forge:verification_signature_shape")
    if not signature_valid:
        blockers.append("untrusted_or_invalid_forge_signature")
    if frozenset(packet) != _FORGE_PACKET_KEYS:
        blockers.append("forge:packet_shape")
    for name, value in (("schema", "forge_v2.promotion_verification.v1"), ("decision", "allow")):
        if packet.get(name) != value:
            blockers.append(f"forge:{name}")
    for name in ("live_apply_allowed", "operator_lease_present"):
        if packet.get(name) is not True:
            blockers.append(f"forge:{name}")
    if packet.get("blockers") != []:
        blockers.append("forge:blockers")

    promotion = _mapping(packet.get("promotion_packet"))
    if promotion is None:
        blockers.append("forge:promotion_packet")
    else:
        if frozenset(promotion) != _PROMOTION_PACKET_KEYS:
            blockers.append("forge:promotion_packet_shape")
        if promotion.get("schema") != "forge_v2.promotion_packet.v1":
            blockers.append("forge:promotion_packet_schema")
        if promotion.get("decision") != "promotable_candidate":
            blockers.append("forge:promotion_decision")
        if promotion.get("failed_conjuncts") != [] or promotion.get("blockers") != []:
            blockers.append("forge:promotion_conjuncts")
        for name in ("arm", "taskbed", "mission_class", "signal_key", "epoch_id"):
            value = promotion.get(name)
            if not isinstance(value, str) or not value or value != value.strip():
                blockers.append(f"forge:promotion_{name}")
        if promotion.get("run_id") != expected.verifier_run_id:
            blockers.append("forge:promotion_run_id")
        strength = promotion.get("evidence_strength")
        if type(strength) not in {int, float} or not math.isfinite(strength) or strength <= 0:
            blockers.append("forge:promotion_evidence_strength")
        if promotion.get("report_positive_promotion_allowed") is not False:
            blockers.append("forge:promotion_report_flag")
        predicate = _mapping(promotion.get("predicate"))
        if (
            predicate is None
            or frozenset(predicate) != REQUIRED_PROMOTION_PREDICATES
            or any(value is not True for value in predicate.values())
        ):
            blockers.append("forge:promotion_predicate")
        safety = _mapping(promotion.get("safety"))
        if (
            safety is None
            or frozenset(safety) != {name for name, _ in CANONICAL_PROMOTION_SAFETY}
            or any(safety.get(name) is not value for name, value in CANONICAL_PROMOTION_SAFETY)
        ):
            blockers.append("forge:promotion_safety")
        promotion_digest = promotion.get("payload_sha256")
        try:
            promotion_body = {
                key: value for key, value in promotion.items() if key != "payload_sha256"
            }
            digest_valid = (
                isinstance(promotion_digest, str)
                and _SHA256_RE.fullmatch(promotion_digest) is not None
                and canonical_sha256(promotion_body) == promotion_digest
            )
        except Exception:
            digest_valid = False
        if not digest_valid:
            blockers.append("forge:promotion_payload_sha256")

    admission = _mapping(packet.get("governed_admission"))
    reduced = _mapping(admission.get("reduced_authority")) if admission else None
    if (
        admission is None
        or frozenset(admission) != _ADMISSION_KEYS
        or admission.get("decision") != "allow"
        or admission.get("reasons") != []
        or admission.get("required_receipts") != []
        or not isinstance(admission.get("request_id"), str)
        or not admission.get("request_id")
        or (promotion is not None and admission.get("request_id") != promotion.get("signal_key"))
        or reduced is None
        or frozenset(reduced) != _REDUCED_AUTHORITY_KEYS
        or reduced
        != {
            "work_kind": "promotion",
            "risk_tier": "Q4",
            "allowed_files": list(expected.authorized_source_files),
            "forbidden_files": [],
            "autonomy_level": "operator_lease",
        }
    ):
        blockers.append("forge:governed_admission")
    telos = _mapping(packet.get("telos"))
    keyword = _mapping(telos.get("keyword")) if telos else None
    keyword_valid = keyword == {} or (
        keyword is not None
        and frozenset(keyword) == _TELOS_KEYWORD_KEYS
        and keyword.get("decision") == "allow"
        and isinstance(keyword.get("gate"), str)
        and isinstance(keyword.get("reason"), str)
    )
    if (
        telos is None
        or frozenset(telos) != _TELOS_KEYS
        or telos.get("decision") != "allow"
        or not isinstance(telos.get("receipt_sha256"), str)
        or _SHA256_RE.fullmatch(telos["receipt_sha256"]) is None
        or not keyword_valid
    ):
        blockers.append("forge:telos")
    receipts = _mapping(packet.get("signed_receipts"))
    if (
        receipts is None
        or frozenset(receipts) != frozenset(REQUIRED_RECEIPTS_V0_ABSENT)
        or any(receipts.get(name) is not True for name in REQUIRED_RECEIPTS_V0_ABSENT)
    ):
        blockers.append("forge:required_signed_receipts")
    if packet.get("authorized_source_files") != list(expected.authorized_source_files):
        blockers.append("forge:authorized_source_files")
    return blockers, signature_valid


def _patch_envelope_blockers(
    envelope: dict[str, Any],
    *,
    expected: ExpectedPromotionBindings,
    vibe_halt_receipt: Mapping[str, Any] | None,
    trusted_judge_public_keys: frozenset[str],
) -> tuple[list[str], dict[str, Any] | None, bool, bool]:
    blockers: list[str] = []
    outer_signature_shape = _signed_packet_shape_valid(envelope)
    outer_signature_valid = outer_signature_shape and verify_promotion_verification_signature(
        envelope, trusted_public_keys=trusted_judge_public_keys,
    )
    if frozenset(envelope) != _PATCH_VERIFICATION_KEYS:
        blockers.append("patch:envelope_shape")
    if envelope.get("schema") != PATCH_VERIFICATION_SCHEMA:
        blockers.append("patch:schema")
    if not outer_signature_shape:
        blockers.append("patch:verification_signature_shape")
    if not outer_signature_valid:
        blockers.append("untrusted_or_invalid_patch_signature")
    if envelope.get("a2a_binding") != expected.to_signed_binding():
        blockers.append("patch:a2a_binding")
    expected_vibe_binding = (
        expected_vibe_halt_binding(vibe_halt_receipt, expected=expected)
        if isinstance(vibe_halt_receipt, Mapping)
        else None
    )
    if expected_vibe_binding is None or envelope.get("vibe_halt_binding") != expected_vibe_binding:
        blockers.append("patch:vibe_halt_binding")
    forge_packet = _mapping(envelope.get("forge_verification"))
    forge_signature_valid = False
    if forge_packet is None:
        blockers.append("patch:forge_verification")
    else:
        forge_blockers, forge_signature_valid = _forge_blockers(
            forge_packet,
            expected=expected,
            trusted_judge_public_keys=trusted_judge_public_keys,
        )
        blockers.extend(forge_blockers)
    return blockers, forge_packet, outer_signature_valid, forge_signature_valid


def _build_owned_promotion_evaluator(remember_capability: Any):
    def evaluate(
        authority: PatchPromotionVerifier,
        signed_patch_verification: Mapping[str, Any] | None,
        *,
        expected: ExpectedPromotionBindings,
        vibe_halt_receipt: Mapping[str, Any] | None,
    ) -> PromotionEvaluation:
        try:
            envelope = _mapping(signed_patch_verification)
            if envelope is None:
                return PromotionRefusal(("malformed_patch_verification",))
            blockers = _expected_blockers(expected)
            envelope_blockers, forge_packet, outer_valid, forge_valid = _patch_envelope_blockers(
                envelope,
                expected=expected,
                vibe_halt_receipt=vibe_halt_receipt,
                trusted_judge_public_keys=authority._judge_keys,  # noqa: SLF001
            )
            blockers.extend(envelope_blockers)
            trusted_vibe_keys = authority._vibe_keys_by_agent.get(  # noqa: SLF001
                expected.verifier_agent_uid,
                frozenset(),
            )
            signatures_authoritative = outer_valid and forge_valid
            vibe = _evaluate_vibe_halt(
                vibe_halt_receipt,
                expected=expected,
                signed_identity_coverage=_mapping(envelope.get("vibe_halt_binding")),
                trusted_vibe_public_keys=(
                    trusted_vibe_keys if signatures_authoritative else frozenset()
                ),
                trusted_judge_public_keys=authority._judge_keys,  # noqa: SLF001
                remember_capability=(remember_capability if signatures_authoritative else None),
            )
            if not isinstance(vibe, VerifiedVibeHalt) or not vibe:
                reason = getattr(vibe, "reason", "unsealed_verified_capability")
                blockers.append(f"vibe_halt:{reason}")
            if blockers:
                return PromotionRefusal(tuple(dict.fromkeys(blockers)))
            if forge_packet is None:
                return PromotionRefusal(("patch:forge_verification",))
            patch_digest = envelope.get("payload_sha256")
            forge_digest = forge_packet.get("payload_sha256")
            if (
                not isinstance(patch_digest, str)
                or _SHA256_RE.fullmatch(patch_digest) is None
                or not isinstance(forge_digest, str)
                or _SHA256_RE.fullmatch(forge_digest) is None
            ):
                return PromotionRefusal(("patch:evidence_digest",))
            warrant = PatchPromotionWarrant(
                bindings=expected,
                patch_verification_sha256=patch_digest,
                forge_verification_sha256=forge_digest,
                vibe_halt_receipt_sha256=vibe.receipt_sha256,
            )
            return remember_capability(warrant, "warrant")
        except Exception:
            return PromotionRefusal(("malformed_evidence",))

    return evaluate


__all__ = []
