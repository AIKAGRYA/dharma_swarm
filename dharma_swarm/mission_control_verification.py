"""Pure consumer for a future governed A2A patch-verification envelope.

No live producer is implied. Success mints only an in-process projection
capability: never persistence or repository-effect authority. The nominal
registry prevents ordinary accidental forging in a cooperating Python process;
it is not a boundary against malicious memory or module mutation.
"""

from __future__ import annotations

import importlib
import re
import weakref
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

from dharma_swarm.forge_v1.forge_v2.promote import REQUIRED_RECEIPTS_V0_ABSENT
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

if TYPE_CHECKING:
    from dharma_swarm.mission_control_verification_vibe import (
        evaluate_vibe_halt,
        expected_vibe_halt_binding,
    )

CURRENT_VIBE_SCHEMA = "dharma.vibe_halt_observer.v1"
PATCH_VIBE_SCHEMA = "dharma.vibe_halt.patch_verification.v1"
FOUNDRY_PATCH_VERIFICATION_SCHEMA = "dharma.foundry.forge_patch_verification.v1"
SIGNED_VIBE_BINDING_SCHEMA = "dharma.vibe_halt.signed_binding.v2"
SIGNED_A2A_BINDING_SCHEMA = "dharma.forge.a2a_patch_binding.v2"
PATCH_VERIFICATION_SCHEMA = "dharma.forge.a2a_patch_verification.v2"
WARRANT_SCHEMA = "dharma.mission_control.patch_promotion_warrant.v2"

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


@dataclass(frozen=True, slots=True)
class VerifierPrincipalBinding:
    """One exact verifier role, durable run, and signing principal."""

    role: Literal["foundry", "vibe_halt"]
    agent_uid: str
    run_id: str
    signer_public_key: str

    def to_signed_binding(self, *, parent_run_id: str) -> dict[str, str]:
        return {
            "role": self.role,
            "agent_uid": self.agent_uid,
            "run_id": self.run_id,
            "parent_run_id": parent_run_id,
            "signer_public_key": self.signer_public_key,
        }


@dataclass(frozen=True, slots=True)
class VerificationSeparationClaim:
    """Distinct keys and durable roles; never OS-process or key-custody proof."""

    level: Literal["distinct_signing_principals"] = field(
        default="distinct_signing_principals",
        init=False,
    )
    independent_processes_proven: Literal[False] = field(default=False, init=False)

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "level": self.level,
            "independent_processes_proven": self.independent_processes_proven,
        }


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
    foundry_verifier: VerifierPrincipalBinding
    vibe_verifier: VerifierPrincipalBinding

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
            "foundry_verifier": self.foundry_verifier.to_signed_binding(
                parent_run_id=self.executor_run_id,
            ),
            "vibe_verifier": self.vibe_verifier.to_signed_binding(
                parent_run_id=self.executor_run_id,
            ),
        }


@dataclass(frozen=True, slots=True, weakref_slot=True)
class VerifiedVibeHalt:
    """Clean, diff-bound evidence from the exact Vibe signing principal."""

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


VibeHaltCapability: TypeAlias = (
    VerifiedVibeHalt | RejectedCapability | InconclusiveCapability
)


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
        if not _is_minted_capability(self, "warrant"):
            return PromotionRefusal(("unsealed_warrant",)).to_dict()
        binding = self.bindings.to_signed_binding()
        binding.pop("schema")
        return {
            "schema": self.schema,
            "capability_scope": "projection_only_gate",
            "repository_effect_authorized": False,
            "verification_separation": VerificationSeparationClaim().to_dict(),
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
    owned_evaluator: Any | None = None

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

    def evaluate_owned(
        authority: PatchPromotionVerifier,
        signed_patch_verification: Mapping[str, Any] | None,
        *,
        expected: ExpectedPromotionBindings,
        vibe_halt_receipt: Mapping[str, Any] | None,
    ) -> PromotionEvaluation:
        nonlocal owned_evaluator
        if owned_evaluator is None:
            from dharma_swarm.mission_control_verification_forge import (
                _build_owned_promotion_evaluator,
            )

            owned_evaluator = _build_owned_promotion_evaluator(remember)
        return owned_evaluator(
            authority,
            signed_patch_verification,
            expected=expected,
            vibe_halt_receipt=vibe_halt_receipt,
        )

    return is_minted, evaluate_owned


_is_minted_capability, _evaluate_owned_promotion_warrant = _new_capability_registry()


def _normal_public_key_hex(public_key: str | bytes) -> str:
    return (
        public_key.hex()
        if isinstance(public_key, bytes)
        else str(public_key).strip().lower()
    )


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
    """Pre-pinned trust policy; constructor access is not an authority boundary."""

    __slots__ = ("_foundry_keys_by_agent", "_judge_keys", "_vibe_keys_by_agent")

    def __init__(
        self,
        *,
        trusted_judge_public_keys: Iterable[str | bytes],
        trusted_foundry_verifier_public_keys: Mapping[str, Iterable[str | bytes]],
        trusted_vibe_verifier_public_keys: Mapping[str, Iterable[str | bytes]],
    ) -> None:
        judge_keys = _normalize_trust_roots(
            trusted_judge_public_keys,
            name="trusted_judge_public_keys",
        )
        principal_maps: list[tuple[str, Mapping[str, Iterable[str | bytes]]]] = [
            ("foundry", trusted_foundry_verifier_public_keys),
            ("vibe", trusted_vibe_verifier_public_keys),
        ]
        normalized: dict[str, Mapping[str, frozenset[str]]] = {}
        for role, supplied in principal_maps:
            keys_by_agent: dict[str, frozenset[str]] = {}
            for agent_uid, keys in supplied.items():
                if (
                    not isinstance(agent_uid, str)
                    or not agent_uid
                    or agent_uid != agent_uid.strip()
                ):
                    raise ValueError(
                        f"trusted {role} verifier identity must be non-empty"
                    )
                keys_by_agent[agent_uid] = _normalize_trust_roots(
                    keys,
                    name=f"trusted_{role}_verifier_public_keys[{agent_uid!r}]",
                )
            if not keys_by_agent:
                raise ValueError(
                    f"trusted_{role}_verifier_public_keys must not be empty"
                )
            normalized[role] = MappingProxyType(keys_by_agent)
        object.__setattr__(self, "_judge_keys", judge_keys)
        object.__setattr__(self, "_foundry_keys_by_agent", normalized["foundry"])
        object.__setattr__(self, "_vibe_keys_by_agent", normalized["vibe"])

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


_LAZY_EXPORTS = {
    "evaluate_vibe_halt": (
        "dharma_swarm.mission_control_verification_vibe",
        "evaluate_vibe_halt",
    ),
    "expected_vibe_halt_binding": (
        "dharma_swarm.mission_control_verification_vibe",
        "expected_vibe_halt_binding",
    ),
    "_evaluate_vibe_halt": (
        "dharma_swarm.mission_control_verification_vibe",
        "_evaluate_vibe_halt",
    ),
    "_mapping": ("dharma_swarm.mission_control_verification_vibe", "_mapping"),
    "_receipt_sha256": (
        "dharma_swarm.mission_control_verification_vibe",
        "_receipt_sha256",
    ),
    "_signature_public_key": (
        "dharma_swarm.mission_control_verification_vibe",
        "_signature_public_key",
    ),
    "_signed_packet_shape_valid": (
        "dharma_swarm.mission_control_verification_vibe",
        "_signed_packet_shape_valid",
    ),
    "_signed_payload_valid": (
        "dharma_swarm.mission_control_verification_vibe",
        "_signed_payload_valid",
    ),
    "_build_owned_promotion_evaluator": (
        "dharma_swarm.mission_control_verification_forge",
        "_build_owned_promotion_evaluator",
    ),
    "_expected_blockers": (
        "dharma_swarm.mission_control_verification_forge",
        "_expected_blockers",
    ),
    "_forge_blockers": (
        "dharma_swarm.mission_control_verification_forge",
        "_forge_blockers",
    ),
    "_patch_envelope_blockers": (
        "dharma_swarm.mission_control_verification_forge",
        "_patch_envelope_blockers",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve compatibility exports without importing helper modules eagerly."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "CANONICAL_PROMOTION_SAFETY",
    "CURRENT_VIBE_SCHEMA",
    "ExpectedPromotionBindings",
    "FOUNDRY_PATCH_VERIFICATION_SCHEMA",
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
    "VerificationSeparationClaim",
    "VerifierPrincipalBinding",
    "VibeHaltCapability",
    "WARRANT_SCHEMA",
    "evaluate_vibe_halt",
    "expected_vibe_halt_binding",
]
