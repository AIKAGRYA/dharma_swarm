"""Proposition-specific, evaluator-owned promotion semantics for chamber V0.

Serialized claims remain evidence, never permission. A promotable claim must
also carry an in-process verifier witness, and the evaluator must have been
configured independently with the exact obligation and a fixed candidate
effect. This is a trusted-process semantic boundary, not a Python sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping

from dharma_swarm.chamber.traces import stable_digest
from dharma_swarm.chamber.verification import (
    FreshProcessVerification,
    verification_is_attested,
)

RUNTIME_VERIFIER_PRINCIPAL = "RuntimeVerifier"
PROMOTE_EFFECT = "Promote"
_CLAIM_SEAL = object()


class SubjectKind(str, Enum):
    SATISFIES = "Satisfies"
    REFUTES = "Refutes"


class EvidenceArm(str, Enum):
    SCENARIO = "scenario"
    CONTROL = "control"


class Modality(str, Enum):
    GENERATED = "Generated"
    OBSERVED = "Observed"
    VENDOR_REPRODUCED = "VendorReproduced"
    MODEL_CHECKED = "ModelChecked"
    REPRODUCED = "Reproduced"


@dataclass(frozen=True, slots=True, eq=False)
class _VerifiedClaimWitness:
    seal: object
    claim_digest: str
    evidence_digest: str
    bundle_digest: str
    source_revision: str
    scope_digest: str

    def __reduce__(self) -> Any:
        raise TypeError("verified claim witness is not serializable")


@dataclass(frozen=True, slots=True)
class Claim:
    candidate_id: str
    evidence_arm: EvidenceArm
    proposition_id: str
    subject: SubjectKind
    modality: Modality
    principal_id: str
    source_revision: str
    bundle_digest: str
    scope_digest: str
    property_verdicts: tuple[tuple[str, bool], ...]
    evidence_digest: str
    fresh_process_count: int
    control_valid: bool
    _witness: object | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "evidence_arm": self.evidence_arm.value,
            "proposition_id": self.proposition_id,
            "subject": self.subject.value,
            "modality": self.modality.value,
            "principal_id": self.principal_id,
            "source_revision": self.source_revision,
            "bundle_digest": self.bundle_digest,
            "scope_digest": self.scope_digest,
            "property_verdicts": dict(self.property_verdicts),
            "evidence_digest": self.evidence_digest,
            "fresh_process_count": self.fresh_process_count,
            "control_valid": self.control_valid,
        }


@dataclass(frozen=True, slots=True)
class PromotionObligation:
    candidate_id: str
    evidence_arm: EvidenceArm
    proposition_id: str
    source_revision: str
    bundle_digest: str
    scope_digest: str
    required_properties: tuple[str, ...]
    effect_binding_id: str
    principal_id: str = RUNTIME_VERIFIER_PRINCIPAL
    effect: str = PROMOTE_EFFECT

    def __post_init__(self) -> None:
        if type(self.evidence_arm) is not EvidenceArm:
            raise ValueError("promotion obligation evidence arm must be typed")
        values = (
            self.candidate_id,
            self.proposition_id,
            self.source_revision,
            self.bundle_digest,
            self.scope_digest,
            self.effect_binding_id,
            self.principal_id,
            self.effect,
        )
        if not all(type(value) is str and value.strip() for value in values):
            raise ValueError("promotion obligation fields must be non-empty strings")
        if (
            type(self.required_properties) is not tuple
            or not self.required_properties
            or not all(type(prop) is str and prop for prop in self.required_properties)
            or len(set(self.required_properties)) != len(self.required_properties)
        ):
            raise ValueError("promotion obligation properties must be unique strings")
        if self.effect != PROMOTE_EFFECT:
            raise ValueError(f"promotion obligation effect must be {PROMOTE_EFFECT!r}")


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    allowed: bool
    code: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "code": self.code, "reason": self.reason}


@dataclass(frozen=True, slots=True, eq=False)
class _OperationalAuthorization:
    seal: object
    obligation_key: tuple[Any, ...]
    handler_token: object

    def __reduce__(self) -> Any:
        raise TypeError("operational authorization is not serializable")


def _obligation_key(obligation: PromotionObligation) -> tuple[Any, ...]:
    return (
        obligation.candidate_id,
        obligation.evidence_arm.value,
        obligation.proposition_id,
        obligation.source_revision,
        obligation.bundle_digest,
        obligation.scope_digest,
        obligation.required_properties,
        obligation.effect_binding_id,
        obligation.principal_id,
        obligation.effect,
    )


def _claim_is_attested(claim: Claim) -> bool:
    witness = claim._witness
    return (
        isinstance(witness, _VerifiedClaimWitness)
        and witness.seal is _CLAIM_SEAL
        and witness.claim_digest == stable_digest(claim.to_dict())
        and witness.evidence_digest == claim.evidence_digest
        and witness.bundle_digest == claim.bundle_digest
        and witness.source_revision == claim.source_revision
        and witness.scope_digest == claim.scope_digest
    )


def claim_from_verification(
    verification: FreshProcessVerification,
    proposition_id: str,
    *,
    use_control: bool = False,
) -> Claim:
    if type(proposition_id) is not str or not proposition_id:
        raise ValueError("proposition_id must be a non-empty string")
    if type(use_control) is not bool:
        raise ValueError("use_control must be a boolean")
    if not verification.verified or not verification_is_attested(verification):
        raise ValueError("verification lacks a live RuntimeVerifier witness")
    verdicts = (
        verification.control_property_verdicts
        if use_control
        else verification.property_verdicts
    )
    if proposition_id not in verdicts:
        raise ValueError(f"property was not activated: {proposition_id}")
    if verification.control_property_verdicts.get(proposition_id) is not True:
        raise ValueError(f"corrected control did not satisfy property: {proposition_id}")
    subject = SubjectKind.SATISFIES if verdicts[proposition_id] else SubjectKind.REFUTES
    evidence_arm = EvidenceArm.CONTROL if use_control else EvidenceArm.SCENARIO
    candidate_id = (
        verification.control_candidate_id
        if use_control
        else verification.scenario_candidate_id
    )
    receipt = verification.to_dict()
    claim = Claim(
        candidate_id=candidate_id,
        evidence_arm=evidence_arm,
        proposition_id=proposition_id,
        subject=subject,
        modality=Modality.REPRODUCED,
        principal_id=RUNTIME_VERIFIER_PRINCIPAL,
        source_revision=verification.source_revision,
        bundle_digest=verification.bundle_digest,
        scope_digest=verification.scope_digest,
        property_verdicts=tuple(sorted(verdicts.items())),
        evidence_digest=str(receipt["receipt_digest"]),
        fresh_process_count=verification.replays_completed,
        control_valid=verification.control_valid,
    )
    witness = _VerifiedClaimWitness(
        _CLAIM_SEAL,
        stable_digest(claim.to_dict()),
        claim.evidence_digest,
        claim.bundle_digest,
        claim.source_revision,
        claim.scope_digest,
    )
    return replace(claim, _witness=witness)


class PromotionEvaluator:
    """Fail-closed evaluator with separately configured policy and effects."""

    def __init__(
        self,
        *,
        authorized_obligations: Iterable[PromotionObligation] = (),
        effect_handlers: Mapping[tuple[str, str], Callable[[], Any]] | None = None,
        trusted_principals: Iterable[str] = (RUNTIME_VERIFIER_PRINCIPAL,),
        allow_worktree_for_tests: bool = False,
    ) -> None:
        self._trusted_principals = frozenset(str(item) for item in trusted_principals)
        self._authorized = frozenset(_obligation_key(item) for item in authorized_obligations)
        handlers = dict(effect_handlers or {})
        self._effect_handlers = MappingProxyType(handlers)
        self._handler_tokens = MappingProxyType({key: object() for key in handlers})
        self._allow_worktree_for_tests = allow_worktree_for_tests
        self._seal = object()
        self._issued: dict[_OperationalAuthorization, tuple[tuple[Any, ...], object]] = {}
        self._minted_obligations: set[tuple[Any, ...]] = set()

    def mint_authorization(self, obligation: PromotionObligation) -> object:
        """Mint only evaluator-policy state; evidence cannot add an obligation."""
        key = _obligation_key(obligation)
        if obligation.principal_id not in self._trusted_principals:
            raise PermissionError("obligation principal is not evaluator-trusted")
        if key not in self._authorized:
            raise PermissionError("obligation is not evaluator-authorized policy")
        handler_key = (obligation.candidate_id, obligation.effect_binding_id)
        if handler_key not in self._effect_handlers:
            raise PermissionError("candidate has no evaluator-registered effect")
        if key in self._minted_obligations:
            raise PermissionError("obligation authorization was already minted")
        handler_token = self._handler_tokens[handler_key]
        capability = _OperationalAuthorization(self._seal, key, handler_token)
        self._issued[capability] = (key, handler_token)
        self._minted_obligations.add(key)
        return capability

    def evaluate(
        self,
        claim: Claim,
        obligation: PromotionObligation,
        capability: object | None,
    ) -> PromotionDecision:
        if claim.subject is not SubjectKind.SATISFIES:
            return _deny("EPI-SUBJECT-REFUTES", "a reproduced violation cannot promote")
        if claim.modality is not Modality.REPRODUCED:
            return _deny("EPI-MODALITY-MISMATCH", "claim is not RuntimeVerifier-reproduced")
        if claim.principal_id != obligation.principal_id:
            return _deny("EPI-PRINCIPAL-MISMATCH", "claim principal differs from obligation")
        if claim.principal_id not in self._trusted_principals:
            return _deny("EPI-PRINCIPAL-UNTRUSTED", "claim principal is not evaluator-trusted")
        if claim.candidate_id != obligation.candidate_id:
            return _deny("EPI-CANDIDATE-MISMATCH", "claim candidate differs from obligation")
        if claim.evidence_arm is not obligation.evidence_arm:
            return _deny("EPI-ARM-MISMATCH", "claim evidence arm differs from obligation")
        if claim.proposition_id != obligation.proposition_id:
            return _deny("EPI-PROP-MISMATCH", "claim does not discharge the obligation")
        if claim.source_revision != obligation.source_revision:
            return _deny("EPI-REVISION-MISMATCH", "claim and candidate revisions differ")
        if claim.source_revision == "WORKTREE" and not self._allow_worktree_for_tests:
            return _deny("EPI-REVISION-UNDURABLE", "worktree evidence cannot promote")
        if claim.bundle_digest != obligation.bundle_digest:
            return _deny("EPI-BUNDLE-MISMATCH", "claim and obligation bundles differ")
        if claim.scope_digest != obligation.scope_digest:
            return _deny("EPI-SCOPE-MISMATCH", "claim and candidate scopes differ")
        verdicts = dict(claim.property_verdicts)
        missing = sorted(prop for prop in obligation.required_properties if prop not in verdicts)
        if missing:
            return _deny("EPI-PROPERTIES-MISSING", f"properties not activated: {missing}")
        failed = sorted(prop for prop in obligation.required_properties if verdicts[prop] is not True)
        if failed:
            return _deny("EPI-PROPERTIES-FAILED", f"required properties failed: {failed}")
        if not claim.control_valid:
            return _deny("EPI-CONTROL-INVALID", "corrected control did not discriminate")
        if claim.fresh_process_count < 1:
            return _deny("EPI-FRESH-PROCESS-MISSING", "no fresh-process verification exists")
        if not _claim_is_attested(claim):
            return _deny("EPI-EVIDENCE-UNATTESTED", "serialized or fabricated claim lacks witness")
        if not isinstance(capability, _OperationalAuthorization):
            return _deny("EPI-AUTHORITY-MISSING", "serialized data is not permission")
        issued_binding = self._issued.get(capability)
        if issued_binding is None or capability.seal is not self._seal:
            return _deny("EPI-AUTHORITY-UNISSUED", "capability was not minted here")
        expected_key = _obligation_key(obligation)
        handler_key = (obligation.candidate_id, obligation.effect_binding_id)
        handler_token = self._handler_tokens.get(handler_key)
        if (
            capability.obligation_key != expected_key
            or capability.handler_token is not handler_token
            or issued_binding != (expected_key, handler_token)
            or expected_key not in self._authorized
        ):
            return _deny("EPI-AUTHORITY-MISMATCH", "capability differs from evaluator policy")
        if handler_key not in self._effect_handlers:
            return _deny("EPI-EFFECT-UNBOUND", "candidate effect is not evaluator-registered")
        return PromotionDecision(True, "ALLOW", "exact proof, policy, and authority")

    def promote(
        self,
        claim: Claim,
        obligation: PromotionObligation,
        capability: object | None,
    ) -> PromotionDecision:
        decision = self.evaluate(claim, obligation, capability)
        if not decision.allowed:
            return decision
        assert isinstance(capability, _OperationalAuthorization)
        self._issued.pop(capability)
        handler_key = (obligation.candidate_id, obligation.effect_binding_id)
        self._effect_handlers[handler_key]()
        return decision


def _deny(code: str, reason: str) -> PromotionDecision:
    return PromotionDecision(False, code, reason)


__all__ = [
    "PROMOTE_EFFECT",
    "RUNTIME_VERIFIER_PRINCIPAL",
    "Claim",
    "EvidenceArm",
    "Modality",
    "PromotionDecision",
    "PromotionEvaluator",
    "PromotionObligation",
    "SubjectKind",
    "claim_from_verification",
]
