"""Typed evidence for fenced campaign renewal and independent acceptance."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

from dharma_swarm.mission_control_contract import (
    MissionControlError,
    clean_identifier,
    stable_id,
)
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.spine.identity import ExecutionIdentity

EVIDENCE_DELTA_RECEIPT_TYPE = "mission_evidence_delta"
ACCEPTANCE_RECEIPT_TYPE = "mission_independent_acceptance"
VERIFIER_RESULT_RECEIPT_TYPE = "mission_verifier_result"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")


def _exact(value: str, label: str) -> str:
    cleaned = clean_identifier(value, label)
    if cleaned != value:
        raise MissionControlError(f"{label} must be canonical")
    return cleaned


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise MissionControlError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _refs(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise MissionControlError(f"{label} must be a tuple")
    checked = tuple(_exact(value, f"{label} item") for value in values)
    if len(set(checked)) != len(checked):
        raise MissionControlError(f"{label} contains a duplicate")
    return checked


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _delta_content_digest(
    *,
    observed_at: Any,
    summary: Any,
    artifact_ids: Any,
    receipt_ids: Any,
) -> str:
    return _digest(
        {
            "observed_at": (
                observed_at.isoformat()
                if isinstance(observed_at, datetime)
                else observed_at
            ),
            "summary": summary,
            "artifact_ids": artifact_ids,
            "receipt_ids": receipt_ids,
        }
    )


@dataclass(frozen=True, slots=True)
class EvidenceDelta:
    """New durable work evidence tied to one exact claim generation."""

    delta_id: str
    mission_id: str
    task_id: str
    run_id: str
    claim_id: str
    agent_id: str
    sequence: int
    observed_at: datetime
    summary: str
    artifact_ids: tuple[str, ...] = ()
    receipt_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label in (
            "delta_id",
            "mission_id",
            "task_id",
            "run_id",
            "claim_id",
            "agent_id",
        ):
            _exact(getattr(self, label), label)
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 1
        ):
            raise MissionControlError("sequence must be a positive integer")
        _aware(self.observed_at, "observed_at")
        if not self.summary or self.summary != self.summary.strip():
            raise MissionControlError("summary must be canonical nonempty text")
        artifacts = _refs(self.artifact_ids, "artifact_ids")
        receipts = _refs(self.receipt_ids, "receipt_ids")
        if not artifacts and not receipts:
            raise MissionControlError("evidence delta must cite durable evidence")
        expected = stable_id(
            "evidence_delta",
            self.mission_id,
            self.task_id,
            self.run_id,
            self.claim_id,
            self.agent_id,
            str(self.sequence),
            _delta_content_digest(
                observed_at=self.observed_at,
                summary=self.summary,
                artifact_ids=self.artifact_ids,
                receipt_ids=self.receipt_ids,
            ),
        )
        if self.delta_id != expected:
            raise MissionControlError("delta_id does not bind the evidence identity")

    @classmethod
    def new(
        cls,
        *,
        mission_id: str,
        task_id: str,
        run_id: str,
        claim_id: str,
        agent_id: str,
        sequence: int,
        observed_at: datetime,
        summary: str,
        artifact_ids: tuple[str, ...] = (),
        receipt_ids: tuple[str, ...] = (),
    ) -> EvidenceDelta:
        delta_id = stable_id(
            "evidence_delta",
            mission_id,
            task_id,
            run_id,
            claim_id,
            agent_id,
            str(sequence),
            _delta_content_digest(
                observed_at=observed_at,
                summary=summary,
                artifact_ids=artifact_ids,
                receipt_ids=receipt_ids,
            ),
        )
        return cls(
            delta_id,
            mission_id,
            task_id,
            run_id,
            claim_id,
            agent_id,
            sequence,
            observed_at,
            summary,
            artifact_ids,
            receipt_ids,
        )

    def require_fresh(
        self,
        *,
        now: datetime,
        last_sequence: int,
        max_age: timedelta,
    ) -> None:
        now = _aware(now, "now")
        if max_age <= timedelta(0):
            raise ValueError("max_age must be positive")
        observed = _aware(self.observed_at, "observed_at")
        if observed > now + timedelta(seconds=5):
            raise MissionControlError("evidence delta is future-dated")
        if observed < now - max_age:
            raise MissionControlError("evidence delta is stale")
        if self.sequence <= last_sequence:
            raise MissionControlError("evidence sequence is duplicate or stale")

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["artifact_ids"] = list(self.artifact_ids)
        payload["receipt_ids"] = list(self.receipt_ids)
        payload["evidence_digest"] = _digest(payload)
        return payload


@dataclass(frozen=True, slots=True)
class IndependentAcceptance:
    """A verifier verdict that cannot be synthesized by producer completion."""

    acceptance_id: str
    mission_id: str
    task_id: str
    producer_run_id: str
    producer_agent_id: str
    producer_model_family: str
    producer_output_digest: str
    verifier_run_id: str
    verifier_agent_id: str
    verifier_model_family: str
    oracle_kind: Literal["model", "deterministic_held_out"]
    accepted: bool
    observed_at: datetime
    rationale: str
    evidence_receipt_ids: tuple[str, ...] = ()
    evidence_artifact_ids: tuple[str, ...] = ()
    oracle_digest: str = ""

    def __post_init__(self) -> None:
        for label in (
            "acceptance_id",
            "mission_id",
            "task_id",
            "producer_run_id",
            "producer_agent_id",
            "verifier_run_id",
            "verifier_agent_id",
        ):
            _exact(getattr(self, label), label)
        if type(self.accepted) is not bool:
            raise MissionControlError("accepted must be a boolean")
        if not _SHA256_RE.fullmatch(self.producer_output_digest):
            raise MissionControlError("producer_output_digest must be sha256")
        _aware(self.observed_at, "observed_at")
        if not self.rationale or self.rationale != self.rationale.strip():
            raise MissionControlError("acceptance rationale is required")
        receipts = _refs(self.evidence_receipt_ids, "evidence_receipt_ids")
        artifacts = _refs(self.evidence_artifact_ids, "evidence_artifact_ids")
        if not receipts and not artifacts:
            raise MissionControlError("acceptance must cite verifier evidence")
        if self.oracle_kind not in {"model", "deterministic_held_out"}:
            raise MissionControlError("oracle_kind is invalid")
        same_agent = self.producer_agent_id == self.verifier_agent_id
        same_family = bool(
            self.producer_model_family
            and self.producer_model_family == self.verifier_model_family
        )
        if self.oracle_kind == "model":
            if not self.producer_model_family or not self.verifier_model_family:
                raise MissionControlError("model acceptance requires both model families")
            _exact(self.producer_model_family, "producer_model_family")
            _exact(self.verifier_model_family, "verifier_model_family")
            if same_agent or same_family:
                raise MissionControlError("generator and verifier must be independent")
        elif not _SHA256_RE.fullmatch(self.oracle_digest):
            raise MissionControlError("held-out oracle requires a sha256 oracle_digest")
        expected = stable_id(
            "independent_acceptance",
            self.mission_id,
            self.task_id,
            self.producer_run_id,
            self.producer_agent_id,
            self.producer_model_family,
            self.producer_output_digest,
            self.verifier_run_id,
            self.verifier_agent_id,
            self.verifier_model_family,
            self.oracle_kind,
            self.oracle_digest,
            str(self.accepted).lower(),
        )
        if self.acceptance_id != expected:
            raise MissionControlError("acceptance_id does not bind the verdict")

    @classmethod
    def new(cls, **values: Any) -> IndependentAcceptance:
        acceptance_id = stable_id(
            "independent_acceptance",
            values["mission_id"],
            values["task_id"],
            values["producer_run_id"],
            values["producer_agent_id"],
            values["producer_model_family"],
            values["producer_output_digest"],
            values["verifier_run_id"],
            values["verifier_agent_id"],
            values["verifier_model_family"],
            values["oracle_kind"],
            values.get("oracle_digest", ""),
            str(values["accepted"]).lower(),
        )
        return cls(acceptance_id=acceptance_id, **values)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["evidence_receipt_ids"] = list(self.evidence_receipt_ids)
        payload["evidence_artifact_ids"] = list(self.evidence_artifact_ids)
        payload["acceptance_digest"] = _digest(payload)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> IndependentAcceptance:
        try:
            row = dict(payload)
            supplied = str(row.pop("acceptance_digest", ""))
            if supplied != _digest(row):
                raise MissionControlError("acceptance payload digest is invalid")
            row["observed_at"] = datetime.fromisoformat(str(row["observed_at"]))
            row["evidence_receipt_ids"] = tuple(
                row.get("evidence_receipt_ids") or ()
            )
            row["evidence_artifact_ids"] = tuple(
                row.get("evidence_artifact_ids") or ()
            )
            return cls(**row)
        except MissionControlError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise MissionControlError("acceptance payload is malformed") from exc


def candidate_output_digest(result: str) -> str:
    if not isinstance(result, str):
        raise MissionControlError("candidate output must be text")
    return "sha256:" + hashlib.sha256(result.encode("utf-8")).hexdigest()


def json_value(value: Any) -> Any:
    if is_dataclass(value):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def has_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(isinstance(payload.get(key), str) and payload[key].strip() for key in keys)


def first_text(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def canonical_served_models(
    receipts: list[RuntimeReceipt],
    *,
    identity: ExecutionIdentity,
) -> set[str]:
    """Extract provider-attested model names from exact owner receipt carriers."""
    models: set[str] = set()
    for receipt in receipts:
        if (
            receipt.receipt_type != "side_effect_complete"
            or receipt.status != "completed"
            or (
                receipt.run_id,
                receipt.task_id,
                receipt.trace_id,
                receipt.correlation_id,
                receipt.causation_id,
                receipt.parent_run_id,
                receipt.agent_id,
            )
            != (
                identity.run_id,
                identity.task_id,
                identity.trace_id,
                identity.correlation_id,
                identity.causation_id,
                identity.parent_run_id,
                identity.agent_id,
            )
        ):
            continue
        nested = receipt.payload.get("receipt")
        if not isinstance(nested, dict) or nested.get("status") != "ok":
            continue
        attributes = nested.get("attributes")
        if not isinstance(attributes, dict):
            continue
        if (
            nested.get("trace_id") != identity.trace_id
            or nested.get("task_id") != identity.task_id
            or nested.get("agent_id") != identity.agent_id
            or nested.get("claim_id") != identity.claim_id
            or attributes.get("run_id") != identity.run_id
            or attributes.get("dispatch_idempotency_key")
            != identity.idempotency_key
            or attributes.get("provider_truth_source") != "llm_response"
        ):
            continue
        provider = first_text(attributes, ("served_provider", "actual_provider"))
        model = first_text(attributes, ("served_model", "actual_model"))
        if provider and model:
            models.add(model)
    return models


__all__ = [
    "ACCEPTANCE_RECEIPT_TYPE",
    "EVIDENCE_DELTA_RECEIPT_TYPE",
    "EvidenceDelta",
    "IndependentAcceptance",
    "VERIFIER_RESULT_RECEIPT_TYPE",
    "canonical_served_models",
    "candidate_output_digest",
    "first_text",
    "has_text",
    "json_value",
]
