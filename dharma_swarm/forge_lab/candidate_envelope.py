"""Immutable RSI -> Foundry candidate envelope and signature binding.

The candidate payload is content addressed independently of its signature.  A
signature is an existing Forge signed-receipt primitive whose payload contains
the complete addressed envelope, so neither the signer nor a transport can
silently rewrite provenance, evidence, lease, expiry, or disposition fields.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    sign_receipt,
    verify_trusted_signed_receipt,
)

CANDIDATE_ENVELOPE_SCHEMA = "forge_lab.rsi_foundry_candidate.v1"
SIGNED_CANDIDATE_ENVELOPE_SCHEMA = "forge_lab.signed_rsi_foundry_candidate.v1"
CANDIDATE_SIGNATURE_RECEIPT = "rsi_foundry_candidate_envelope"
MAX_CANDIDATE_LIFETIME_SECONDS = 24 * 60 * 60

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class CandidateEnvelopeError(ValueError):
    """Raised when an envelope is incomplete, mutable-by-alias, or rewritten."""


def _token(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 512 or any(ord(ch) < 32 for ch in text):
        raise CandidateEnvelopeError(f"{field} must be a non-empty printable token")
    return text


def _sha256(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA256.fullmatch(text):
        raise CandidateEnvelopeError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _git_sha(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _GIT_SHA.fullmatch(text):
        raise CandidateEnvelopeError(f"{field} must be a full SHA-1 or SHA-256 Git object id")
    return text


def _utc(value: Any, field: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CandidateEnvelopeError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CandidateEnvelopeError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise CandidateEnvelopeError(f"signature receipt contains non-JSON value: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class EvidenceBinding:
    """A digest-bound external receipt; receipt contents stay in their owner."""

    schema: str
    receipt_id: str
    sha256: str
    issuer: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema", _token(self.schema, "evidence.schema"))
        object.__setattr__(self, "receipt_id", _token(self.receipt_id, "evidence.receipt_id"))
        object.__setattr__(self, "sha256", _sha256(self.sha256, "evidence.sha256"))
        object.__setattr__(self, "issuer", _token(self.issuer, "evidence.issuer"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "evidence.created_at"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceBinding":
        if set(payload) != set(cls.__dataclass_fields__):
            raise CandidateEnvelopeError("evidence binding fields are invalid")
        return cls(**{name: payload.get(name) for name in cls.__dataclass_fields__})


class TerminalState(StrEnum):
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"
    REFUSED = "refused"
    EXPIRED = "expired"
    DEAD_LETTERED = "dead_lettered"
    CANARY_PASSED = "canary_passed"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"

    @property
    def final(self) -> bool:
        return self is not TerminalState.SUBMITTED


@dataclass(frozen=True)
class TerminalDisposition:
    state: TerminalState
    reason_code: str
    receipt_id: str
    at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", TerminalState(self.state))
        object.__setattr__(self, "reason_code", _token(self.reason_code, "terminal.reason_code"))
        object.__setattr__(self, "receipt_id", _token(self.receipt_id, "terminal.receipt_id"))
        object.__setattr__(self, "at", _utc(self.at, "terminal.at"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "reason_code": self.reason_code,
            "receipt_id": self.receipt_id,
            "at": self.at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TerminalDisposition":
        if set(payload) != {"state", "reason_code", "receipt_id", "at"}:
            raise CandidateEnvelopeError("terminal disposition fields are invalid")
        return cls(
            state=TerminalState(str(payload.get("state") or "")),
            reason_code=str(payload.get("reason_code") or ""),
            receipt_id=str(payload.get("receipt_id") or ""),
            at=str(payload.get("at") or ""),
        )


@dataclass(frozen=True)
class CandidateEnvelope:
    """One immutable, versioned statement about an RSI shadow candidate."""

    candidate_id: str
    revision: int
    predecessor_envelope_id: str
    correlation_id: str
    idempotency_key: str
    source_run_id: str
    source_task_id: str
    source_sha: str
    controller_sha: str
    harness_sha: str
    evaluator_sha: str
    target_sha: str
    base_sha: str
    patch_sha256: str
    dependencies_sha256: str
    toolchain_sha256: str
    artifact_sha256: str
    configuration_sha256: str
    provider_attestation: EvidenceBinding
    budget_receipt: EvidenceBinding
    evaluation_receipt: EvidenceBinding
    provenance_receipt: EvidenceBinding
    task_identity: str
    holdout_identity: str
    parent_lineage: tuple[str, ...]
    evaluation_outcome: str
    evaluation_comparable: bool
    authority_id: str
    lease_id: str
    lease_expires_at: str
    created_at: str
    expires_at: str
    attempt: int
    fence: int
    terminal_disposition: TerminalDisposition
    schema: str = CANDIDATE_ENVELOPE_SCHEMA

    def __post_init__(self) -> None:
        token_fields = (
            "candidate_id", "correlation_id", "idempotency_key", "source_run_id",
            "source_task_id", "task_identity", "holdout_identity", "evaluation_outcome",
            "authority_id", "lease_id",
        )
        for field in token_fields:
            object.__setattr__(self, field, _token(getattr(self, field), field))
        object.__setattr__(self, "schema", _token(self.schema, "schema"))
        if self.schema != CANDIDATE_ENVELOPE_SCHEMA:
            raise CandidateEnvelopeError(f"unsupported candidate envelope schema: {self.schema}")
        if not isinstance(self.revision, int) or isinstance(self.revision, bool) or self.revision < 1:
            raise CandidateEnvelopeError("revision must be a positive integer")
        predecessor = str(self.predecessor_envelope_id or "").strip().lower()
        if self.revision == 1 and predecessor:
            raise CandidateEnvelopeError("revision 1 cannot have a predecessor")
        if self.revision > 1:
            predecessor = _sha256(predecessor, "predecessor_envelope_id")
        object.__setattr__(self, "predecessor_envelope_id", predecessor)
        if self.revision == 1 and self.terminal_disposition.state is not TerminalState.SUBMITTED:
            raise CandidateEnvelopeError("revision 1 must have submitted disposition")
        if self.revision > 1 and not self.terminal_disposition.state.final:
            raise CandidateEnvelopeError("derived revisions require a final disposition")
        for field in (
            "source_sha", "controller_sha", "harness_sha", "evaluator_sha",
            "target_sha", "base_sha",
        ):
            object.__setattr__(self, field, _git_sha(getattr(self, field), field))
        for field in (
            "patch_sha256", "dependencies_sha256", "toolchain_sha256",
            "artifact_sha256", "configuration_sha256",
        ):
            object.__setattr__(self, field, _sha256(getattr(self, field), field))
        lineage = tuple(_token(item, "parent_lineage") for item in self.parent_lineage)
        if len(set(lineage)) != len(lineage):
            raise CandidateEnvelopeError("parent_lineage must not contain duplicates")
        object.__setattr__(self, "parent_lineage", lineage)
        if not isinstance(self.evaluation_comparable, bool):
            raise CandidateEnvelopeError("evaluation_comparable must be boolean")
        for field in ("attempt", "fence"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise CandidateEnvelopeError(f"{field} must be a positive integer")
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "expires_at", _utc(self.expires_at, "expires_at"))
        object.__setattr__(self, "lease_expires_at", _utc(self.lease_expires_at, "lease_expires_at"))
        created = _instant(self.created_at)
        expires = _instant(self.expires_at)
        lease_expires = _instant(self.lease_expires_at)
        terminal_at = _instant(self.terminal_disposition.at)
        for field in (
            "provider_attestation", "budget_receipt", "evaluation_receipt", "provenance_receipt",
        ):
            if _instant(getattr(self, field).created_at) > created:
                raise CandidateEnvelopeError(f"{field} cannot postdate candidate creation")
        if expires <= created:
            raise CandidateEnvelopeError("expires_at must be later than created_at")
        if lease_expires <= created:
            raise CandidateEnvelopeError("lease_expires_at must be later than created_at")
        if expires > lease_expires:
            raise CandidateEnvelopeError("candidate envelope cannot outlive its producer lease")
        if (expires - created).total_seconds() > MAX_CANDIDATE_LIFETIME_SECONDS:
            raise CandidateEnvelopeError("candidate envelope lifetime exceeds the 24-hour bound")
        if (lease_expires - created).total_seconds() > MAX_CANDIDATE_LIFETIME_SECONDS:
            raise CandidateEnvelopeError("producer lease lifetime exceeds the 24-hour bound")
        if terminal_at < created or terminal_at > expires:
            raise CandidateEnvelopeError("terminal disposition must fall within envelope lifetime")

    @property
    def envelope_id(self) -> str:
        return canonical_sha256(self.content_dict())

    def content_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "candidate_id": self.candidate_id,
            "revision": self.revision,
            "predecessor_envelope_id": self.predecessor_envelope_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "source_run_id": self.source_run_id,
            "source_task_id": self.source_task_id,
            "source_sha": self.source_sha,
            "controller_sha": self.controller_sha,
            "harness_sha": self.harness_sha,
            "evaluator_sha": self.evaluator_sha,
            "target_sha": self.target_sha,
            "base_sha": self.base_sha,
            "digests": {
                "patch": self.patch_sha256,
                "dependencies": self.dependencies_sha256,
                "toolchain": self.toolchain_sha256,
                "artifact": self.artifact_sha256,
                "configuration": self.configuration_sha256,
            },
            "evidence": {
                "provider_attestation": self.provider_attestation.to_dict(),
                "budget_receipt": self.budget_receipt.to_dict(),
                "evaluation_receipt": self.evaluation_receipt.to_dict(),
                "provenance_receipt": self.provenance_receipt.to_dict(),
            },
            "task_identity": self.task_identity,
            "holdout_identity": self.holdout_identity,
            "parent_lineage": list(self.parent_lineage),
            "evaluation_outcome": self.evaluation_outcome,
            "evaluation_comparable": self.evaluation_comparable,
            "authority": {
                "authority_id": self.authority_id,
                "lease_id": self.lease_id,
                "lease_expires_at": self.lease_expires_at,
            },
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "attempt": self.attempt,
            "fence": self.fence,
            "terminal_disposition": self.terminal_disposition.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.content_dict(), "envelope_id": self.envelope_id}

    def is_expired(self, *, now: str) -> bool:
        return _instant(_utc(now, "now")) >= _instant(self.expires_at)

    def derive_terminal(
        self,
        disposition: TerminalDisposition,
        *,
        evaluation_receipt: EvidenceBinding | None = None,
        evaluation_outcome: str | None = None,
        evaluation_comparable: bool | None = None,
        evaluator_sha: str | None = None,
    ) -> "CandidateEnvelope":
        """Create the next immutable revision; the current object is untouched."""

        return replace(
            self,
            revision=self.revision + 1,
            predecessor_envelope_id=self.envelope_id,
            evaluation_receipt=evaluation_receipt or self.evaluation_receipt,
            evaluation_outcome=evaluation_outcome or self.evaluation_outcome,
            evaluation_comparable=(
                self.evaluation_comparable
                if evaluation_comparable is None
                else evaluation_comparable
            ),
            evaluator_sha=evaluator_sha or self.evaluator_sha,
            terminal_disposition=disposition,
        )

    @classmethod
    def from_content_dict(cls, payload: Mapping[str, Any]) -> "CandidateEnvelope":
        expected = {
            "schema", "candidate_id", "revision", "predecessor_envelope_id",
            "correlation_id", "idempotency_key", "source_run_id", "source_task_id",
            "source_sha", "controller_sha", "harness_sha", "evaluator_sha",
            "target_sha", "base_sha", "digests", "evidence", "task_identity",
            "holdout_identity", "parent_lineage", "evaluation_outcome",
            "evaluation_comparable", "authority", "created_at", "expires_at",
            "attempt", "fence", "terminal_disposition",
        }
        if set(payload) != expected:
            raise CandidateEnvelopeError("candidate envelope fields are invalid")
        digests = dict(payload.get("digests") or {})
        evidence = dict(payload.get("evidence") or {})
        authority = dict(payload.get("authority") or {})
        if set(digests) != {"patch", "dependencies", "toolchain", "artifact", "configuration"}:
            raise CandidateEnvelopeError("candidate digest fields are invalid")
        if set(evidence) != {
            "provider_attestation", "budget_receipt", "evaluation_receipt", "provenance_receipt",
        }:
            raise CandidateEnvelopeError("candidate evidence fields are invalid")
        if set(authority) != {"authority_id", "lease_id", "lease_expires_at"}:
            raise CandidateEnvelopeError("candidate authority fields are invalid")
        return cls(
            candidate_id=payload.get("candidate_id"),
            revision=payload.get("revision"),
            predecessor_envelope_id=payload.get("predecessor_envelope_id"),
            correlation_id=payload.get("correlation_id"),
            idempotency_key=payload.get("idempotency_key"),
            source_run_id=payload.get("source_run_id"),
            source_task_id=payload.get("source_task_id"),
            source_sha=payload.get("source_sha"),
            controller_sha=payload.get("controller_sha"),
            harness_sha=payload.get("harness_sha"),
            evaluator_sha=payload.get("evaluator_sha"),
            target_sha=payload.get("target_sha"),
            base_sha=payload.get("base_sha"),
            patch_sha256=digests.get("patch"),
            dependencies_sha256=digests.get("dependencies"),
            toolchain_sha256=digests.get("toolchain"),
            artifact_sha256=digests.get("artifact"),
            configuration_sha256=digests.get("configuration"),
            provider_attestation=EvidenceBinding.from_dict(evidence.get("provider_attestation") or {}),
            budget_receipt=EvidenceBinding.from_dict(evidence.get("budget_receipt") or {}),
            evaluation_receipt=EvidenceBinding.from_dict(evidence.get("evaluation_receipt") or {}),
            provenance_receipt=EvidenceBinding.from_dict(evidence.get("provenance_receipt") or {}),
            task_identity=payload.get("task_identity"),
            holdout_identity=payload.get("holdout_identity"),
            parent_lineage=tuple(payload.get("parent_lineage") or ()),
            evaluation_outcome=payload.get("evaluation_outcome"),
            evaluation_comparable=payload.get("evaluation_comparable"),
            authority_id=authority.get("authority_id"),
            lease_id=authority.get("lease_id"),
            lease_expires_at=authority.get("lease_expires_at"),
            created_at=payload.get("created_at"),
            expires_at=payload.get("expires_at"),
            attempt=payload.get("attempt"),
            fence=payload.get("fence"),
            terminal_disposition=TerminalDisposition.from_dict(payload.get("terminal_disposition") or {}),
            schema=payload.get("schema") or "",
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateEnvelope":
        if "envelope_id" not in payload:
            raise CandidateEnvelopeError("candidate envelope_id is missing")
        candidate = cls.from_content_dict(
            {key: value for key, value in payload.items() if key != "envelope_id"}
        )
        supplied_id = str(payload.get("envelope_id") or "").lower()
        if supplied_id != candidate.envelope_id:
            raise CandidateEnvelopeError("candidate envelope content hash mismatch")
        return candidate


@dataclass(frozen=True)
class SignedCandidateEnvelope:
    envelope: CandidateEnvelope
    signature_receipt: Mapping[str, Any]
    schema: str = SIGNED_CANDIDATE_ENVELOPE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SIGNED_CANDIDATE_ENVELOPE_SCHEMA:
            raise CandidateEnvelopeError(f"unsupported signed envelope schema: {self.schema}")
        object.__setattr__(self, "signature_receipt", _freeze_json(self.signature_receipt))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "envelope": self.envelope.to_dict(),
            "signature_receipt": _thaw_json(self.signature_receipt),
        }

    def verify(self, *, trusted_public_keys: Iterable[str | bytes]) -> bool:
        receipt = _thaw_json(self.signature_receipt)
        payload = receipt.get("payload")
        return bool(
            self.schema == SIGNED_CANDIDATE_ENVELOPE_SCHEMA
            and receipt.get("name") == CANDIDATE_SIGNATURE_RECEIPT
            and isinstance(payload, dict)
            and payload == self.envelope.to_dict()
            and verify_trusted_signed_receipt(
                receipt,
                trusted_public_keys=trusted_public_keys,
            )
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SignedCandidateEnvelope":
        if set(payload) != {"schema", "envelope", "signature_receipt"}:
            raise CandidateEnvelopeError("signed candidate envelope fields are invalid")
        schema = str(payload.get("schema") or "")
        if schema != SIGNED_CANDIDATE_ENVELOPE_SCHEMA:
            raise CandidateEnvelopeError(f"unsupported signed envelope schema: {schema}")
        receipt = payload.get("signature_receipt")
        if not isinstance(receipt, dict):
            raise CandidateEnvelopeError("signed envelope requires a signature receipt")
        return cls(
            envelope=CandidateEnvelope.from_dict(payload.get("envelope") or {}),
            signature_receipt=dict(receipt),
        )


def sign_candidate_envelope(
    envelope: CandidateEnvelope,
    *,
    signing_key: Any,
    authority_epoch_sha256: str,
    key_id: str = "",
) -> SignedCandidateEnvelope:
    receipt = sign_receipt(
        name=CANDIDATE_SIGNATURE_RECEIPT,
        payload=envelope.to_dict(),
        signing_key=signing_key,
        epoch_ruler_sha256=_sha256(authority_epoch_sha256, "authority_epoch_sha256"),
        key_id=key_id,
    )
    return SignedCandidateEnvelope(envelope=envelope, signature_receipt=receipt)


__all__ = [
    "CANDIDATE_ENVELOPE_SCHEMA",
    "SIGNED_CANDIDATE_ENVELOPE_SCHEMA",
    "CandidateEnvelope",
    "CandidateEnvelopeError",
    "EvidenceBinding",
    "MAX_CANDIDATE_LIFETIME_SECONDS",
    "SignedCandidateEnvelope",
    "TerminalDisposition",
    "TerminalState",
    "sign_candidate_envelope",
]
