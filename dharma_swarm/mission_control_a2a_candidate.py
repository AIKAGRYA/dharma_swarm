"""Exact atomic proposal evidence reader for the Mission Control A2A seam."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.a2a.agent_card import resolve_agent_uid
from dharma_swarm.mission_control_a2a import (
    A2A_BINDING_SCHEMA,
    A2ANativeExecutionRef,
    _DELIVERY_ID,
    _FOUNDRY_DIGEST,
    _GIT_SHA,
    _SHA256,
    _safe_token,
)
from dharma_swarm.mission_control_a2a_io import _read_only_db
from dharma_swarm.mission_control_contract import MissionControlError, clean_identifier
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.spine.identity import ExecutionIdentity

_EXACT_SELF_MOD_SCHEMA = "dharma.runtime.self_mod_exact.v1"
_EXACT_SELF_MOD_AUTHORITY = "attestation_only"
_MAX_EXACT_JSON_CHARS = 2 * 1024 * 1024
_EXACT_PROPOSAL_WRAPPER_FIELDS = {
    "schema_version",
    "authority_semantics",
    "proposal_id",
    "stage",
    "evidence",
    "operation_hash",
}
_STORE_OBSERVATION_SEAL = object()


@dataclass(frozen=True, slots=True)
class ExactProposalRecord:
    """One proposal receipt and every idempotency row occupying its slot."""

    receipt: RuntimeReceipt
    idempotency_rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ExactProposalStoreExpectation:
    """Committed query values; lifecycle IDs are deliberately not accepted."""

    native_ref: A2ANativeExecutionRef
    attempt_key: str
    operator_id: str
    assigned_by: str
    executor_run_id: str
    executor_process_boot_id: str
    candidate_digest: str
    diff_sha256: str
    base_sha: str
    artifact_sha256: str
    authorized_source_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExactProposalStoreObservation:
    """Internally consistent owner rows; never a repository-effect warrant."""

    native_ref: A2ANativeExecutionRef
    mission_attempt_id: str
    mission_claim_id: str
    executor_run_id: str
    executor_process_boot_id: str
    proposal_receipt_id: str
    proposal_receipt_sha256: str
    observed_at: datetime
    lease_stale_after: datetime
    task_status: str = field(default="running", init=False)
    snapshot_kind: str = field(default="bracketed_stable_join", init=False)
    canonical_store_custody_unproven: bool = field(default=True, init=False)
    proves_executor_liveness: bool = field(default=False, init=False)
    authorizes_repository_effect: bool = field(default=False, init=False)
    _seal: object | None = field(default=None, init=False, repr=False, compare=False)

    @classmethod
    def _mint(cls, **values: Any) -> ExactProposalStoreObservation:
        result = cls(**values)
        object.__setattr__(result, "_seal", _STORE_OBSERVATION_SEAL)
        return result

    def __bool__(self) -> bool:
        raise TypeError("store observations cannot be used as authority booleans")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("_seal", None)
        payload["observed_at"] = self.observed_at.isoformat()
        payload["lease_stale_after"] = self.lease_stale_after.isoformat()
        return payload


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def _load_canonical_object(raw: str, *, label: str) -> dict[str, Any]:
    def reject_constant(constant: str) -> None:
        raise ValueError(f"non-finite JSON constant {constant}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key {key!r}")
            value[key] = child
        return value

    try:
        if type(raw) is not str or len(raw) > _MAX_EXACT_JSON_CHARS:
            raise ValueError("JSON text exceeds its exact read bound")
        value = json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
        if not isinstance(value, dict) or _canonical_json(value) != raw:
            raise ValueError("not one canonical JSON object")
    except (TypeError, ValueError) as exc:
        raise MissionControlError(f"{label} is malformed or noncanonical") from exc
    return value


def load_exact_proposals(
    runtime_db: Path,
    ref: A2ANativeExecutionRef,
    *,
    scan_limit: int,
) -> list[ExactProposalRecord]:
    """Read proposal receipts and their exact idempotency slots in one snapshot."""

    with _read_only_db(runtime_db, "RuntimeState") as connection:
        return load_exact_proposals_from_connection(
            connection,
            ref,
            scan_limit=scan_limit,
        )


def load_exact_proposals_from_connection(
    connection: sqlite3.Connection,
    ref: A2ANativeExecutionRef,
    *,
    scan_limit: int,
) -> list[ExactProposalRecord]:
    """Read exact proposal pairs through an already stable owner snapshot."""

    columns = (
        "receipt_id, receipt_type, status, run_id, task_id, trace_id, "
        "correlation_id, causation_id, parent_run_id, agent_id, "
        "idempotency_key, side_effect_key, payload_json, created_at"
    )
    records: list[ExactProposalRecord] = []
    rows = connection.execute(
        f"SELECT {columns} FROM runtime_receipts "
        "WHERE correlation_id = ? AND receipt_type = 'self_mod_proposal' "
        "ORDER BY created_at ASC LIMIT ?",
        (ref.correlation_id, scan_limit + 1),
    ).fetchall()
    for row in rows:
        payload = _load_canonical_object(
            str(row["payload_json"] or "{}"),
            label="self-mod proposal evidence",
        )
        try:
            created_at = datetime.fromisoformat(str(row["created_at"]))
        except ValueError as exc:
            raise MissionControlError(
                "self-mod proposal evidence is malformed",
            ) from exc
        receipt = RuntimeReceipt(
            receipt_id=str(row["receipt_id"]),
            receipt_type=str(row["receipt_type"]),
            status=str(row["status"]),
            run_id=str(row["run_id"] or ""),
            task_id=str(row["task_id"] or ""),
            trace_id=str(row["trace_id"] or ""),
            correlation_id=str(row["correlation_id"] or ""),
            causation_id=str(row["causation_id"] or ""),
            parent_run_id=str(row["parent_run_id"] or ""),
            agent_id=str(row["agent_id"] or ""),
            idempotency_key=str(row["idempotency_key"] or ""),
            side_effect_key=str(row["side_effect_key"] or ""),
            payload=payload,
            created_at=created_at,
        )
        rows_for_slot = connection.execute(
            "SELECT idempotency_key, side_effect_key, run_id, task_id,"
            " trace_id, correlation_id, status, result_receipt_id,"
            " metadata_json, created_at, updated_at"
            " FROM idempotency_records WHERE side_effect_key = ? LIMIT 3",
            (receipt.side_effect_key,),
        ).fetchall()
        idempotency_rows: list[dict[str, Any]] = []
        for slot_row in rows_for_slot:
            metadata = _load_canonical_object(
                str(slot_row["metadata_json"] or "{}"),
                label="self-mod proposal idempotency evidence",
            )
            idempotency_rows.append(
                {
                    **{
                        key: str(slot_row[key] or "")
                        for key in (
                            "idempotency_key",
                            "side_effect_key",
                            "run_id",
                            "task_id",
                            "trace_id",
                            "correlation_id",
                            "status",
                            "result_receipt_id",
                            "created_at",
                            "updated_at",
                        )
                    },
                    "metadata": metadata,
                },
            )
        records.append(
            ExactProposalRecord(
                receipt=receipt,
                idempotency_rows=tuple(idempotency_rows),
            ),
        )
    return records


def unwrap_exact_proposal(
    record: ExactProposalRecord,
    ref: A2ANativeExecutionRef,
    executor: ExecutionIdentity,
) -> dict[str, Any]:
    """Return candidate evidence only for the exact writer's closed pair."""

    proposal = record.receipt
    wrapper = proposal.payload
    evidence = wrapper.get("evidence")
    wrapper_without_hash = {
        key: wrapper.get(key)
        for key in (
            "schema_version",
            "authority_semantics",
            "proposal_id",
            "stage",
            "evidence",
        )
    }
    slot_json = _canonical_json(
        {"proposal_id": ref.proposal_id, "stage": "proposal"},
    )
    expected_receipt_id = (
        "rr_self_mod_exact_"
        + hashlib.sha256(slot_json.encode("utf-8")).hexdigest()[:32]
    )
    side_effect_key = f"self_mod:{ref.proposal_id}:proposal"
    receipt_semantics = {
        "receipt_id": expected_receipt_id,
        "receipt_type": "self_mod_proposal",
        "run_id": executor.run_id,
        "task_id": executor.task_id,
        "trace_id": executor.trace_id,
        "correlation_id": executor.correlation_id,
        "causation_id": executor.causation_id,
        "parent_run_id": executor.parent_run_id,
        "agent_id": executor.agent_id,
        "idempotency_key": executor.idempotency_key,
        "side_effect_key": side_effect_key,
        "status": "proposed",
        "payload": wrapper_without_hash,
    }
    try:
        operation_hash = hashlib.sha256(
            _canonical_json(
                {
                    "execution_identity": executor.to_dict(),
                    "runtime_receipt": receipt_semantics,
                },
            ).encode("utf-8"),
        ).hexdigest()
    except (TypeError, ValueError) as exc:
        raise MissionControlError(
            "patch candidate exact evidence is not canonical",
        ) from exc
    timestamp = proposal.created_at.isoformat()
    expected_idempotency = {
        "idempotency_key": executor.idempotency_key,
        "side_effect_key": side_effect_key,
        "run_id": executor.run_id,
        "task_id": executor.task_id,
        "trace_id": executor.trace_id,
        "correlation_id": executor.correlation_id,
        "status": "completed",
        "result_receipt_id": expected_receipt_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "metadata": {
            "schema_version": _EXACT_SELF_MOD_SCHEMA,
            "authority_semantics": _EXACT_SELF_MOD_AUTHORITY,
            "stage": "proposal",
            "proposal_id": ref.proposal_id,
            "receipt_id": expected_receipt_id,
            "operation_hash": operation_hash,
        },
    }
    receipt_identity = (
        proposal.run_id == executor.run_id
        and proposal.task_id == executor.task_id
        and proposal.trace_id == executor.trace_id
        and proposal.correlation_id == executor.correlation_id
        and proposal.causation_id == executor.causation_id
        and proposal.parent_run_id == executor.parent_run_id
        and proposal.agent_id == executor.agent_id
        and proposal.idempotency_key == executor.idempotency_key
    )
    exact = (
        set(wrapper) == _EXACT_PROPOSAL_WRAPPER_FIELDS
        and wrapper.get("schema_version") == _EXACT_SELF_MOD_SCHEMA
        and wrapper.get("authority_semantics") == _EXACT_SELF_MOD_AUTHORITY
        and wrapper.get("proposal_id") == ref.proposal_id
        and wrapper.get("stage") == "proposal"
        and isinstance(evidence, dict)
        and wrapper.get("operation_hash") == operation_hash
        and proposal.receipt_id == expected_receipt_id
        and proposal.receipt_type == "self_mod_proposal"
        and proposal.status == "proposed"
        and proposal.created_at.tzinfo is not None
        and proposal.side_effect_key == side_effect_key
        and receipt_identity
        and len(record.idempotency_rows) == 1
        and record.idempotency_rows[0] == expected_idempotency
    )
    if not exact:
        raise MissionControlError(
            "patch candidate is not exact atomic proposal evidence",
        )
    assert isinstance(evidence, dict)
    return evidence


def require_store_expectation(expected: ExactProposalStoreExpectation) -> None:
    """Validate caller commitments before copying either owner database."""

    if type(expected) is not ExactProposalStoreExpectation:
        raise MissionControlError("exact proposal store expectation is required")
    ref = expected.native_ref
    if type(ref) is not A2ANativeExecutionRef:
        raise MissionControlError("exact native A2A reference is required")
    ref_values = (
        ref.mission_id,
        ref.task_id,
        ref.agent_uid,
        ref.packet_id,
        ref.correlation_id,
        ref.delivery_id,
        ref.proposal_id,
        ref.content_sha256,
    )
    commitments = (
        expected.attempt_key,
        expected.operator_id,
        expected.assigned_by,
        expected.executor_run_id,
        expected.executor_process_boot_id,
        expected.candidate_digest,
        expected.diff_sha256,
        expected.base_sha,
        expected.artifact_sha256,
    )
    if any(
        type(value) is not str or not value or len(value) > 256
        for value in (*ref_values, *commitments)
    ):
        raise MissionControlError("proposal store expectation strings are malformed")
    clean_identifier(ref.mission_id, "mission_id")
    clean_identifier(ref.task_id, "task_id")
    for value, label in (
        (ref.agent_uid, "agent_uid"),
        (ref.packet_id, "packet_id"),
        (ref.proposal_id, "proposal_id"),
        (expected.executor_run_id, "executor_run_id"),
        (expected.executor_process_boot_id, "executor_process_boot_id"),
    ):
        _safe_token(value, label)
    try:
        canonical_agent = resolve_agent_uid(ref.agent_uid)
    except ValueError as exc:
        raise MissionControlError("proposal store agent UID is malformed") from exc
    if canonical_agent != ref.agent_uid:
        raise MissionControlError("proposal store agent UID is not canonical")
    if (
        ref.correlation_id != f"a2a_send:{ref.agent_uid}:{ref.packet_id}"
        or not _DELIVERY_ID.fullmatch(ref.delivery_id)
        or not _SHA256.fullmatch(ref.content_sha256)
        or not _FOUNDRY_DIGEST.fullmatch(expected.candidate_digest)
        or not _SHA256.fullmatch(expected.diff_sha256)
        or not _GIT_SHA.fullmatch(expected.base_sha)
        or not _SHA256.fullmatch(expected.artifact_sha256)
    ):
        raise MissionControlError("proposal store expectation digests disagree")
    for value, label in (
        (expected.attempt_key, "attempt_key"),
        (expected.operator_id, "operator_id"),
        (expected.assigned_by, "assigned_by"),
    ):
        clean_identifier(value, label)
    files = expected.authorized_source_files
    if (
        type(files) is not tuple
        or not files
        or len(files) > 256
        or any(
            type(path) is not str
            or not path
            or len(path) > 4096
            or "\x00" in path
            or "\\" in path
            or Path(path).is_absolute()
            or Path(path) == Path(".")
            or Path(path).as_posix() != path
            or ".." in Path(path).parts
            for path in files
        )
    ):
        raise MissionControlError("authorized source files are malformed")
    if len(set(files)) != len(files):
        raise MissionControlError("authorized source files must be unique")


def require_task_native_ref(
    metadata: dict[str, Any],
    ref: A2ANativeExecutionRef,
) -> None:
    binding = metadata.get("a2a_binding")
    required = {
        "schema_version": A2A_BINDING_SCHEMA,
        "agent_uid": ref.agent_uid,
        "packet_id": ref.packet_id,
        "correlation_id": ref.correlation_id,
        "delivery_id": ref.delivery_id,
        "proposal_id": ref.proposal_id,
        "content_sha256": ref.content_sha256,
    }
    if (
        type(binding) is not dict
        or binding.keys() != required.keys()
        or any(
            type(binding[key]) is not str or binding[key] != value
            for key, value in required.items()
        )
    ):
        raise MissionControlError(
            "task A2A binding disagrees with the native reference"
        )


__all__ = [
    "ExactProposalRecord",
    "ExactProposalStoreExpectation",
    "ExactProposalStoreObservation",
    "load_exact_proposals",
    "load_exact_proposals_from_connection",
    "require_store_expectation",
    "require_task_native_ref",
    "unwrap_exact_proposal",
]
