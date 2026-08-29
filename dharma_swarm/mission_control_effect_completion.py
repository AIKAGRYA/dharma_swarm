from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.mission_control_a2a_owner_snapshot import one_owner_row, owner_object, owner_text, owner_time
from dharma_swarm.mission_control_contract import GOVERNED_PATCH_COMPLETION_CONTRACT, GOVERNED_PATCH_COMPLETION_METADATA_FIELDS, GOVERNED_PATCH_COMPLETION_PROOF_SCHEMA, GOVERNED_PATCH_COMPLETION_RESULT, OPEN_CLAIM_STATUSES, RECOVERY_RECEIPT_TYPE, SCHEMA_VERSION, TERMINAL_RECEIPT_TYPE, MissionControlError, ReceiptView, completion_contract_from_metadata, session_id, stable_id, terminal_operation_metadata
from dharma_swarm.mission_control_effect_codec import canonical_json, terminal_from_json
from dharma_swarm.mission_control_effect_fence_store import row_binding
from dharma_swarm.mission_control_effect_owner import (
    inspect_owner_stores,
    owner_transaction,
)
from dharma_swarm.mission_control_effect_owner_graph import (
    validate_observed_effect_owner_triples,
)
from dharma_swarm.mission_control_effect_records import OwnerStoreBinding
from dharma_swarm.mission_control_effect_terminal_store import existing_terminal
from dharma_swarm.mission_control_lifecycle import _serialized_task
from dharma_swarm.mission_control_projection import receipt_view
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.runtime_state_effect_fence import EFFECT_FENCE_TABLE, EFFECT_RECEIPT_TYPE
from dharma_swarm.spine.identity import ExecutionIdentity

def validate_governed_patch_terminal_proof(
    receipt: RuntimeReceipt, identity: ExecutionIdentity, mission_id: str,
    supporting_receipts: Sequence[RuntimeReceipt],
) -> None:
    payload = receipt.payload
    metadata = payload.get("metadata")
    if (
        receipt.status != "succeeded"
        or payload.get("result") != GOVERNED_PATCH_COMPLETION_RESULT
        or payload.get("failure_code") != ""
        or set(payload)
        != {
            "schema_version", "mission_id", "attempt_id", "result",
            "failure_code", "metadata",
        }
        or type(metadata) is not dict
        or set(metadata) != GOVERNED_PATCH_COMPLETION_METADATA_FIELDS
        or metadata.get("schema_version") != SCHEMA_VERSION
        or metadata.get("mission_id") != mission_id
        or metadata.get("attempt_id") != identity.run_id
        or metadata.get("attempt_key") != identity.idempotency_key
        or metadata.get("completion_contract")
        != GOVERNED_PATCH_COMPLETION_CONTRACT
        or metadata.get("proof_schema") != GOVERNED_PATCH_COMPLETION_PROOF_SCHEMA
    ):
        raise MissionControlError(
            f"attempt {identity.run_id!r} has conflicting governed terminal proof"
        )
    supporting = [item for item in supporting_receipts if item.receipt_type == EFFECT_RECEIPT_TYPE]
    if len(supporting) != 1:
        raise MissionControlError(
            f"attempt {identity.run_id!r} lacks one exact supporting effect receipt"
        )
    effect_receipt = supporting[0]
    try:
        terminal = terminal_from_json(canonical_json(effect_receipt.payload))
    except (TypeError, ValueError) as exc:
        raise MissionControlError(
            f"attempt {identity.run_id!r} has malformed supporting effect evidence"
        ) from exc
    expected = completion_proof_metadata(identity, mission_id, terminal)
    if (
        metadata != expected
        or effect_receipt.receipt_id != terminal.terminal_receipt_id
        or effect_receipt.run_id != identity.run_id
        or effect_receipt.task_id != identity.task_id
        or effect_receipt.trace_id != ""
        or not effect_receipt.correlation_id
        or not effect_receipt.causation_id
        or not effect_receipt.parent_run_id
        or effect_receipt.agent_id != terminal.claimed_by
        or effect_receipt.idempotency_key != "idem_" + terminal.terminal_receipt_id
        or effect_receipt.side_effect_key != terminal.effect_key
        or effect_receipt.status != "consumed"
        or effect_receipt.payload != terminal.to_dict()
        or effect_receipt.created_at != terminal.consumed_at
        or effect_receipt.created_at > receipt.created_at
    ):
        raise MissionControlError(
            f"attempt {identity.run_id!r} has conflicting supporting effect evidence"
        )


def completion_proof_metadata(identity: ExecutionIdentity, mission_id: str, terminal: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "attempt_id": identity.run_id,
        "attempt_key": identity.idempotency_key,
        "completion_contract": GOVERNED_PATCH_COMPLETION_CONTRACT,
        "proof_schema": GOVERNED_PATCH_COMPLETION_PROOF_SCHEMA,
        "effect_key": terminal.effect_key,
        "effect_terminal_id": terminal.terminal_id,
        "effect_terminal_receipt_id": terminal.terminal_receipt_id,
        "effect_terminal_receipt_sha256": terminal.terminal_receipt_sha256,
        "effect_fence_id": terminal.fence_id,
        "effect_binding_sha256": terminal.binding_sha256,
        "candidate_bundle_sha256": terminal.candidate_bundle_sha256,
        "diff_sha256": terminal.diff_sha256,
        "base_sha": terminal.base_sha,
        "postimage_sha256": terminal.postimage_sha256,
    }


def _identity(row: sqlite3.Row) -> ExecutionIdentity:
    metadata = owner_object(row["metadata_json"], "parent execution identity")
    return ExecutionIdentity(
        **{
            name: owner_text(row, name)
            for name in (
                "trace_id", "correlation_id", "task_id", "run_id", "claim_id", "idempotency_key", "causation_id", "parent_run_id", "agent_id",
                "session_id", "external_a2a_task_id", "message_id", "event_id", "artifact_id", "proposal_id",
            )
        },
        metadata=metadata,
    )


def _runtime_receipt(row: sqlite3.Row) -> RuntimeReceipt:
    return RuntimeReceipt(
        **{name: owner_text(row, name) for name in (
            "receipt_id", "receipt_type", "status", "run_id", "task_id", "trace_id",
            "correlation_id", "causation_id", "parent_run_id", "agent_id",
            "idempotency_key", "side_effect_key",
        )},
        payload=owner_object(row["payload_json"], "runtime receipt"),
        created_at=owner_time(row, "created_at"),
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _require_promotion_claim(
    db: sqlite3.Connection, run: sqlite3.Row, claim: sqlite3.Row, task_id: str,
    now: datetime,
    *, _recovery_only: bool,
) -> datetime:
    if type(_recovery_only) is not bool or any(
        claim[name] is None for name in ("acked_at", "heartbeat_at", "stale_after")
    ):
        raise MissionControlError("governed completion claim timeline is incomplete")
    claimed_at = owner_time(claim, "claimed_at")
    acked_at = owner_time(claim, "acked_at")
    heartbeat_at = owner_time(claim, "heartbeat_at")
    stale_after = owner_time(claim, "stale_after")
    valid_window = stale_after <= now if _recovery_only else now < stale_after
    if (
        owner_text(claim, "status") != "active" or claim["recovered_at"] is not None
        or not claimed_at <= acked_at <= heartbeat_at <= stale_after
        or not heartbeat_at <= now or not valid_window
    ):
        state = "expired active" if _recovery_only else "fresh active"
        raise MissionControlError(f"governed completion requires an exact {state} claim")
    others = db.execute(
        "SELECT * FROM task_claims WHERE task_id=? AND claim_id<>? LIMIT 10001",
        (task_id, owner_text(claim, "claim_id")),
    ).fetchall()
    if len(others) > 10_000:
        raise MissionControlError("claim fence scan saturated")
    if others:
        raise MissionControlError("governed completion claim is not unique")
    runs = db.execute(
        "SELECT * FROM delegation_runs WHERE task_id=? AND run_id<>? LIMIT 10001",
        (task_id, owner_text(run, "run_id")),
    ).fetchall()
    if len(runs) > 10_000:
        raise MissionControlError("delegation run fence scan saturated")
    if runs:
        raise MissionControlError("governed completion run was superseded")
    return stale_after


def _terminal_rows(
    db: sqlite3.Connection, identity: ExecutionIdentity, receipt_id: str,
    side_effect_key: str,
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    receipts = db.execute(
        "SELECT * FROM runtime_receipts WHERE (run_id=? AND receipt_type IN (?,?))"
        " OR side_effect_key=? OR receipt_id=? LIMIT 4",
        (identity.run_id, TERMINAL_RECEIPT_TYPE, RECOVERY_RECEIPT_TYPE,
         side_effect_key, receipt_id),
    ).fetchall()
    idempotency = db.execute(
        "SELECT * FROM idempotency_records WHERE side_effect_key=?"
        " OR result_receipt_id=? OR (idempotency_key=? AND side_effect_key=?) LIMIT 4",
        (side_effect_key, receipt_id, identity.idempotency_key, side_effect_key),
    ).fetchall()
    if len(receipts) > 1 or len(idempotency) > 1:
        raise MissionControlError("conflicting terminal or idempotency evidence")
    return receipts, idempotency


def _exact_replay(
    receipts: list[sqlite3.Row], idempotency: list[sqlite3.Row],
    expected: RuntimeReceipt, idempotency_metadata: dict[str, Any],
) -> RuntimeReceipt | None:
    if not receipts and not idempotency:
        return None
    if len(receipts) != 1 or len(idempotency) != 1:
        raise MissionControlError("partial terminal evidence is not replayable")
    receipt = _runtime_receipt(receipts[0])
    idem = idempotency[0]
    if (
        receipt != expected
        or owner_text(idem, "idempotency_key") != expected.idempotency_key
        or owner_text(idem, "side_effect_key") != expected.side_effect_key
        or owner_text(idem, "run_id") != expected.run_id
        or owner_text(idem, "task_id") != expected.task_id
        or owner_text(idem, "trace_id") != expected.trace_id
        or owner_text(idem, "correlation_id") != expected.correlation_id
        or owner_text(idem, "status") != "completed"
        or owner_text(idem, "result_receipt_id") != expected.receipt_id
        or owner_object(idem["metadata_json"], "terminal idempotency")
        != idempotency_metadata
        or owner_time(idem, "created_at") != expected.created_at
        or owner_time(idem, "updated_at") != expected.created_at
    ):
        raise MissionControlError("existing terminal evidence conflicts with proof")
    return receipt


class MissionControlEffectCompletionMixin:
    def _effect_readback_owner_stores(
        self, snapshot_owners: OwnerStoreBinding
    ) -> OwnerStoreBinding:
        source_owners = getattr(self, "_immutable_snapshot_source_owners", None)
        if source_owners is None:
            return snapshot_owners
        if type(source_owners) is not OwnerStoreBinding:
            raise MissionControlError("immutable snapshot source identity is malformed")
        try:
            current = inspect_owner_stores(
                Path(source_owners.runtime_database_path),
                Path(source_owners.task_database_path),
            )
        except (OSError, ValueError) as exc:
            raise MissionControlError(
                "immutable snapshot source identity is unavailable"
            ) from exc
        if current != source_owners:
            raise MissionControlError("immutable snapshot source identity drifted")
        return source_owners

    def _validate_observed_patch_effect_receipts_sync(
        self, receipts: Sequence[RuntimeReceipt]
    ) -> None:
        snapshot_owners = inspect_owner_stores(
            Path(self._runtime.db_path), Path(self._board._db_path)
        )
        expected_owners = self._effect_readback_owner_stores(snapshot_owners)
        with owner_transaction(snapshot_owners, read_only=True) as db:
            validate_observed_effect_owner_triples(
                db, receipts, expected_owner_stores=expected_owners
            )
            db.rollback()

    async def _validate_observed_patch_effect_receipts(
        self, receipts: Sequence[RuntimeReceipt]
    ) -> None:
        if receipts:
            await asyncio.to_thread(
                self._validate_observed_patch_effect_receipts_sync, tuple(receipts)
            )

    def _validate_patch_effect_completion_readback_sync(
        self,
        receipt: RuntimeReceipt,
        *,
        mission_id: str,
        task_id: str,
        agent_id: str,
        attempt_id: str,
        effect_key: str,
    ) -> None:
        """Rejoin a promoted parent receipt to its exact effect owners."""

        snapshot_owners = inspect_owner_stores(
            Path(self._runtime.db_path), Path(self._board._db_path)
        )
        expected_owners = self._effect_readback_owner_stores(snapshot_owners)
        with owner_transaction(snapshot_owners, read_only=True) as db:
            rows = db.execute(
                "SELECT * FROM runtime_receipts WHERE receipt_id=?"
                " AND run_id=? AND receipt_type=? LIMIT 2",
                (receipt.receipt_id, attempt_id, TERMINAL_RECEIPT_TYPE),
            ).fetchall()
            if len(rows) != 1 or _runtime_receipt(rows[0]) != receipt:
                raise MissionControlError(
                    "promoted parent receipt disappeared during owner readback"
                )
            validated = self._promote_patch_effect(
                db,
                snapshot_owners,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                attempt_id=attempt_id,
                effect_key=effect_key,
                expected_owner_stores=expected_owners,
            )
            if validated != receipt:
                raise MissionControlError("promoted parent proof readback disagrees")
            db.rollback()

    async def _validate_patch_effect_completion_readback(
        self,
        receipt: RuntimeReceipt,
        *,
        mission_id: str,
        task_id: str,
        agent_id: str,
        attempt_id: str,
        effect_key: str,
    ) -> None:
        await asyncio.to_thread(
            self._validate_patch_effect_completion_readback_sync,
            receipt,
            mission_id=mission_id,
            task_id=task_id,
            agent_id=agent_id,
            attempt_id=attempt_id,
            effect_key=effect_key,
        )

    @_serialized_task
    async def finish_attempt_from_patch_effect(
        self,
        mission_id: str, task_id: str, agent_id: str, *, attempt_id: str,
        effect_key: str,
    ) -> ReceiptView:
        return await self._finish_attempt_from_patch_effect(
            mission_id, task_id, agent_id, attempt_id=attempt_id,
            effect_key=effect_key, _recovery_only=False,
        )

    async def _recover_attempt_from_patch_effect(
        self, mission_id: str, task_id: str, agent_id: str, *, attempt_id: str,
        effect_key: str,
    ) -> ReceiptView:
        return await self._finish_attempt_from_patch_effect(
            mission_id, task_id, agent_id, attempt_id=attempt_id,
            effect_key=effect_key, _recovery_only=True,
        )

    async def _finish_attempt_from_patch_effect(
        self, mission_id: str, task_id: str, agent_id: str, *, attempt_id: str,
        effect_key: str, _recovery_only: bool,
    ) -> ReceiptView:
        from dharma_swarm.mission_control_contract import clean_identifier
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        agent_id = clean_identifier(agent_id, "agent_id")
        attempt_id = clean_identifier(attempt_id, "attempt_id")
        effect_key = clean_identifier(effect_key, "effect_key")
        await self._require_task(mission_id, task_id)
        await self._resolve_attempt(
            mission_id, task_id, agent_id, attempt_id=attempt_id
        )
        try:
            receipt = await asyncio.to_thread(
                self._commit_patch_effect_promotion,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                attempt_id=attempt_id,
                effect_key=effect_key,
                _recovery_only=_recovery_only,
            )
        except MissionControlError:
            raise
        except (KeyError, OSError, RuntimeError, sqlite3.Error, TypeError, ValueError) as exc:
            raise MissionControlError("governed patch completion refused") from exc
        task = await self._require_task(mission_id, task_id)
        run = await self._runtime.get_delegation_run(attempt_id)
        identity = await self._runtime.get_execution_identity(attempt_id)
        if run is None or identity is None:
            raise MissionControlError("committed governed completion lineage disappeared")
        claim = await self._runtime.get_task_claim(run.claim_id)
        if claim is None:
            raise MissionControlError("committed governed completion claim disappeared")
        await self._project_terminal_lineage(
            mission_id,
            task=task,
            run=run,
            claim=claim,
            identity=identity,
            receipt=receipt,
        )
        return receipt_view(receipt, mission_id)

    def _commit_patch_effect_promotion(
        self,
        *,
        mission_id: str,
        task_id: str,
        agent_id: str,
        attempt_id: str,
        effect_key: str,
        _recovery_only: bool,
    ) -> RuntimeReceipt:
        owners = inspect_owner_stores(
            Path(self._runtime.db_path), Path(self._board._db_path)
        )
        with owner_transaction(owners) as db:
            receipt = self._promote_patch_effect(
                db,
                owners,
                mission_id=mission_id,
                task_id=task_id,
                agent_id=agent_id,
                attempt_id=attempt_id,
                effect_key=effect_key,
                _recovery_only=_recovery_only,
            )
            db.commit()
            return receipt

    def _promote_patch_effect(
        self,
        db: sqlite3.Connection,
        owners: Any,
        *,
        mission_id: str,
        task_id: str,
        agent_id: str,
        attempt_id: str,
        effect_key: str,
        _recovery_only: bool = False,
        expected_owner_stores: OwnerStoreBinding | None = None,
    ) -> RuntimeReceipt:
        task = one_owner_row(
            db, "SELECT * FROM taskboard.tasks WHERE id=? LIMIT 2", (task_id,), "task"
        )
        run = one_owner_row(
            db, "SELECT * FROM delegation_runs WHERE run_id=? LIMIT 2", (attempt_id,), "run"
        )
        claim_id = owner_text(run, "claim_id")
        claim = one_owner_row(
            db, "SELECT * FROM task_claims WHERE claim_id=? LIMIT 2", (claim_id,), "claim"
        )
        identity_row = one_owner_row(
            db,
            "SELECT * FROM execution_identities WHERE run_id=? LIMIT 2",
            (attempt_id,),
            "parent identity",
        )
        identity = _identity(identity_row)
        task_metadata = owner_object(task["metadata"], "task")
        run_metadata = owner_object(run["metadata_json"], "run")
        claim_metadata = owner_object(claim["metadata_json"], "claim")
        if any(
            completion_contract_from_metadata(item)
            != GOVERNED_PATCH_COMPLETION_CONTRACT
            for item in (task_metadata, run_metadata, claim_metadata, identity.metadata)
        ):
            raise MissionControlError("governed completion lineage contract is absent")
        self._require_identity(identity, mission_id, task_id, agent_id, attempt_id)
        if (
            owner_text(task, "assigned_to") != agent_id
            or task_metadata.get("schema_version") != SCHEMA_VERSION
            or task_metadata.get("mission_id") != mission_id
            or task_metadata.get("mission_attempt_id") != attempt_id
            or task_metadata.get("mission_claim_id") != claim_id
            or owner_text(run, "session_id") != session_id(mission_id)
            or owner_text(run, "task_id") != task_id
            or owner_text(run, "assigned_to") != agent_id
            or run_metadata.get("schema_version") != SCHEMA_VERSION
            or run_metadata.get("mission_id") != mission_id
            or owner_text(claim, "session_id") != session_id(mission_id)
            or owner_text(claim, "task_id") != task_id
            or owner_text(claim, "agent_id") != agent_id
            or claim_metadata.get("schema_version") != SCHEMA_VERSION
            or claim_metadata.get("mission_id") != mission_id
            or claim_metadata.get("attempt_id") != attempt_id
            or identity.metadata
            != {
                "schema_version": SCHEMA_VERSION,
                "mission_id": mission_id,
                "completion_contract": GOVERNED_PATCH_COMPLETION_CONTRACT,
            }
            or identity.claim_id != claim_id
            or run_metadata.get("attempt_key") != identity.idempotency_key
            or claim_metadata.get("attempt_key") != identity.idempotency_key
            or identity.trace_id != stable_id("trace", attempt_id)
            or identity.correlation_id != f"mission:{mission_id}:attempt:{attempt_id}"
            or not identity.idempotency_key
            or any((identity.causation_id, identity.parent_run_id,
                    identity.external_a2a_task_id, identity.message_id, identity.event_id,
                    identity.artifact_id, identity.proposal_id))
            or owner_text(identity_row, "source") != "mission_control.start_attempt"
        ):
            raise MissionControlError("governed completion lineage binding disagrees")
        fence_rows = db.execute(
            f"SELECT * FROM {EFFECT_FENCE_TABLE} WHERE effect_key=?"
            " OR mission_attempt_id=? OR mission_claim_id=? LIMIT 4",
            (effect_key, attempt_id, claim_id),
        ).fetchall()
        if len(fence_rows) != 1:
            raise MissionControlError("one exact consumed effect fence is required")
        fence = fence_rows[0]
        terminal = existing_terminal(db, fence)
        effect_binding = row_binding(fence)
        canary = effect_binding.canary
        if (
            effect_binding.owner_stores
            != (
                owners
                if expected_owner_stores is None
                else expected_owner_stores
            )
            or terminal.effect_key != effect_key
            or canary.mission_id != mission_id
            or canary.task_id != task_id
            or canary.mission_attempt_id != attempt_id
            or canary.mission_claim_id != claim_id
            or canary.executor_agent_uid != agent_id
            or canary.attempt_key != identity.idempotency_key
            or canary.assigned_by != owner_text(run, "assigned_by")
        ):
            raise MissionControlError("consumed effect does not bind canonical lineage")
        effect_receipt = RuntimeReceipt(
            terminal.terminal_receipt_id, EFFECT_RECEIPT_TYPE, "consumed", attempt_id,
            task_id, "", canary.correlation_id, canary.proposal_receipt_id,
            canary.executor_run_id, terminal.claimed_by,
            "idem_" + terminal.terminal_receipt_id, effect_key, terminal.to_dict(),
            terminal.consumed_at,
        )
        effect_rows = db.execute(
            "SELECT * FROM runtime_receipts WHERE run_id=? AND receipt_type=? LIMIT 2",
            (attempt_id, EFFECT_RECEIPT_TYPE),
        ).fetchall()
        if len(effect_rows) != 1 or _runtime_receipt(effect_rows[0]) != effect_receipt:
            raise MissionControlError("one exact run-scoped effect receipt is required")
        metadata = completion_proof_metadata(identity, mission_id, terminal)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": attempt_id,
            "result": GOVERNED_PATCH_COMPLETION_RESULT,
            "failure_code": "",
            "metadata": metadata,
        }
        receipt_id = stable_id("receipt", attempt_id, "succeeded")
        side_effect_key = f"mission_control:{attempt_id}:terminal"
        rows, idem = _terminal_rows(db, identity, receipt_id, side_effect_key)
        created_at = (
            owner_time(rows[0], "created_at")
            if rows
            else max(datetime.now(timezone.utc), terminal.consumed_at)
        )
        if terminal.consumed_at > created_at:
            raise MissionControlError(
                "parent terminal cannot predate its supporting effect"
            )
        receipt = RuntimeReceipt(
            receipt_id, TERMINAL_RECEIPT_TYPE, "succeeded", identity.run_id,
            identity.task_id, identity.trace_id, identity.correlation_id,
            identity.causation_id, identity.parent_run_id, identity.agent_id,
            identity.idempotency_key, side_effect_key, payload, created_at,
        )
        _, idem_metadata = terminal_operation_metadata(receipt, identity, mission_id)
        replay = _exact_replay(rows, idem, receipt, idem_metadata)
        if replay is not None:
            claim_status = owner_text(claim, "status").lower()
            if (
                owner_text(run, "status") != "completed"
                or run["completed_at"] is None
                or owner_time(run, "completed_at") != created_at
                or owner_text(run, "failure_code") != ""
                or any(run_metadata.get(key) != value for key, value in metadata.items())
                or (
                    claim_status not in OPEN_CLAIM_STATUSES
                    and (
                        claim_status != "completed"
                        or any(
                            claim_metadata.get(key) != value
                            for key, value in metadata.items()
                        )
                    )
                )
            ):
                raise MissionControlError("terminal replay lacks completed owner CAS")
            return replay
        if owner_text(run, "status") != "running" or run["completed_at"] is not None:
            raise MissionControlError("governed completion requires a running attempt")
        if owner_text(task, "status") != "running":
            raise MissionControlError("governed completion requires RUNNING task owner")
        stale_after = _require_promotion_claim(
            db, run, claim, task_id, created_at, _recovery_only=_recovery_only
        )
        if _recovery_only and not (
            (not terminal.recovery_finalized and terminal.consumed_at < stale_after)
            or (
                terminal.recovery_finalized
                and terminal.recovery_owner_basis == "expired_active"
            )
        ):
            raise MissionControlError("effect lacks exact expired-active recovery proof")
        receipt_values = (
            receipt.receipt_id, receipt.receipt_type, receipt.run_id, receipt.task_id,
            receipt.trace_id, receipt.correlation_id, receipt.causation_id,
            receipt.parent_run_id, receipt.agent_id, receipt.idempotency_key,
            receipt.side_effect_key, receipt.status, _json(payload), created_at.isoformat(),
        )
        db.execute(
            "INSERT OR ABORT INTO runtime_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            receipt_values,
        )
        db.execute(
            "INSERT OR ABORT INTO idempotency_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                identity.idempotency_key, side_effect_key, attempt_id, task_id,
                identity.trace_id, identity.correlation_id, "completed", receipt_id,
                _json(idem_metadata), created_at.isoformat(), created_at.isoformat(),
            ),
        )
        completed_metadata = {**run_metadata, **metadata}
        cursor = db.execute(
            "UPDATE delegation_runs SET status='completed',completed_at=?,failure_code='',"
            "metadata_json=? WHERE run_id=? AND status='running' AND completed_at IS NULL",
            (created_at.isoformat(), _json(completed_metadata), attempt_id),
        )
        if cursor.rowcount != 1:
            raise MissionControlError("governed completion owner CAS was lost")
        post_rows, post_idem = _terminal_rows(db, identity, receipt_id, side_effect_key)
        _exact_replay(post_rows, post_idem, receipt, idem_metadata)
        post_run = one_owner_row(
            db, "SELECT * FROM delegation_runs WHERE run_id=? LIMIT 2", (attempt_id,), "run"
        )
        if (
            owner_text(post_run, "status") != "completed"
            or owner_time(post_run, "completed_at") != created_at
            or owner_object(post_run["metadata_json"], "completed run")
            != completed_metadata
        ):
            raise MissionControlError("governed completion postread disagrees")
        return receipt


__all__ = ["MissionControlEffectCompletionMixin", "completion_proof_metadata", "validate_governed_patch_terminal_proof"]
