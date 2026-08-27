"""Read-only A2A-to-Mission-Control projection and in-process gate."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Mapping

from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
    MissionControlError,
    session_id as mission_session_id,
)
from dharma_swarm.mission_control_verification import ExpectedPromotionBindings
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.spine.identity import ExecutionIdentity

if TYPE_CHECKING:
    from dharma_swarm.mission_control_a2a_evaluator import A2APatchPromotionEvaluator
    from dharma_swarm.mission_control_a2a_projection import MissionControlA2AProjection

A2A_BINDING_SCHEMA = "dharma.mission_control.a2a_binding.v1"
A2A_PROJECTION_SCHEMA = "dharma.mission_control.a2a_projection.v1"
PATCH_CANDIDATE_SCHEMA = "dharma.a2a.patch_candidate.v1"
_SCAN_LIMIT = 10_000
_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FOUNDRY_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_DELIVERY_ID = re.compile(r"^[0-9a-f]{24}$")
_OBSERVATION_SEAL = object()


class A2AEvidencePhase(str, Enum):
    """Derived evidence phase; deliberately not a TaskStatus."""

    DELIVERED = "delivered"
    EXECUTED = "executed"
    VERIFYING = "verifying"


@dataclass(frozen=True, slots=True)
class A2ANativeExecutionRef:
    mission_id: str
    task_id: str
    agent_uid: str
    packet_id: str
    correlation_id: str
    delivery_id: str
    proposal_id: str
    content_sha256: str

    @property
    def attempt_id(self) -> str:
        return self.packet_id

    @property
    def lease_id(self) -> str:
        return self.delivery_id


@dataclass(frozen=True, slots=True)
class A2AExecutionObservation:
    """Nominal observation minted only by a successful exact read."""

    native_ref: A2ANativeExecutionRef
    phase: A2AEvidencePhase
    task_status: TaskStatus
    envelope_sha256: str
    artifact_sha256: str = ""
    semantic_job_status: str = ""
    responder_status: str = ""
    proposal_receipt_id: str = ""
    proposal_receipt_sha256: str = ""
    candidate_digest: str = ""
    diff_sha256: str = ""
    base_sha: str = ""
    authorized_source_files: tuple[str, ...] = ()
    executor_run_id: str = ""
    proves_executor_liveness: bool = False
    canonical_task_terminal: bool = False
    _seal: object | None = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def _mint(cls, **values: Any) -> A2AExecutionObservation:
        observation = cls(**values)
        object.__setattr__(observation, "_seal", _OBSERVATION_SEAL)
        return observation

    def __bool__(self) -> bool:
        return self._seal is _OBSERVATION_SEAL

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("_seal", None)
        payload["phase"] = self.phase.value
        payload["task_status"] = self.task_status.value
        return payload


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _safe_token(value: str, label: str) -> str:
    if not value or len(value) > 96 or not _TOKEN.fullmatch(value):
        raise MissionControlError(f"invalid A2A {label}")
    return value


def _delivery_id(
    path: Path,
    delivery: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> str:
    stable = {
        "path": str(path),
        "packet_id": str(envelope.get("packet_id") or ""),
        "reply_subject": str(envelope.get("reply_subject") or ""),
        "envelope_sha256": str(delivery.get("envelope_sha256") or ""),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()[:24]


def _receipt_digest(receipt: RuntimeReceipt) -> str:
    names = (
        "receipt_id",
        "receipt_type",
        "status",
        "run_id",
        "task_id",
        "trace_id",
        "correlation_id",
        "causation_id",
        "parent_run_id",
        "agent_id",
        "idempotency_key",
        "side_effect_key",
        "payload",
    )
    return _canonical_digest({name: getattr(receipt, name) for name in names})


def _require_binding(task: Task, mission_id: str) -> A2ANativeExecutionRef:
    if (
        task.metadata.get("mission_id") != mission_id
        or task.metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
    ):
        raise MissionControlError(
            f"task {task.id!r} is not owned by mission {mission_id!r}",
        )
    binding = task.metadata.get("a2a_binding")
    if (
        not isinstance(binding, dict)
        or binding.get("schema_version") != A2A_BINDING_SCHEMA
    ):
        raise MissionControlError("task is missing the typed A2A binding")
    agent = str(binding.get("agent_uid") or "")
    packet = str(binding.get("packet_id") or "")
    correlation = str(binding.get("correlation_id") or "")
    delivery = str(binding.get("delivery_id") or "")
    proposal = str(binding.get("proposal_id") or "")
    content = str(binding.get("content_sha256") or "")
    _safe_token(agent, "agent_uid")
    _safe_token(packet, "packet_id")
    _safe_token(proposal, "proposal_id")
    if correlation != f"a2a_send:{agent}:{packet}":
        raise MissionControlError("A2A correlation does not bind the target and packet")
    if not _DELIVERY_ID.fullmatch(delivery) or not _SHA256.fullmatch(content):
        raise MissionControlError("A2A binding is incomplete")
    return A2ANativeExecutionRef(
        mission_id=mission_id,
        task_id=task.id,
        agent_uid=agent,
        packet_id=packet,
        correlation_id=correlation,
        delivery_id=delivery,
        proposal_id=proposal,
        content_sha256=content,
    )


def _require_expected_ref(
    expected: ExpectedPromotionBindings,
    ref: A2ANativeExecutionRef,
    *,
    artifact_sha256: str | None,
) -> None:
    strings = (
        expected.mission_id,
        expected.task_id,
        expected.attempt_id,
        expected.packet_id,
        expected.proposal_id,
        expected.executor_agent_uid,
        expected.executor_run_id,
        expected.foundry_verifier.agent_uid,
        expected.foundry_verifier.run_id,
        expected.vibe_verifier.agent_uid,
        expected.vibe_verifier.run_id,
    )
    bare_digests = (
        expected.diff_sha256,
        expected.artifact_sha256,
        expected.foundry_verifier.signer_public_key,
        expected.vibe_verifier.signer_public_key,
    )
    foundry_digests = (
        expected.candidate_digest,
        expected.lineage_digest,
        expected.command_digest,
        expected.output_digest,
        expected.isolation_digest,
    )
    if (
        any(not value or len(value) > 128 for value in strings)
        or expected.mission_id != ref.mission_id
        or expected.task_id != ref.task_id
        or expected.attempt_id != ref.attempt_id
        or expected.lease_id != ref.lease_id
        or expected.packet_id != ref.packet_id
        or expected.correlation_id != ref.correlation_id
        or expected.delivery_id != ref.delivery_id
        or expected.proposal_id != ref.proposal_id
        or expected.executor_agent_uid != ref.agent_uid
        or (artifact_sha256 is not None and expected.artifact_sha256 != artifact_sha256)
        or not all(_SHA256.fullmatch(value) for value in bare_digests)
        or not all(_FOUNDRY_DIGEST.fullmatch(value) for value in foundry_digests)
        or not _GIT_SHA.fullmatch(expected.base_sha)
        or not expected.authorized_source_files
        or any(
            not path or Path(path).is_absolute() or ".." in Path(path).parts
            for path in expected.authorized_source_files
        )
    ):
        raise MissionControlError(
            "promotion bindings do not match observed A2A execution"
        )


def _identity_matches_expected(
    identity: ExecutionIdentity,
    expected: ExpectedPromotionBindings,
    *,
    role: Literal["executor", "foundry", "vibe_halt"],
) -> bool:
    principal = {
        "foundry": expected.foundry_verifier,
        "vibe_halt": expected.vibe_verifier,
    }.get(role)
    expected_agent = principal.agent_uid if principal else expected.executor_agent_uid
    expected_run = principal.run_id if principal else expected.executor_run_id
    return (
        identity.task_id == expected.task_id
        and identity.correlation_id == expected.correlation_id
        and identity.session_id == mission_session_id(expected.mission_id)
        and identity.proposal_id == expected.proposal_id
        and identity.agent_id == expected_agent
        and identity.run_id == expected_run
        and (identity.parent_run_id == expected.executor_run_id if principal else True)
        and bool(identity.trace_id)
        and bool(identity.claim_id)
        and bool(identity.idempotency_key)
    )


_LAZY_EXPORTS = {
    "A2APatchPromotionEvaluator": (
        "dharma_swarm.mission_control_a2a_evaluator",
        "A2APatchPromotionEvaluator",
    ),
    "MissionControlA2AProjection": (
        "dharma_swarm.mission_control_a2a_projection",
        "MissionControlA2AProjection",
    ),
    "CanonicalA2AEvidenceReader": (
        "dharma_swarm.mission_control_a2a_evidence",
        "CanonicalA2AEvidenceReader",
    ),
    "DELIVERY_SCHEMA": (
        "dharma_swarm.mission_control_a2a_evidence",
        "DELIVERY_SCHEMA",
    ),
    "read_bytes": ("dharma_swarm.mission_control_a2a_io", "read_bytes"),
    "read_json": ("dharma_swarm.mission_control_a2a_io", "read_json"),
    "safe_file": ("dharma_swarm.mission_control_a2a_io", "safe_file"),
    "_existing_db": ("dharma_swarm.mission_control_a2a_io", "_existing_db"),
    "_read_only_db": ("dharma_swarm.mission_control_a2a_io", "_read_only_db"),
    "_regular_state": ("dharma_swarm.mission_control_a2a_io", "_regular_state"),
    "_snapshot_database": (
        "dharma_swarm.mission_control_a2a_io",
        "_snapshot_database",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve compatibility exports without introducing import cycles."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "A2A_BINDING_SCHEMA",
    "A2AEvidencePhase",
    "A2AExecutionObservation",
    "A2ANativeExecutionRef",
    "A2APatchPromotionEvaluator",
    "MissionControlA2AProjection",
]
