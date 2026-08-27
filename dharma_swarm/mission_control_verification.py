"""Pure consumer for a future governed A2A patch-verification envelope.

No live producer is implied. Success mints only an in-process projection
capability: never persistence or repository-effect authority. The nominal
registry prevents ordinary accidental forging in a cooperating Python process;
it is not a boundary against malicious memory or module mutation.
"""

from __future__ import annotations

import math
import json
import re
import weakref
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, TypeAlias

from dharma_swarm.forge_v1.forge_v2.promote import REQUIRED_RECEIPTS_V0_ABSENT
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    verify_promotion_verification_signature,
)

CURRENT_VIBE_SCHEMA = "dharma.vibe_halt_observer.v1"
PATCH_VIBE_SCHEMA = "dharma.vibe_halt.patch_verification.v1"
SIGNED_VIBE_BINDING_SCHEMA = "dharma.vibe_halt.signed_binding.v1"
SIGNED_A2A_BINDING_SCHEMA = "dharma.forge.a2a_patch_binding.v1"
PATCH_VERIFICATION_SCHEMA = "dharma.forge.a2a_patch_verification.v1"
WARRANT_SCHEMA = "dharma.mission_control.patch_promotion_warrant.v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FOUNDRY_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ED25519_SIGNATURE_RE = re.compile(r"^[0-9a-f]{128}$")
_REQUIRED_EVIDENCE_PREDICATES = frozenset(
    """receipt_core_present stats_confirm_gate e4_confirm_full_500
    e4_no_split_confirm e4_target_effect_ge_5pp e4_confirm_power_sufficient
    fdr_significant contamination_self_mod_clean contamination_sealed_provenance
    class_null_valid null_did_not_survive evidence_strength_positive
    packet_guard_review_present packet_guard_passed
    e4_discrimination_receipt_present e4_discrimination_passed""".split()
)
REQUIRED_PROMOTION_PREDICATES = _REQUIRED_EVIDENCE_PREDICATES | frozenset(
    f"receipt_{name}_present" for name in REQUIRED_RECEIPTS_V0_ABSENT
)
CANONICAL_PROMOTION_SAFETY = (
    ("shadow_only", True), ("live_apply_allowed", False), ("code_diff_allowed", False)
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
_PATCH_VIBE_KEYS = frozenset(
    """schema candidate_digest diff_sha256 verifier ran reported_outcome
    diff_bound calibration_only process findings errors blockers payload_sha256
    signature""".split()
)
_ADMISSION_KEYS = frozenset(
    "request_id decision reasons required_receipts reduced_authority".split()
)
_REDUCED_AUTHORITY_KEYS = frozenset(
    "work_kind risk_tier allowed_files forbidden_files autonomy_level".split()
)
_TELOS_KEYS = frozenset("decision receipt_sha256 keyword".split())
_TELOS_KEYWORD_KEYS = frozenset("decision gate reason".split())
_SIGNATURE_KEYS = frozenset("scheme key_id public_key signature".split())


@dataclass(frozen=True, slots=True)
class ExpectedPromotionBindings:
    """Exact identities and digests one signed verdict must authorize."""

    mission_id: str
    task_id: str
    attempt_id: str
    lease_id: str
    packet_id: str
    correlation_id: str
    delivery_id: str
    proposal_id: str
    candidate_digest: str
    diff_sha256: str
    base_sha: str
    artifact_sha256: str
    lineage_digest: str
    command_digest: str
    output_digest: str
    isolation_digest: str
    authorized_source_files: tuple[str, ...]
    executor_agent_uid: str
    executor_run_id: str
    verifier_agent_uid: str
    verifier_run_id: str
    verifier_parent_run_id: str

    def to_signed_binding(self) -> dict[str, Any]:
        """Return the exact block that must be covered by the judge signature."""
        return {
            "schema": SIGNED_A2A_BINDING_SCHEMA,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "lease_id": self.lease_id,
            "packet_id": self.packet_id,
            "correlation_id": self.correlation_id,
            "delivery_id": self.delivery_id,
            "proposal_id": self.proposal_id,
            "candidate_digest": self.candidate_digest,
            "diff_sha256": self.diff_sha256,
            "base_sha": self.base_sha,
            "artifact_sha256": self.artifact_sha256,
            "lineage_digest": self.lineage_digest,
            "command_digest": self.command_digest,
            "output_digest": self.output_digest,
            "isolation_digest": self.isolation_digest,
            "authorized_source_files": list(self.authorized_source_files),
            "executor": {
                "agent_uid": self.executor_agent_uid,
                "run_id": self.executor_run_id,
            },
            "verifier": {
                "agent_uid": self.verifier_agent_uid,
                "run_id": self.verifier_run_id,
                "parent_run_id": self.verifier_parent_run_id,
            },
        }


@dataclass(frozen=True, slots=True, weakref_slot=True)
class VerifiedVibeHalt:
    """Inhabited only by a clean, diff-bound, independently run capability."""

    candidate_digest: str
    diff_sha256: str
    verifier_agent_uid: str
    verifier_run_id: str
    verifier_public_key: str
    receipt_sha256: str

    def __bool__(self) -> bool:
        return _is_minted_capability(self, "vibe")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("VerifiedVibeHalt is a final nominal capability")


@dataclass(frozen=True, slots=True)
class RejectedCapability:
    """A capability ran and produced a substantive rejecting finding."""

    reason: str

    def __bool__(self) -> Literal[False]:
        return False


@dataclass(frozen=True, slots=True)
class InconclusiveCapability:
    """Evidence is absent, malformed, unchecked, or not candidate-bound."""

    reason: str

    def __bool__(self) -> Literal[False]:
        return False


VibeHaltCapability: TypeAlias = VerifiedVibeHalt | RejectedCapability | InconclusiveCapability


@dataclass(frozen=True, slots=True, weakref_slot=True)
class PatchPromotionWarrant:
    """In-process projection capability; never durable mutation authority."""

    bindings: ExpectedPromotionBindings
    patch_verification_sha256: str
    forge_verification_sha256: str
    vibe_halt_receipt_sha256: str
    schema: str = WARRANT_SCHEMA

    def __bool__(self) -> bool:
        return _is_minted_capability(self, "warrant")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("PatchPromotionWarrant is a final nominal capability")

    def to_dict(self) -> dict[str, Any]:
        # Avoid dynamic bool dispatch: subclasses cannot mint by overriding it.
        if not _is_minted_capability(self, "warrant"):
            return PromotionRefusal(("unsealed_warrant",)).to_dict()
        binding = self.bindings.to_signed_binding()
        binding.pop("schema")
        return {
            "schema": self.schema,
            "capability_scope": "projection_only_gate",
            "repository_effect_authorized": False,
            **binding,
            "patch_verification_sha256": self.patch_verification_sha256,
            "forge_verification_sha256": self.forge_verification_sha256,
            "vibe_halt_receipt_sha256": self.vibe_halt_receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class PromotionRefusal:
    """Fail-closed result; never usable as a promotion capability."""

    blockers: tuple[str, ...]

    def __bool__(self) -> Literal[False]:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "dharma.mission_control.patch_promotion_refusal.v1",
            "decision": "refused",
            "blockers": list(self.blockers),
        }


PromotionEvaluation: TypeAlias = PatchPromotionWarrant | PromotionRefusal


def _capability_fingerprint(value: object, kind: str) -> str:
    if kind == "vibe" and type(value) is VerifiedVibeHalt:
        vibe = value
        return canonical_sha256(
            {
                "kind": kind,
                "candidate_digest": vibe.candidate_digest,
                "diff_sha256": vibe.diff_sha256,
                "verifier_agent_uid": vibe.verifier_agent_uid,
                "verifier_run_id": vibe.verifier_run_id,
                "verifier_public_key": vibe.verifier_public_key,
                "receipt_sha256": vibe.receipt_sha256,
            }
        )
    if kind == "warrant" and type(value) is PatchPromotionWarrant:
        warrant = value
        return canonical_sha256(
            {
                "kind": kind,
                "schema": warrant.schema,
                "bindings": warrant.bindings.to_signed_binding(),
                "patch_verification_sha256": warrant.patch_verification_sha256,
                "forge_verification_sha256": warrant.forge_verification_sha256,
                "vibe_halt_receipt_sha256": warrant.vibe_halt_receipt_sha256,
            }
        )
    return ""


def _new_capability_registry():
    entries: dict[int, tuple[weakref.ReferenceType[object], str, str]] = {}

    def remember(value: object, kind: str) -> object:
        identity = id(value)
        fingerprint = _capability_fingerprint(value, kind)

        def forget(reference: weakref.ReferenceType[object]) -> None:
            current = entries.get(identity)
            if current is not None and current[0] is reference:
                entries.pop(identity, None)

        reference = weakref.ref(value, forget)
        entries[identity] = (reference, kind, fingerprint)
        return value

    def is_minted(value: object, kind: str) -> bool:
        entry = entries.get(id(value))
        if entry is None:
            return False
        reference, recorded_kind, fingerprint = entry
        return (
            reference() is value
            and recorded_kind == kind
            and bool(fingerprint)
            and _capability_fingerprint(value, kind) == fingerprint
        )

    return is_minted, remember


_is_minted_capability, _remember_capability = _new_capability_registry()


def _normal_public_key_hex(public_key: str | bytes) -> str:
    return public_key.hex() if isinstance(public_key, bytes) else str(public_key).strip().lower()


def _normalize_trust_roots(
    public_keys: Iterable[str | bytes],
    *,
    name: str,
) -> frozenset[str]:
    roots = frozenset(_normal_public_key_hex(key) for key in public_keys)
    if not roots:
        raise ValueError(f"{name} must not be empty")
    if any(_SHA256_RE.fullmatch(key) is None for key in roots):
        raise ValueError(f"{name} must contain raw lowercase Ed25519 public keys")
    return roots


class PatchPromotionVerifier:
    """Immutable composition-owned trust policy and projection evaluator.

    Vibe keys are agent-bound and distinct from Forge judge authority.
    """

    __slots__ = ("_judge_keys", "_vibe_keys_by_agent")

    def __init__(
        self,
        *,
        trusted_judge_public_keys: Iterable[str | bytes],
        trusted_vibe_verifier_public_keys: Mapping[str, Iterable[str | bytes]],
    ) -> None:
        judge_keys = _normalize_trust_roots(
            trusted_judge_public_keys,
            name="trusted_judge_public_keys",
        )
        vibe_keys: dict[str, frozenset[str]] = {}
        for agent_uid, keys in trusted_vibe_verifier_public_keys.items():
            if not isinstance(agent_uid, str) or not agent_uid or agent_uid != agent_uid.strip():
                raise ValueError("trusted Vibe verifier identity must be non-empty")
            vibe_keys[agent_uid] = _normalize_trust_roots(
                keys,
                name=f"trusted_vibe_verifier_public_keys[{agent_uid!r}]",
            )
        if not vibe_keys:
            raise ValueError("trusted_vibe_verifier_public_keys must not be empty")
        object.__setattr__(self, "_judge_keys", judge_keys)
        object.__setattr__(self, "_vibe_keys_by_agent", MappingProxyType(vibe_keys))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} trust policy is immutable")

    def evaluate(
        self,
        signed_patch_verification: Mapping[str, Any] | None,
        *,
        expected: ExpectedPromotionBindings,
        vibe_halt_receipt: Mapping[str, Any] | None,
    ) -> PromotionEvaluation:
        return _evaluate_owned_promotion_warrant(
            self,
            signed_patch_verification,
            expected=expected,
            vibe_halt_receipt=vibe_halt_receipt,
        )


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


def _expected_blockers(expected: ExpectedPromotionBindings) -> list[str]:
    blockers: list[str] = []
    scalar_names = (
        "mission_id",
        "task_id",
        "attempt_id",
        "lease_id",
        "packet_id",
        "correlation_id",
        "delivery_id",
        "proposal_id",
        "candidate_digest",
        "diff_sha256",
        "base_sha",
        "artifact_sha256",
        "lineage_digest",
        "command_digest",
        "output_digest",
        "isolation_digest",
        "executor_agent_uid",
        "executor_run_id",
        "verifier_agent_uid",
        "verifier_run_id",
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
        "candidate_digest",
        "lineage_digest",
        "command_digest",
        "output_digest",
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
    if expected.correlation_id != (
        f"a2a_send:{expected.executor_agent_uid}:{expected.packet_id}"
    ):
        blockers.append("correlation_not_executor_packet_bound")
    if expected.executor_agent_uid == expected.verifier_agent_uid:
        blockers.append("verifier_agent_not_independent")
    if expected.executor_run_id == expected.verifier_run_id:
        blockers.append("verifier_run_not_independent")
    if expected.verifier_parent_run_id != expected.executor_run_id:
        blockers.append("verifier_parent_not_executor_run")
    return blockers


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
        "verifier_agent_uid": expected.verifier_agent_uid,
        "verifier_run_id": expected.verifier_run_id,
        "verifier_parent_run_id": expected.verifier_parent_run_id,
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
            "agent_uid": expected.verifier_agent_uid,
            "run_id": expected.verifier_run_id,
            "parent_run_id": expected.verifier_parent_run_id,
        }
        and expected.verifier_agent_uid != expected.executor_agent_uid
        and expected.verifier_run_id != expected.executor_run_id
        and expected.verifier_parent_run_id == expected.executor_run_id
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
        verifier_agent_uid=expected.verifier_agent_uid,
        verifier_run_id=expected.verifier_run_id,
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
    """Classify Vibe evidence; public callers can never mint authority.

    ``signed_identity_coverage`` remains accepted for structural diagnostics,
    but only a composition-owned :class:`PatchPromotionVerifier` can supply
    both trusted authority domains and access the nominal capability mint.
    """
    return _evaluate_vibe_halt(
        receipt,
        expected=expected,
        signed_identity_coverage=signed_identity_coverage,
    )


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
    exact_text = (
        ("schema", "forge_v2.promotion_verification.v1"),
        ("decision", "allow"),
    )
    for name, value in exact_text:
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
        if (
            type(strength) not in {int, float}
            or not math.isfinite(strength)
            or strength <= 0
        ):
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
        # Canonical Forge v2 still marks its nested statistical packet as
        # shadow-only.  Preserve that fact exactly; the separate signed outer
        # judge verdict, never this nested safety block, is the live authority.
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
                key: value
                for key, value in promotion.items()
                if key != "payload_sha256"
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
        or (
            promotion is not None
            and admission.get("request_id") != promotion.get("signal_key")
        )
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
        or any(
            receipts.get(name) is not True for name in REQUIRED_RECEIPTS_V0_ABSENT
        )
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
    outer_signature_valid = (
        outer_signature_shape
        and verify_promotion_verification_signature(
            envelope,
            trusted_public_keys=trusted_judge_public_keys,
        )
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
            (
                envelope_blockers,
                forge_packet,
                outer_signature_valid,
                forge_signature_valid,
            ) = _patch_envelope_blockers(
                envelope,
                expected=expected,
                vibe_halt_receipt=vibe_halt_receipt,
                trusted_judge_public_keys=authority._judge_keys,
            )
            blockers.extend(envelope_blockers)
            trusted_vibe_keys = authority._vibe_keys_by_agent.get(
                expected.verifier_agent_uid,
                frozenset(),
            )
            signatures_authoritative = outer_signature_valid and forge_signature_valid
            vibe = _evaluate_vibe_halt(
                vibe_halt_receipt,
                expected=expected,
                signed_identity_coverage=_mapping(envelope.get("vibe_halt_binding")),
                trusted_vibe_public_keys=(
                    trusted_vibe_keys if signatures_authoritative else frozenset()
                ),
                trusted_judge_public_keys=authority._judge_keys,
                remember_capability=(
                    remember_capability if signatures_authoritative else None
                ),
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


_evaluate_owned_promotion_warrant = _build_owned_promotion_evaluator(
    _remember_capability
)
del _remember_capability


__all__ = [
    "CANONICAL_PROMOTION_SAFETY",
    "CURRENT_VIBE_SCHEMA",
    "ExpectedPromotionBindings",
    "InconclusiveCapability",
    "PATCH_VERIFICATION_SCHEMA",
    "PATCH_VIBE_SCHEMA",
    "PatchPromotionVerifier",
    "PatchPromotionWarrant",
    "PromotionEvaluation",
    "PromotionRefusal",
    "RejectedCapability",
    "REQUIRED_PROMOTION_PREDICATES",
    "SIGNED_A2A_BINDING_SCHEMA",
    "SIGNED_VIBE_BINDING_SCHEMA",
    "VerifiedVibeHalt",
    "VibeHaltCapability",
    "WARRANT_SCHEMA",
    "evaluate_vibe_halt",
    "expected_vibe_halt_binding",
]
