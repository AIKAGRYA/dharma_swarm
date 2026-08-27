"""Exact atomic proposal evidence reader for the Mission Control A2A seam."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_a2a import A2ANativeExecutionRef
from dharma_swarm.mission_control_a2a_io import _read_only_db
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.spine.identity import ExecutionIdentity

_EXACT_SELF_MOD_SCHEMA = "dharma.runtime.self_mod_exact.v1"
_EXACT_SELF_MOD_AUTHORITY = "attestation_only"
_EXACT_PROPOSAL_WRAPPER_FIELDS = {
    "schema_version",
    "authority_semantics",
    "proposal_id",
    "stage",
    "evidence",
    "operation_hash",
}


@dataclass(frozen=True, slots=True)
class ExactProposalRecord:
    """One proposal receipt and every idempotency row occupying its slot."""

    receipt: RuntimeReceipt
    idempotency_rows: tuple[dict[str, Any], ...]


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

    columns = (
        "receipt_id, receipt_type, status, run_id, task_id, trace_id, "
        "correlation_id, causation_id, parent_run_id, agent_id, "
        "idempotency_key, side_effect_key, payload_json, created_at"
    )
    records: list[ExactProposalRecord] = []
    with _read_only_db(runtime_db, "RuntimeState") as connection:
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


__all__ = ["ExactProposalRecord", "load_exact_proposals", "unwrap_exact_proposal"]
