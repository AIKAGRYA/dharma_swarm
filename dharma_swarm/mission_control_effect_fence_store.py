"""Private exact-row writer for the governed repository-effect fence."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone

from dharma_swarm.mission_control_effect_codec import (
    canonical_json,
    effect_binding_from_json,
)
from dharma_swarm.mission_control_effect_warrant import (
    EffectBinding,
    effect_warrant_evidence_sha256,
)
from dharma_swarm.runtime_state_effect_fence import (
    EFFECT_FENCE_TABLE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _time(raw: object) -> datetime:
    value = datetime.fromisoformat(str(raw))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("effect fence timestamp is naive")
    return value


def fence_id_for(effect_key: str) -> str:
    return "ef_" + hashlib.sha256(effect_key.encode("utf-8")).hexdigest()


def _projection(binding: EffectBinding) -> dict[str, object]:
    canary, scratch = binding.canary, binding.canary.scratch
    return {
        "effect_key": canary.effect_key, "mission_id": canary.mission_id,
        "task_id": canary.task_id, "mission_attempt_id": canary.mission_attempt_id,
        "mission_claim_id": canary.mission_claim_id, "packet_id": canary.packet_id,
        "correlation_id": canary.correlation_id, "delivery_id": canary.delivery_id,
        "proposal_id": canary.proposal_id, "candidate_digest": canary.candidate_digest,
        "diff_sha256": canary.diff_sha256, "base_sha": canary.base_sha,
        "artifact_sha256": canary.artifact_sha256,
        "candidate_bundle_sha256": canary.candidate_bundle_sha256,
        "source_path": scratch.source_path, "source_sha256": scratch.preimage_sha256,
        "postimage_sha256": scratch.postimage_sha256,
        "authorized_source_files_json": canonical_json(list(canary.authorized_source_files)),
        "executor_agent_uid": canary.executor_agent_uid,
        "executor_run_id": canary.executor_run_id,
        "executor_process_boot_id": canary.executor_process_boot_id,
        "proposal_receipt_id": canary.proposal_receipt_id,
        "proposal_receipt_sha256": canary.proposal_receipt_sha256,
        "independent_verification_sha256": binding.independent_verification_sha256,
        "foundry_canary_evidence_sha256": binding.foundry_canary_evidence_sha256,
        "foundry_process_receipt_sha256": binding.foundry_process_receipt_sha256,
        "vibe_process_receipt_sha256": binding.vibe_process_receipt_sha256,
        "vibe_patch_receipt_sha256": binding.vibe_patch_receipt_sha256,
        "supervisor_authority_sha256": binding.supervisor_authority_sha256,
        "binding_sha256": binding.binding_sha256,
        "effect_binding_json": canonical_json(binding.to_dict()),
        "scratch_identity": scratch.scratch_identity,
        "scratch_binding_json": canonical_json(scratch.to_dict()),
    }


def row_binding(row: sqlite3.Row) -> EffectBinding:
    binding = effect_binding_from_json(str(row["effect_binding_json"]))
    expected = _projection(binding)
    if (
        str(row["fence_id"]) != fence_id_for(binding.effect_key)
        or any(row[name] != value for name, value in expected.items())
    ):
        raise ValueError("durable effect binding projection disagrees")
    return binding


def _issued_defaults(row: sqlite3.Row) -> bool:
    return tuple(row[name] for name in (
        "state", "claim_generation", "claim_token_sha256", "claimed_by",
        "claim_expires_at", "consuming_at", "terminal_record_json",
        "terminal_receipt_id", "consumed_at", "recovery_supervisor_id",
        "recovery_supervisor_process_boot_id",
        "recovery_supervisor_authority_sha256", "quarantine_reason",
        "observed_sha256", "quarantined_at",
    )) == (
        "issued", 0, "", "", None, None, None, "", None, "", "", "", "", "", None,
    )


def exact_issued(row: sqlite3.Row, binding: EffectBinding) -> bool:
    """Validate the whole durable issued state, including its public warrant."""

    try:
        issued = _time(row["warrant_issued_at"])
        expires = _time(row["warrant_expires_at"])
        token_sha = str(row["warrant_token_sha256"])
        warrant_sha = str(row["warrant_sha256"])
        return bool(
            row_binding(row) == binding and _issued_defaults(row)
            and _time(row["fence_created_at"]) <= issued < expires
            and len(token_sha) == len(warrant_sha) == 64
            and all(character in "0123456789abcdef" for character in token_sha + warrant_sha)
            and warrant_sha == effect_warrant_evidence_sha256(
                fence_id=str(row["fence_id"]), binding=binding,
                issued_at=issued, expires_at=expires,
                warrant_token_sha256=token_sha,
            )
        )
    except (KeyError, TypeError, ValueError):
        return False


def insert_issued(
    db: sqlite3.Connection, binding: EffectBinding, issued: datetime,
    expires: datetime, token_sha: str, warrant_sha: str,
) -> str:
    fence_id = fence_id_for(binding.effect_key)
    values = {
        "fence_id": fence_id, "state": "issued", **_projection(binding),
        "fence_created_at": issued.isoformat(),
        "warrant_issued_at": issued.isoformat(),
        "warrant_expires_at": expires.isoformat(),
        "warrant_token_sha256": token_sha, "warrant_sha256": warrant_sha,
    }
    names = tuple(values)
    cursor = db.execute(
        f"INSERT OR ABORT INTO {EFFECT_FENCE_TABLE} ({','.join(names)})"
        f" VALUES ({','.join('?' for _ in names)})",
        tuple(values[name] for name in names),
    )
    row = db.execute(
        f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE fence_id=?", (fence_id,),
    ).fetchone()
    if (
        cursor.rowcount != 1 or row is None or not exact_issued(row, binding)
        or any(row[key] != val for key, val in values.items())
    ):
        raise sqlite3.IntegrityError("effect fence insert exact postread disagrees")
    return fence_id


def reissue(
    db: sqlite3.Connection, row: sqlite3.Row, binding: EffectBinding,
    issued: datetime, expires: datetime, token_sha: str, warrant_sha: str,
) -> bool:
    try:
        prior = row_binding(row)
        immutable = (
            prior.canary == binding.canary and prior.owner_stores == binding.owner_stores
            and prior.independent_verification_sha256
            == binding.independent_verification_sha256
            and prior.foundry_canary_evidence_sha256
            == binding.foundry_canary_evidence_sha256
            and prior.foundry_process_receipt_sha256
            == binding.foundry_process_receipt_sha256
            and prior.vibe_process_receipt_sha256 == binding.vibe_process_receipt_sha256
            and prior.vibe_patch_receipt_sha256 == binding.vibe_patch_receipt_sha256
        )
        if (
            not exact_issued(row, prior)
            or _time(row["warrant_expires_at"]) > issued or not immutable
        ):
            return False
        updates = {
            "supervisor_authority_sha256": binding.supervisor_authority_sha256,
            "binding_sha256": binding.binding_sha256,
            "effect_binding_json": canonical_json(binding.to_dict()),
            "warrant_issued_at": issued.isoformat(),
            "warrant_expires_at": expires.isoformat(),
            "warrant_token_sha256": token_sha, "warrant_sha256": warrant_sha,
        }
        assignments = ",".join(f"{name}=?" for name in updates)
        cursor = db.execute(
            f"UPDATE {EFFECT_FENCE_TABLE} SET {assignments} WHERE fence_id=?"
            " AND state='issued' AND binding_sha256=? AND warrant_expires_at=?"
            " AND terminal_record_json IS NULL",
            (*updates.values(), row["fence_id"], row["binding_sha256"],
             row["warrant_expires_at"]),
        )
        post = db.execute(
            f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE fence_id=?", (row["fence_id"],),
        ).fetchone()
        return bool(
            cursor.rowcount == 1 and post is not None and exact_issued(post, binding)
            and all(post[key] == val for key, val in updates.items())
        )
    except (ValueError, TypeError, sqlite3.Error):
        return False


def collision(db: sqlite3.Connection, effect_key: str, receipt_id: str, idem: str) -> bool:
    receipts = db.execute(
        "SELECT 1 FROM runtime_receipts WHERE receipt_id=? OR side_effect_key=?"
        " OR idempotency_key=? LIMIT 1", (receipt_id, effect_key, idem),
    ).fetchone()
    idempotency = db.execute(
        "SELECT 1 FROM idempotency_records WHERE side_effect_key=?"
        " OR idempotency_key=? OR result_receipt_id=? LIMIT 1",
        (effect_key, idem, receipt_id),
    ).fetchone()
    return receipts is not None or idempotency is not None


def quarantine(db: sqlite3.Connection, row: sqlite3.Row, reason: str, observed: str) -> None:
    when = _now().isoformat()
    cursor = db.execute(
        f"UPDATE {EFFECT_FENCE_TABLE} SET state='quarantined',quarantine_reason=?,"
        " observed_sha256=?,quarantined_at=?,warrant_token_sha256=''"
        " WHERE fence_id=? AND state='issued' AND binding_sha256=?",
        (reason, observed, when, row["fence_id"], row["binding_sha256"]),
    )
    post = db.execute(
        f"SELECT state,quarantine_reason,observed_sha256,quarantined_at,"
        f"warrant_token_sha256 FROM {EFFECT_FENCE_TABLE} WHERE fence_id=?",
        (row["fence_id"],),
    ).fetchone()
    if cursor.rowcount != 1 or post is None or tuple(post) != (
        "quarantined", reason, observed, when, "",
    ):
        raise sqlite3.IntegrityError("effect quarantine CAS lost its slot")


__all__ = [
    "collision", "exact_issued", "fence_id_for", "insert_issued", "quarantine",
    "reissue", "row_binding",
]
