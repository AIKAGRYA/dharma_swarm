"""Exact RuntimeReceipt/idempotency/fence terminal triple writer."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.mission_control_effect_codec import (
    canonical_json,
    terminal_from_json,
)
from dharma_swarm.mission_control_effect_fence_store import collision, row_binding
from dharma_swarm.mission_control_effect_records import (
    EffectMutationResult,
    EffectTerminalRecord,
)
from dharma_swarm.mission_control_effect_supervisor import supervisor_authority_sha256
from dharma_swarm.mission_control_effect_warrant import (
    EffectBinding,
    SupervisorEffectAuthority,
)
from dharma_swarm.runtime_state_effect_fence import (
    EFFECT_FENCE_TABLE,
    EFFECT_RECEIPT_ID_PREFIX,
    EFFECT_RECEIPT_TYPE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _time(raw: object) -> datetime:
    value = datetime.fromisoformat(str(raw))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effect fence timestamp is naive")
    return value


def _receipt_values(
    record: EffectTerminalRecord, binding: EffectBinding, payload: str,
) -> dict[str, str]:
    return {
        "receipt_id": record.terminal_receipt_id, "receipt_type": EFFECT_RECEIPT_TYPE,
        "run_id": binding.mission_attempt_id, "task_id": binding.task_id,
        "trace_id": "", "correlation_id": binding.correlation_id,
        "causation_id": binding.proposal_receipt_id,
        "parent_run_id": binding.executor_run_id, "agent_id": record.claimed_by,
        "idempotency_key": "idem_" + record.terminal_receipt_id,
        "side_effect_key": binding.effect_key, "status": "consumed",
        "payload_json": payload, "created_at": record.consumed_at.isoformat(),
    }


def _receipt_sha(record: EffectTerminalRecord, binding: EffectBinding) -> str:
    body = record.to_dict()
    body["terminal_receipt_sha256"] = ""
    return canonical_sha256(_receipt_values(record, binding, canonical_json(body)))


def recovery_result(binding: EffectBinding, observed: object) -> EffectMutationResult:
    scratch = binding.canary.scratch
    return EffectMutationResult(
        scratch.source_path, scratch.preimage_sha256, scratch.postimage_sha256,
        scratch.scratch_identity, scratch.preimage_sha256,
        scratch.target_device, scratch.target_inode,
        observed.target_device, observed.target_inode,
        scratch.target_mode, scratch.target_uid, scratch.target_gid,
        scratch.target_nlink, observed.target_mode, observed.target_uid,
        observed.target_gid, observed.target_nlink,
    )


def terminal_matches_current_target(
    record: EffectTerminalRecord, observed: object,
) -> bool:
    return bool(
        observed.disposition == "recovery_finalizable"
        and observed.observed_sha256 == record.postimage_sha256
        and (
            observed.target_device, observed.target_inode, observed.target_mode,
            observed.target_uid, observed.target_gid, observed.target_nlink,
        ) == (
            record.target_device_after, record.target_inode_after,
            record.target_mode_after, record.target_uid_after,
            record.target_gid_after, record.target_nlink_after,
        )
    )


def terminal_record(
    row: sqlite3.Row, binding: EffectBinding, result: EffectMutationResult, *,
    claimed_by: str, generation: int, consuming: datetime,
    recovery_authority: SupervisorEffectAuthority | None,
    recovery_owner_basis: str = "",
    recovery_owner_observation_sha256: str = "",
) -> EffectTerminalRecord:
    consumed = _now()
    digest = hashlib.sha256(binding.effect_key.encode()).hexdigest()
    recovery = recovery_authority
    record = EffectTerminalRecord(
        "etr_" + digest, EFFECT_RECEIPT_ID_PREFIX + digest, "", str(row["fence_id"]),
        binding.effect_key, binding.binding_sha256, binding.candidate_bundle_sha256,
        binding.diff_sha256, binding.base_sha, result.path, result.preimage_sha256,
        result.postimage_sha256, result.scratch_identity, str(row["warrant_sha256"]),
        binding.supervisor_id, binding.supervisor_process_boot_id, generation,
        claimed_by, result.target_device_before, result.target_inode_before,
        result.target_device_after, result.target_inode_after,
        result.target_mode_before, result.target_uid_before, result.target_gid_before,
        result.target_nlink_before, result.target_mode_after, result.target_uid_after,
        result.target_gid_after, result.target_nlink_after, _time(row["fence_created_at"]),
        consuming, consumed, recovery is not None,
        recovery.supervisor_id if recovery is not None else "",
        recovery.process_boot_id if recovery is not None else "",
        supervisor_authority_sha256(recovery) if recovery is not None else "",
        recovery_owner_basis,
        recovery_owner_observation_sha256,
    )
    return replace(record, terminal_receipt_sha256=_receipt_sha(record, binding))


def write_terminal(
    db: sqlite3.Connection, row: sqlite3.Row, binding: EffectBinding,
    record: EffectTerminalRecord, claim_token_sha: str,
) -> EffectTerminalRecord:
    blank = replace(record, terminal_receipt_sha256="")
    if record.terminal_receipt_sha256 != _receipt_sha(blank, binding):
        raise ValueError("terminal receipt digest convention disagrees")
    final_payload = canonical_json(record.to_dict())
    if terminal_from_json(final_payload) != record:
        raise ValueError("terminal record codec disagrees before persistence")
    values = _receipt_values(record, binding, final_payload)
    idem = values["idempotency_key"]
    if collision(db, binding.effect_key, record.terminal_receipt_id, idem):
        raise sqlite3.IntegrityError("effect terminal triple is occupied")
    names = tuple(values)
    metadata = canonical_json({
        "schema": "dharma.mission_control.effect_idempotency.v1",
        "binding_sha256": binding.binding_sha256,
        "terminal_receipt_sha256": record.terminal_receipt_sha256,
    })
    idem_values = {
        "idempotency_key": idem, "side_effect_key": binding.effect_key,
        "run_id": binding.mission_attempt_id, "task_id": binding.task_id,
        "trace_id": "", "correlation_id": binding.correlation_id,
        "status": "completed", "result_receipt_id": record.terminal_receipt_id,
        "metadata_json": metadata, "created_at": record.consumed_at.isoformat(),
        "updated_at": record.consumed_at.isoformat(),
    }
    db.execute(
        f"INSERT OR ABORT INTO runtime_receipts ({','.join(names)})"
        f" VALUES ({','.join('?' for _ in names)})", tuple(values.values()),
    )
    db.execute(
        "INSERT OR ABORT INTO idempotency_records (idempotency_key,side_effect_key,"
        "run_id,task_id,trace_id,correlation_id,status,result_receipt_id,metadata_json,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        tuple(idem_values.values()),
    )
    cursor = db.execute(
        f"UPDATE {EFFECT_FENCE_TABLE} SET state='consumed',terminal_record_json=?,"
        "terminal_receipt_id=?,consumed_at=?,warrant_token_sha256='',"
        "recovery_supervisor_id=?,recovery_supervisor_process_boot_id=?,"
        "recovery_supervisor_authority_sha256=? WHERE fence_id=? AND state='consuming'"
        " AND binding_sha256=? AND claim_token_sha256=?",
        (final_payload, record.terminal_receipt_id, record.consumed_at.isoformat(),
         record.recovery_supervisor_id, record.recovery_supervisor_process_boot_id,
         record.recovery_supervisor_authority_sha256, row["fence_id"],
         binding.binding_sha256, claim_token_sha),
    )
    post = db.execute(
        f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE fence_id=?", (row["fence_id"],),
    ).fetchone()
    receipt = db.execute(
        "SELECT * FROM runtime_receipts WHERE receipt_id=? OR side_effect_key=?"
        " OR idempotency_key=?",
        (record.terminal_receipt_id, binding.effect_key, idem),
    ).fetchall()
    idem_rows = db.execute(
        "SELECT * FROM idempotency_records WHERE idempotency_key=? OR side_effect_key=?"
        " OR result_receipt_id=?", (idem, binding.effect_key, record.terminal_receipt_id),
    ).fetchall()
    if (
        cursor.rowcount != 1 or post is None or row_binding(post) != binding
        or tuple(post[name] for name in (
            "state", "terminal_record_json", "terminal_receipt_id", "consumed_at",
            "warrant_token_sha256", "recovery_supervisor_id",
            "recovery_supervisor_process_boot_id",
            "recovery_supervisor_authority_sha256", "claim_generation",
            "claim_token_sha256", "claimed_by", "consuming_at",
            "quarantine_reason", "observed_sha256", "quarantined_at",
        )) != (
            "consumed", final_payload, record.terminal_receipt_id,
            record.consumed_at.isoformat(), "", record.recovery_supervisor_id,
            record.recovery_supervisor_process_boot_id,
            record.recovery_supervisor_authority_sha256, record.claim_generation,
            claim_token_sha, record.claimed_by, record.consuming_at.isoformat(),
            "", "", None,
        ) or post["claim_expires_at"] is None
        or record.consumed_at >= _time(post["claim_expires_at"])
        or len(receipt) != 1
        or any(receipt[0][name] != value for name, value in values.items())
        or len(idem_rows) != 1
        or any(idem_rows[0][name] != value for name, value in idem_values.items())
    ):
        raise sqlite3.IntegrityError("effect terminal triple exact postread disagrees")
    return record


def existing_terminal(db: sqlite3.Connection, row: sqlite3.Row) -> EffectTerminalRecord:
    record = terminal_from_json(str(row["terminal_record_json"]))
    binding = row_binding(row)
    payload = canonical_json(record.to_dict())
    values = _receipt_values(record, binding, payload)
    receipt = db.execute(
        "SELECT * FROM runtime_receipts WHERE receipt_id=? OR side_effect_key=?"
        " OR idempotency_key=?",
        (record.terminal_receipt_id, record.effect_key, values["idempotency_key"]),
    ).fetchall()
    idem = db.execute(
        "SELECT * FROM idempotency_records WHERE idempotency_key=? OR side_effect_key=?"
        " OR result_receipt_id=?", (values["idempotency_key"], record.effect_key,
                                    record.terminal_receipt_id),
    ).fetchall()
    metadata = canonical_json({
        "schema": "dharma.mission_control.effect_idempotency.v1",
        "binding_sha256": binding.binding_sha256,
        "terminal_receipt_sha256": record.terminal_receipt_sha256,
    })
    idem_values = {
        "idempotency_key": values["idempotency_key"],
        "side_effect_key": record.effect_key, "run_id": binding.mission_attempt_id,
        "task_id": binding.task_id, "trace_id": "",
        "correlation_id": binding.correlation_id, "status": "completed",
        "result_receipt_id": record.terminal_receipt_id, "metadata_json": metadata,
        "created_at": record.consumed_at.isoformat(),
        "updated_at": record.consumed_at.isoformat(),
    }
    digest = hashlib.sha256(record.effect_key.encode()).hexdigest()
    scratch = binding.canary.scratch
    exact_record = (
        record.terminal_id == "etr_" + digest
        and record.terminal_receipt_id == EFFECT_RECEIPT_ID_PREFIX + digest
        and (record.fence_id, record.effect_key, record.binding_sha256)
        == (row["fence_id"], binding.effect_key, binding.binding_sha256)
        and (record.candidate_bundle_sha256, record.diff_sha256, record.base_sha,
             record.path, record.preimage_sha256, record.postimage_sha256,
             record.scratch_identity, record.warrant_sha256)
        == (binding.candidate_bundle_sha256, binding.diff_sha256, binding.base_sha,
            scratch.source_path, scratch.preimage_sha256, scratch.postimage_sha256,
            scratch.scratch_identity, row["warrant_sha256"])
        and (record.supervisor_id, record.supervisor_process_boot_id)
        == (binding.supervisor_id, binding.supervisor_process_boot_id)
        and (record.target_device_before, record.target_inode_before,
             record.target_mode_before, record.target_uid_before,
             record.target_gid_before, record.target_nlink_before)
        == (scratch.target_device, scratch.target_inode, scratch.target_mode,
            scratch.target_uid, scratch.target_gid, scratch.target_nlink)
        and record.target_device_after == record.target_device_before
        and record.target_inode_after != record.target_inode_before
        and (record.target_mode_after, record.target_uid_after,
             record.target_gid_after, record.target_nlink_after)
        == (record.target_mode_before, record.target_uid_before,
            record.target_gid_before, record.target_nlink_before)
        and record.fence_created_at == _time(row["fence_created_at"])
        and record.fence_created_at <= record.consuming_at <= record.consumed_at
        and _time(row["warrant_issued_at"]) <= record.consuming_at
        and record.consumed_at.isoformat() == row["consumed_at"]
        and record.claim_generation == row["claim_generation"]
        and record.claimed_by == row["claimed_by"]
        and record.consuming_at.isoformat() == row["consuming_at"]
        and (record.recovery_supervisor_id,
             record.recovery_supervisor_process_boot_id,
             record.recovery_supervisor_authority_sha256)
        == (row["recovery_supervisor_id"],
            row["recovery_supervisor_process_boot_id"],
            row["recovery_supervisor_authority_sha256"])
        and record.recovery_finalized
        == bool(record.recovery_supervisor_authority_sha256)
        and (bool(record.recovery_supervisor_id)
             == bool(record.recovery_supervisor_process_boot_id)
             == bool(record.recovery_supervisor_authority_sha256))
        and row["terminal_record_json"] == payload
        and row["terminal_receipt_id"] == record.terminal_receipt_id
        and row["warrant_token_sha256"] == ""
        and row["claim_token_sha256"] != ""
        and row["claim_expires_at"] is not None
        and record.consumed_at < _time(row["claim_expires_at"])
        and row["quarantine_reason"] == "" and row["observed_sha256"] == ""
        and row["quarantined_at"] is None
    )
    if (
        row["state"] != "consumed" or not exact_record
        or len(receipt) != 1 or len(idem) != 1
        or any(receipt[0][name] != value for name, value in values.items())
        or any(idem[0][name] != value for name, value in idem_values.items())
        or record.terminal_receipt_sha256
        != _receipt_sha(replace(record, terminal_receipt_sha256=""), binding)
    ):
        raise sqlite3.IntegrityError("existing effect terminal triple conflicts")
    return record


__all__ = [
    "existing_terminal", "recovery_result", "terminal_matches_current_target",
    "terminal_record", "write_terminal",
]
