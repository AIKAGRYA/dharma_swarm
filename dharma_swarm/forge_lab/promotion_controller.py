"""Independent aggregation and fail-closed RSI -> Foundry promotion control."""

from __future__ import annotations
import inspect
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Awaitable, Iterable, Mapping, Protocol
from dharma_swarm.a2a.candidate_lease import (
    LeaseVerification, OperatorLeaseVerifier, lease_result_is_exact,
)
from dharma_swarm.forge_lab.candidate_envelope import (
    CandidateEnvelope, EvidenceBinding, SignedCandidateEnvelope, TerminalDisposition, TerminalState,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import sign_receipt, verify_trusted_signed_receipt
INDEPENDENT_EVALUATION_SCHEMA = "forge_lab.independent_evaluation.v2"
EVALUATION_AGGREGATE_SCHEMA = "forge_lab.evaluation_aggregate.v1"
PROMOTION_DECISION_SCHEMA = "forge_lab.promotion_decision.v1"
CANARY_RESULT_EVIDENCE_SCHEMA = "forge_lab.canary_result_evidence.v1"
ROLLBACK_RESULT_EVIDENCE_SCHEMA = "forge_lab.rollback_result_evidence.v1"
INDEPENDENT_EVALUATION_RECEIPT = "rsi_foundry_independent_evaluation_v2"
PROMOTION_DECISION_RECEIPT = "rsi_foundry_promotion_decision"
CANARY_RESULT_RECEIPT = "rsi_foundry_canary_result"
ROLLBACK_RESULT_RECEIPT = "rsi_foundry_rollback_result"
class PromotionControlError(RuntimeError):
    """Raised when the controller cannot produce a truthful signed outcome."""
def _now(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise PromotionControlError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)
def _token(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PromotionControlError(f"{name} is required")
    return text
def _sha(value: Any, name: str, *, git: bool = False) -> str:
    text = str(value or "").strip().lower()
    sizes = (40, 64) if git else (64,)
    if len(text) not in sizes or any(ch not in "0123456789abcdef" for ch in text):
        raise PromotionControlError(f"{name} is not a full digest")
    return text
def _receipt_key(receipt: Mapping[str, Any]) -> str:
    signature = receipt.get("signature")
    return str(signature.get("public_key") if isinstance(signature, Mapping) else "").lower()
def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise PromotionControlError("signature receipt contains a non-JSON value")
def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def canary_result_evidence_content(
    *,
    canary_id: str,
    envelope_id: str,
    aggregate_id: str,
    healthy: bool,
    rollback_ready: bool,
    performed_at: str,
) -> dict[str, Any]:
    return {
        "schema": CANARY_RESULT_EVIDENCE_SCHEMA,
        "canary_id": canary_id,
        "envelope_id": envelope_id,
        "aggregate_id": aggregate_id,
        "healthy": healthy,
        "rollback_ready": rollback_ready,
        "performed_at": performed_at,
    }


def rollback_result_evidence_content(
    *,
    envelope_id: str,
    reason_code: str,
    rolled_back: bool,
    performed_at: str,
) -> dict[str, Any]:
    return {
        "schema": ROLLBACK_RESULT_EVIDENCE_SCHEMA,
        "envelope_id": envelope_id,
        "reason_code": reason_code,
        "rolled_back": rolled_back,
        "performed_at": performed_at,
    }
@dataclass(frozen=True)
class IndependentEvaluation:
    envelope_id: str
    candidate_id: str
    evaluator_id: str
    evaluator_sha: str
    evaluator_executable_sha256: str
    evaluator_release_tree_sha256: str
    target_sha: str
    outcome: str
    comparable: bool
    passed: bool
    score_micros: int
    isolation_receipt: EvidenceBinding
    evidence_receipt: EvidenceBinding
    created_at: str
    schema: str = INDEPENDENT_EVALUATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != INDEPENDENT_EVALUATION_SCHEMA:
            raise PromotionControlError(f"unsupported independent evaluation schema: {self.schema}")
        _sha(self.envelope_id, "envelope_id")
        _token(self.candidate_id, "candidate_id")
        _token(self.evaluator_id, "evaluator_id")
        _sha(self.evaluator_sha, "evaluator_sha", git=True)
        _sha(self.evaluator_executable_sha256, "evaluator_executable_sha256")
        _sha(self.evaluator_release_tree_sha256, "evaluator_release_tree_sha256")
        _sha(self.target_sha, "target_sha", git=True)
        _token(self.outcome, "outcome")
        if not isinstance(self.comparable, bool) or not isinstance(self.passed, bool):
            raise PromotionControlError("evaluation verdicts must be boolean")
        if not isinstance(self.isolation_receipt, EvidenceBinding) or not isinstance(
            self.evidence_receipt, EvidenceBinding
        ):
            raise PromotionControlError("evaluation receipts must be immutable evidence bindings")
        if not isinstance(self.score_micros, int) or isinstance(self.score_micros, bool):
            raise PromotionControlError("score_micros must be an integer")
        if not 0 <= self.score_micros <= 1_000_000:
            raise PromotionControlError("score_micros must be between 0 and 1,000,000")
        object.__setattr__(
            self, "created_at", _now(self.created_at).isoformat().replace("+00:00", "Z")
        )

    def content_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "envelope_id": self.envelope_id,
            "candidate_id": self.candidate_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_sha": self.evaluator_sha,
            "evaluator_executable_sha256": self.evaluator_executable_sha256,
            "evaluator_release_tree_sha256": self.evaluator_release_tree_sha256,
            "target_sha": self.target_sha,
            "outcome": self.outcome,
            "comparable": self.comparable,
            "passed": self.passed,
            "score_micros": self.score_micros,
            "isolation_receipt": self.isolation_receipt.to_dict(),
            "evidence_receipt": self.evidence_receipt.to_dict(),
            "created_at": self.created_at,
        }

    @property
    def evaluation_id(self) -> str:
        return canonical_sha256(self.content_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.content_dict(), "evaluation_id": self.evaluation_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IndependentEvaluation":
        expected = {
            "schema", "envelope_id", "candidate_id", "evaluator_id", "evaluator_sha",
            "evaluator_executable_sha256", "evaluator_release_tree_sha256", "target_sha",
            "outcome", "comparable", "passed", "score_micros",
            "isolation_receipt", "evidence_receipt", "created_at", "evaluation_id",
        }
        if set(payload) != expected:
            raise PromotionControlError("independent evaluation fields are invalid")
        evaluation = cls(
            envelope_id=str(payload.get("envelope_id") or ""),
            candidate_id=str(payload.get("candidate_id") or ""),
            evaluator_id=str(payload.get("evaluator_id") or ""),
            evaluator_sha=str(payload.get("evaluator_sha") or ""),
            evaluator_executable_sha256=str(
                payload.get("evaluator_executable_sha256") or ""
            ),
            evaluator_release_tree_sha256=str(
                payload.get("evaluator_release_tree_sha256") or ""
            ),
            target_sha=str(payload.get("target_sha") or ""),
            outcome=str(payload.get("outcome") or ""),
            comparable=payload.get("comparable"),
            passed=payload.get("passed"),
            score_micros=payload.get("score_micros"),
            isolation_receipt=EvidenceBinding.from_dict(payload.get("isolation_receipt") or {}),
            evidence_receipt=EvidenceBinding.from_dict(payload.get("evidence_receipt") or {}),
            created_at=str(payload.get("created_at") or ""),
            schema=str(payload.get("schema") or ""),
        )
        if payload.get("evaluation_id") != evaluation.evaluation_id:
            raise PromotionControlError("independent evaluation content hash mismatch")
        return evaluation


@dataclass(frozen=True)
class SignedIndependentEvaluation:
    evaluation: IndependentEvaluation
    signature_receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "signature_receipt", _freeze(self.signature_receipt))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation": self.evaluation.to_dict(),
            "signature_receipt": _thaw(self.signature_receipt),
        }

    def verify(self, *, trusted_public_keys: Iterable[str | bytes]) -> bool:
        receipt = _thaw(self.signature_receipt)
        return bool(
            receipt.get("name") == INDEPENDENT_EVALUATION_RECEIPT
            and receipt.get("payload") == self.evaluation.to_dict()
            and verify_trusted_signed_receipt(receipt, trusted_public_keys=trusted_public_keys)
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SignedIndependentEvaluation":
        if set(payload) != {"evaluation", "signature_receipt"}:
            raise PromotionControlError("signed evaluation fields are invalid")
        receipt = payload.get("signature_receipt")
        if not isinstance(receipt, Mapping):
            raise PromotionControlError("signed evaluation receipt is invalid")
        return cls(
            evaluation=IndependentEvaluation.from_dict(payload.get("evaluation") or {}),
            signature_receipt=dict(receipt),
        )


def sign_independent_evaluation(
    evaluation: IndependentEvaluation,
    *,
    signing_key: Any,
    authority_epoch_sha256: str,
    key_id: str = "",
) -> SignedIndependentEvaluation:
    return SignedIndependentEvaluation(
        evaluation=evaluation,
        signature_receipt=sign_receipt(
            name=INDEPENDENT_EVALUATION_RECEIPT,
            payload=evaluation.to_dict(),
            signing_key=signing_key,
            epoch_ruler_sha256=_sha(authority_epoch_sha256, "authority_epoch_sha256"),
            key_id=key_id,
        ),
    )


@dataclass(frozen=True)
class EvaluationAggregate:
    envelope_id: str
    candidate_id: str
    evaluation_ids: tuple[str, ...]
    evaluator_ids: tuple[str, ...]
    signer_public_keys: tuple[str, ...]
    minimum_independent: int
    conservative_score_micros: int
    passed: bool
    blockers: tuple[str, ...]
    schema: str = EVALUATION_AGGREGATE_SCHEMA

    def content_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def aggregate_id(self) -> str:
        return canonical_sha256(self.content_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.content_dict(), "aggregate_id": self.aggregate_id}


def aggregate_independent_evaluations(
    evaluations: Iterable[SignedIndependentEvaluation],
    *,
    envelope: CandidateEnvelope,
    trusted_public_keys: Iterable[str | bytes],
    excluded_evaluator_ids: Iterable[str] = (),
    excluded_signer_public_keys: Iterable[str | bytes] = (),
    minimum_independent: int = 2,
    as_of: str | None = None,
) -> EvaluationAggregate:
    if not isinstance(minimum_independent, int) or isinstance(minimum_independent, bool) or minimum_independent < 2:
        raise PromotionControlError("minimum_independent must be an integer of at least two")
    trusted = tuple(trusted_public_keys)
    excluded = {str(value) for value in excluded_evaluator_ids} | {envelope.authority_id}
    excluded_keys = {
        value.hex().lower() if isinstance(value, bytes) else str(value).lower()
        for value in excluded_signer_public_keys
    }
    seen_evaluators: set[str] = set()
    seen_keys: set[str] = set()
    accepted: list[IndependentEvaluation] = []
    blockers: set[str] = set()
    for signed in evaluations:
        item = signed.evaluation
        if not signed.verify(trusted_public_keys=trusted):
            blockers.add(f"untrusted_or_invalid_evaluation:{item.evaluator_id}")
            continue
        key = _receipt_key(signed.signature_receipt)
        if item.envelope_id != envelope.envelope_id or item.candidate_id != envelope.candidate_id:
            blockers.add(f"evaluation_binding_mismatch:{item.evaluator_id}")
            continue
        if item.target_sha != envelope.target_sha:
            blockers.add(f"evaluation_target_mismatch:{item.evaluator_id}")
            continue
        evaluation_at = _now(item.created_at)
        if not (
            _now(envelope.created_at) <= evaluation_at < _now(envelope.expires_at)
            and evaluation_at < _now(envelope.lease_expires_at)
            and (as_of is None or evaluation_at <= _now(as_of))
        ):
            blockers.add(f"evaluation_time_mismatch:{item.evaluator_id}")
            continue
        if any(
            not (_now(envelope.created_at) <= _now(receipt.created_at) <= evaluation_at)
            for receipt in (item.isolation_receipt, item.evidence_receipt)
        ):
            blockers.add(f"evaluation_evidence_time_mismatch:{item.evaluator_id}")
            continue
        if item.evaluator_id in excluded:
            blockers.add(f"evaluator_not_independent:{item.evaluator_id}")
            continue
        if not key or key in excluded_keys:
            blockers.add(f"evaluator_signer_not_independent:{item.evaluator_id}")
            continue
        if item.evaluator_id in seen_evaluators or key in seen_keys:
            blockers.add(f"duplicate_evaluator_lane:{item.evaluator_id}")
            continue
        seen_evaluators.add(item.evaluator_id)
        seen_keys.add(key)
        accepted.append(item)
        if not item.comparable or not item.passed:
            blockers.add(f"evaluation_not_passing:{item.evaluator_id}")
    if len(accepted) < minimum_independent:
        blockers.add(f"independent_quorum:{len(accepted)}/{minimum_independent}")
    accepted.sort(key=lambda item: (item.evaluator_id, item.evaluation_id))
    return EvaluationAggregate(
        envelope_id=envelope.envelope_id,
        candidate_id=envelope.candidate_id,
        evaluation_ids=tuple(item.evaluation_id for item in accepted),
        evaluator_ids=tuple(item.evaluator_id for item in accepted),
        signer_public_keys=tuple(sorted(seen_keys)),
        minimum_independent=minimum_independent,
        conservative_score_micros=min((item.score_micros for item in accepted), default=0),
        passed=not blockers,
        blockers=tuple(sorted(blockers)),
    )


@dataclass(frozen=True)
class CanaryResult:
    canary_id: str
    envelope_id: str
    aggregate_id: str
    healthy: bool
    rollback_ready: bool
    receipt: EvidenceBinding
    signature_receipt: Mapping[str, Any]

    def evidence_content(self) -> dict[str, Any]:
        """Return the complete typed result body committed by ``receipt``."""
        return canary_result_evidence_content(
            canary_id=self.canary_id,
            envelope_id=self.envelope_id,
            aggregate_id=self.aggregate_id,
            healthy=self.healthy,
            rollback_ready=self.rollback_ready,
            performed_at=self.receipt.created_at,
        )

    def __post_init__(self) -> None:
        _token(self.canary_id, "canary_id")
        _sha(self.envelope_id, "canary.envelope_id")
        _sha(self.aggregate_id, "canary.aggregate_id")
        if not isinstance(self.healthy, bool) or not isinstance(self.rollback_ready, bool):
            raise PromotionControlError("canary verdicts must be boolean")
        if not isinstance(self.receipt, EvidenceBinding):
            raise PromotionControlError("canary receipt must be an immutable evidence binding")
        if self.receipt.schema != CANARY_RESULT_EVIDENCE_SCHEMA:
            raise PromotionControlError("canary receipt schema is not the typed result schema")
        if self.receipt.sha256 != canonical_sha256(self.evidence_content()):
            raise PromotionControlError("canary receipt does not bind the exact result content")
        if not isinstance(self.signature_receipt, Mapping):
            raise PromotionControlError("canary signature receipt is required")
        object.__setattr__(self, "signature_receipt", _freeze(self.signature_receipt))
        signed = _thaw(self.signature_receipt)
        if signed.get("name") != CANARY_RESULT_RECEIPT or signed.get("payload") != self.evidence_content():
            raise PromotionControlError("canary signature receipt does not contain the exact result body")

    def verify(self, *, trusted_public_keys: Iterable[str | bytes]) -> bool:
        return verify_trusted_signed_receipt(
            _thaw(self.signature_receipt), trusted_public_keys=trusted_public_keys,
        )


@dataclass(frozen=True)
class RollbackResult:
    envelope_id: str
    reason_code: str
    rolled_back: bool
    receipt: EvidenceBinding
    signature_receipt: Mapping[str, Any]

    def evidence_content(self) -> dict[str, Any]:
        """Return the complete typed rollback body committed by ``receipt``."""
        return rollback_result_evidence_content(
            envelope_id=self.envelope_id,
            reason_code=self.reason_code,
            rolled_back=self.rolled_back,
            performed_at=self.receipt.created_at,
        )

    def __post_init__(self) -> None:
        _sha(self.envelope_id, "rollback.envelope_id")
        _token(self.reason_code, "rollback.reason_code")
        if not isinstance(self.rolled_back, bool):
            raise PromotionControlError("rollback verdict must be boolean")
        if not isinstance(self.receipt, EvidenceBinding):
            raise PromotionControlError("rollback receipt must be an immutable evidence binding")
        if self.receipt.schema != ROLLBACK_RESULT_EVIDENCE_SCHEMA:
            raise PromotionControlError("rollback receipt schema is not the typed result schema")
        if self.receipt.sha256 != canonical_sha256(self.evidence_content()):
            raise PromotionControlError("rollback receipt does not bind the exact result content")
        if not isinstance(self.signature_receipt, Mapping):
            raise PromotionControlError("rollback signature receipt is required")
        object.__setattr__(self, "signature_receipt", _freeze(self.signature_receipt))
        signed = _thaw(self.signature_receipt)
        if signed.get("name") != ROLLBACK_RESULT_RECEIPT or signed.get("payload") != self.evidence_content():
            raise PromotionControlError("rollback signature receipt does not contain the exact result body")

    def verify(self, *, trusted_public_keys: Iterable[str | bytes]) -> bool:
        return verify_trusted_signed_receipt(
            _thaw(self.signature_receipt), trusted_public_keys=trusted_public_keys,
        )


def sign_canary_result(
    *,
    canary_id: str,
    envelope_id: str,
    aggregate_id: str,
    healthy: bool,
    rollback_ready: bool,
    receipt: EvidenceBinding,
    signing_key: Any,
    authority_epoch_sha256: str,
) -> CanaryResult:
    content = canary_result_evidence_content(
        canary_id=canary_id,
        envelope_id=envelope_id,
        aggregate_id=aggregate_id,
        healthy=healthy,
        rollback_ready=rollback_ready,
        performed_at=receipt.created_at,
    )
    return CanaryResult(
        canary_id=canary_id,
        envelope_id=envelope_id,
        aggregate_id=aggregate_id,
        healthy=healthy,
        rollback_ready=rollback_ready,
        receipt=receipt,
        signature_receipt=sign_receipt(
            name=CANARY_RESULT_RECEIPT,
            payload=content,
            signing_key=signing_key,
            epoch_ruler_sha256=_sha(authority_epoch_sha256, "authority_epoch_sha256"),
        ),
    )


def sign_rollback_result(
    *,
    envelope_id: str,
    reason_code: str,
    rolled_back: bool,
    receipt: EvidenceBinding,
    signing_key: Any,
    authority_epoch_sha256: str,
) -> RollbackResult:
    content = rollback_result_evidence_content(
        envelope_id=envelope_id,
        reason_code=reason_code,
        rolled_back=rolled_back,
        performed_at=receipt.created_at,
    )
    return RollbackResult(
        envelope_id=envelope_id,
        reason_code=reason_code,
        rolled_back=rolled_back,
        receipt=receipt,
        signature_receipt=sign_receipt(
            name=ROLLBACK_RESULT_RECEIPT,
            payload=content,
            signing_key=signing_key,
            epoch_ruler_sha256=_sha(authority_epoch_sha256, "authority_epoch_sha256"),
        ),
    )


class CanaryRunner(Protocol):
    def run(
        self,
        envelope: CandidateEnvelope,
        aggregate: EvaluationAggregate,
    ) -> CanaryResult | Awaitable[CanaryResult]:
        ...


class RollbackExecutor(Protocol):
    def rollback(
        self,
        envelope: CandidateEnvelope,
        *,
        reason_code: str,
    ) -> RollbackResult | Awaitable[RollbackResult]:
        ...


@dataclass(frozen=True)
class PromotionRun:
    aggregate: EvaluationAggregate
    canary: CanaryResult | None
    rollback: RollbackResult | None
    terminal_envelope: CandidateEnvelope
    decision: Mapping[str, Any]
    signed_decision_receipt: Mapping[str, Any]

    @property
    def live_apply_allowed(self) -> bool:
        return self.decision.get("live_apply_allowed") is True


async def _await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value

class PromotionController:
    """Separate promotion authority; live authorization is disabled by default."""

    def __init__(
        self,
        *,
        trusted_source_public_keys: Iterable[str | bytes],
        trusted_evaluator_public_keys: Iterable[str | bytes],
        trusted_canary_public_keys: Iterable[str | bytes],
        trusted_rollback_public_keys: Iterable[str | bytes],
        decision_signing_key: Any,
        decision_authority_epoch_sha256: str,
        canary_runner: CanaryRunner,
        rollback_executor: RollbackExecutor,
        lease_verifier: OperatorLeaseVerifier | None = None,
        live_enabled: bool = False,
        minimum_independent: int = 2,
        terminal_store: CandidateStore | None = None,
    ) -> None:
        self.trusted_source_public_keys = tuple(trusted_source_public_keys)
        self.trusted_evaluator_public_keys = tuple(trusted_evaluator_public_keys)
        self.trusted_canary_public_keys = tuple(trusted_canary_public_keys)
        self.trusted_rollback_public_keys = tuple(trusted_rollback_public_keys)
        self.decision_signing_key = decision_signing_key
        self.decision_authority_epoch_sha256 = _sha(
            decision_authority_epoch_sha256, "decision_authority_epoch_sha256"
        )
        self.canary_runner = canary_runner
        self.rollback_executor = rollback_executor
        self.lease_verifier = lease_verifier
        self.live_enabled = bool(live_enabled)
        self.minimum_independent = max(2, int(minimum_independent))
        self.terminal_store = terminal_store

    async def run(
        self,
        signed_envelope: SignedCandidateEnvelope,
        evaluations: Iterable[SignedIndependentEvaluation],
        *,
        now: str,
        requested_live: bool = False,
        force_rollback: bool = False,
    ) -> PromotionRun:
        envelope = signed_envelope.envelope
        decision_at = _now(now)
        if decision_at < _now(envelope.created_at):
            raise PromotionControlError("decision time precedes candidate creation")
        if (
            envelope.revision != 1
            or envelope.predecessor_envelope_id
            or envelope.terminal_disposition.state is not TerminalState.SUBMITTED
        ):
            raise PromotionControlError(
                "promotion input requires the genesis submitted candidate revision"
            )
        source_signer = _receipt_key(signed_envelope.signature_receipt)
        aggregate = aggregate_independent_evaluations(
            evaluations,
            envelope=envelope,
            trusted_public_keys=self.trusted_evaluator_public_keys,
            excluded_evaluator_ids=(envelope.authority_id,),
            excluded_signer_public_keys=(source_signer,),
            minimum_independent=self.minimum_independent,
            as_of=now,
        )
        blockers = set(aggregate.blockers)
        if not signed_envelope.verify(trusted_public_keys=self.trusted_source_public_keys):
            blockers.add("source_signature_untrusted_or_invalid")
        if envelope.is_expired(now=now):
            blockers.add("candidate_envelope_expired")

        canary: CanaryResult | None = None
        rollback: RollbackResult | None = None
        lease: LeaseVerification | None = None
        lease_consumed = False
        outcome = "refused"
        if not blockers:
            candidate_canary = await _await(self.canary_runner.run(envelope, aggregate))
            if not isinstance(candidate_canary, CanaryResult) or not (
                candidate_canary.verify(trusted_public_keys=self.trusted_canary_public_keys)
                and
                _now(envelope.created_at) <= _now(candidate_canary.receipt.created_at) <= decision_at
                and candidate_canary.envelope_id == envelope.envelope_id
                and candidate_canary.aggregate_id == aggregate.aggregate_id
            ):
                blockers.add("canary_result_invalid")
            else:
                canary = candidate_canary
            if not blockers and canary is not None and (force_rollback or not canary.healthy):
                rollback_reason = "forced_rollback" if force_rollback else "canary_unhealthy"
                candidate_rollback = await _await(
                    self.rollback_executor.rollback(
                        envelope,
                        reason_code=rollback_reason,
                    )
                )
                if not isinstance(candidate_rollback, RollbackResult) or not (
                    candidate_rollback.verify(trusted_public_keys=self.trusted_rollback_public_keys)
                    and
                    _now(envelope.created_at) <= _now(candidate_rollback.receipt.created_at) <= decision_at
                    and candidate_rollback.envelope_id == envelope.envelope_id
                    and candidate_rollback.reason_code == rollback_reason
                ):
                    blockers.add("rollback_result_invalid")
                else:
                    rollback = candidate_rollback
                if rollback is None or not rollback.rolled_back:
                    blockers.add("rollback_failed")
                outcome = "rolled_back" if rollback is not None and rollback.rolled_back else "refused"
            elif not blockers and canary is not None and not canary.rollback_ready:
                blockers.add("rollback_not_ready")
            elif not blockers and canary is not None and requested_live:
                if not self.live_enabled:
                    blockers.add("live_promotion_disabled")
                elif self.lease_verifier is None:
                    blockers.add("operator_lease_verifier_missing")
                else:
                    try:
                        lease = await _await(
                            self.lease_verifier.verify(
                                authority_id=envelope.authority_id,
                                lease_id=envelope.lease_id,
                                candidate_id=envelope.candidate_id,
                                envelope_id=envelope.envelope_id,
                                fence=envelope.fence,
                                lease_expires_at=envelope.lease_expires_at,
                                required_scope="foundry_rsi.live_promotion",
                                now=now,
                            )
                        )
                    except Exception:
                        blockers.add("operator_lease_verification_error")
                        lease = None
                    if lease is None:
                        pass
                    elif not isinstance(lease, LeaseVerification):
                        blockers.add("operator_lease_result_invalid")
                    elif not lease.allowed:
                        blockers.add(f"operator_lease_refused:{lease.reason_code}")
                    elif not lease_result_is_exact(
                        lease,
                        authority_id=envelope.authority_id, lease_id=envelope.lease_id,
                        candidate_id=envelope.candidate_id, envelope_id=envelope.envelope_id,
                        fence=envelope.fence, lease_expires_at=envelope.lease_expires_at,
                        required_scope="foundry_rsi.live_promotion", now=now,
                    ):
                        blockers.add("operator_lease_binding_invalid")
                    elif self.terminal_store is None:
                        blockers.add("durable_lease_consumption_store_missing")
                    else:
                        try:
                            lease_consumed = await self.terminal_store.consume_live_lease_once(
                                authority_id=envelope.authority_id,
                                lease_id=envelope.lease_id,
                                candidate_id=envelope.candidate_id,
                                envelope_id=envelope.envelope_id,
                                fence=envelope.fence,
                                required_scope="foundry_rsi.live_promotion",
                                expires_at=envelope.lease_expires_at,
                                verifier_receipt_sha256=lease.verifier_receipt_sha256,
                                consumed_at=now,
                            )
                        except Exception:
                            blockers.add("durable_lease_consumption_error")
                        if not blockers and not lease_consumed:
                            blockers.add("operator_lease_already_consumed")
                if not blockers:
                    outcome = "live_authorized"
            elif not blockers and canary is not None:
                outcome = "shadow_canary_passed"

        if outcome == "rolled_back":
            state, reason, receipt_id = TerminalState.ROLLED_BACK, "forced_or_unhealthy_canary", rollback.receipt.receipt_id
        elif outcome == "shadow_canary_passed":
            state, reason, receipt_id = TerminalState.CANARY_PASSED, outcome, canary.receipt.receipt_id
        elif outcome == "live_authorized":
            state, reason, receipt_id = TerminalState.CANARY_PASSED, outcome, canary.receipt.receipt_id
        else:
            state, reason = TerminalState.REFUSED, sorted(blockers)[0] if blockers else "promotion_refused"
            receipt_id = canary.receipt.receipt_id if canary else envelope.terminal_disposition.receipt_id
        disposition_at = envelope.expires_at if envelope.is_expired(now=now) else now
        disposition = TerminalDisposition(state=state, reason_code=reason, receipt_id=receipt_id, at=disposition_at)
        terminal = envelope.derive_terminal(disposition)
        decision = {
            "schema": PROMOTION_DECISION_SCHEMA,
            "input_envelope_id": envelope.envelope_id,
            "terminal_envelope_id": terminal.envelope_id,
            "candidate_id": envelope.candidate_id,
            "aggregate_id": aggregate.aggregate_id,
            "canary_receipt_sha256": canary.receipt.sha256 if canary else "",
            "rollback_receipt_sha256": rollback.receipt.sha256 if rollback else "",
            "canary_result_content_verified": canary is not None,
            "rollback_result_content_verified": rollback is not None,
            "canary_binding": (
                {"canary_id": canary.canary_id, "envelope_id": canary.envelope_id,
                 "aggregate_id": canary.aggregate_id} if canary else None
            ),
            "rollback_binding": (
                {"envelope_id": rollback.envelope_id, "reason_code": rollback.reason_code}
                if rollback else None
            ),
            "evidence_binding_only": False,
            "typed_canary_result_signature_verified": canary is not None,
            "typed_rollback_result_signature_verified": rollback is not None,
            "independent_evidence_bodies_verified_by_controller": False,
            "lease_verification": lease.to_dict() if lease else None,
            "operator_lease_consumed": lease_consumed,
            "requested_live": bool(requested_live),
            "live_controller_enabled": self.live_enabled,
            "live_apply_allowed": outcome == "live_authorized" and not blockers,
            "outcome": outcome,
            "blockers": sorted(blockers),
            "decided_at": now,
        }
        decision["decision_id"] = canonical_sha256(decision)
        signed_decision = sign_receipt(
            name=PROMOTION_DECISION_RECEIPT,
            payload=decision,
            signing_key=self.decision_signing_key,
            epoch_ruler_sha256=self.decision_authority_epoch_sha256,
        )
        if self.terminal_store is not None:
            await self.terminal_store.append_terminal_disposition(
                candidate_id=envelope.candidate_id,
                envelope_id=terminal.envelope_id,
                disposition=disposition,
                attempt=terminal.attempt,
                fence=terminal.fence,
                promotion_decision_sha256=decision["decision_id"],
                allow_external_candidate=True,
            )
        return PromotionRun(
            aggregate=aggregate,
            canary=canary,
            rollback=rollback,
            terminal_envelope=terminal,
            decision=decision,
            signed_decision_receipt=signed_decision,
        )


def verify_signed_promotion_decision(
    run: PromotionRun,
    *,
    trusted_public_keys: Iterable[str | bytes],
) -> bool:
    receipt = dict(run.signed_decision_receipt)
    return bool(
        receipt.get("name") == PROMOTION_DECISION_RECEIPT
        and receipt.get("payload") == dict(run.decision)
        and verify_trusted_signed_receipt(receipt, trusted_public_keys=trusted_public_keys)
    )


__all__ = [
    "CANARY_RESULT_EVIDENCE_SCHEMA", "ROLLBACK_RESULT_EVIDENCE_SCHEMA",
    "CANARY_RESULT_RECEIPT", "ROLLBACK_RESULT_RECEIPT",
    "CanaryResult", "EvaluationAggregate", "IndependentEvaluation", "LeaseVerification",
    "OperatorLeaseVerifier", "PromotionController", "PromotionControlError", "PromotionRun",
    "RollbackResult", "SignedIndependentEvaluation", "aggregate_independent_evaluations",
    "canary_result_evidence_content", "rollback_result_evidence_content",
    "sign_canary_result", "sign_independent_evaluation", "sign_rollback_result",
    "verify_signed_promotion_decision",
]
