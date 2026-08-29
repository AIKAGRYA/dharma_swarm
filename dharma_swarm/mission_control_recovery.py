"""Terminal attempt completion and stale-lineage recovery mechanics."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_contract import (
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    PUBLIC_TERMINAL_ATTEMPT_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_CAS_STALE_AFTER_SECONDS,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    ReceiptView,
    claim_is_expired,
    clean_identifier,
    completion_contract_from_metadata,
    require_same_completion_contract,
    stable_id,
    terminal_operation_metadata,
    terminal_receipt_contract,
    utc_now,
)
from dharma_swarm.mission_control_lifecycle import _serialized_task
from dharma_swarm.mission_control_effect_owner import inspect_owner_stores, owner_transaction
from dharma_swarm.mission_control_projection import receipt_view
from dharma_swarm.mission_control_recovery_cas import recover_stale_lineage_cas
from dharma_swarm.models import Task
from dharma_swarm.runtime_state import DelegationRun, RuntimeReceipt, TaskClaim
from dharma_swarm.runtime_state_effect_fence import EFFECT_RECEIPT_TYPE
from dharma_swarm.spine.identity import ExecutionIdentity


def _recover_stale_lineage_in_owner_transaction(
    runtime_database: Path,
    task_database: Path,
    *,
    mission_id: str,
    task: Task,
    run: DelegationRun,
    claim: TaskClaim,
    identity: ExecutionIdentity,
    receipt: RuntimeReceipt,
    recovered_at: datetime,
) -> RuntimeReceipt:
    """Commit one exact stale recovery without occupying the event loop."""

    owners = inspect_owner_stores(runtime_database, task_database)
    with owner_transaction(owners) as database:
        result = recover_stale_lineage_cas(
            database,
            mission_id=mission_id,
            task=task,
            run=run,
            claim=claim,
            identity=identity,
            receipt=receipt,
            recovered_at=recovered_at,
        )
        database.commit()
        return result


class MissionControlRecoveryMixin:
    """Finalize attempts and converge interrupted terminal transitions."""

    _runtime: Any

    @_serialized_task
    async def finish_attempt(
        self,
        mission_id: str,
        task_id: str,
        agent_id: str,
        *,
        attempt_id: str = "",
        status: str,
        result: str = "",
        failure_code: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReceiptView:
        mission_id = clean_identifier(mission_id, "mission_id")
        task_id = clean_identifier(task_id, "task_id")
        agent_id = clean_identifier(agent_id, "agent_id")
        terminal_status = str(status or "").strip().lower()
        if terminal_status not in PUBLIC_TERMINAL_ATTEMPT_STATUSES:
            raise MissionControlError("status must be 'succeeded' or 'failed'")
        run = await self._resolve_attempt(
            mission_id, task_id, agent_id, attempt_id=attempt_id
        )
        task = await self._require_task(mission_id, task_id)
        identity = await self._runtime.get_execution_identity(run.run_id)
        if identity is None:
            raise MissionControlError(
                f"execution identity for attempt {run.run_id!r} was not found"
            )
        self._require_identity(identity, mission_id, task_id, agent_id, run.run_id)
        if identity.claim_id != run.claim_id:
            raise MissionControlError(
                f"execution identity for {run.run_id!r} has foreign fields"
            )
        claim = await self._runtime.get_task_claim(run.claim_id)
        if claim is None:
            raise MissionControlError(f"claim {run.claim_id!r} was not found")
        self._require_claim_identity(claim, mission_id, task_id, agent_id, run.run_id)
        completion_contract = require_same_completion_contract(
            task.metadata,
            run.metadata,
            claim.metadata,
            identity.metadata,
        )
        requested_contract = completion_contract_from_metadata(dict(metadata or {}))
        if completion_contract or requested_contract:
            raise MissionControlError(
                "governed completion requires finish_attempt_from_patch_effect"
            )
        attempt_key = str(run.metadata.get("attempt_key") or identity.idempotency_key)
        owner_terminal_status = (
            "completed" if terminal_status == "succeeded" else "failed"
        )
        safe_metadata = self._attempt_metadata(
            metadata,
            mission_id=mission_id,
            attempt_id=run.run_id,
            attempt_key=attempt_key,
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": run.run_id,
            "result": str(result or ""),
            "failure_code": str(failure_code or ""),
            "metadata": safe_metadata,
        }
        receipt_id = stable_id("receipt", run.run_id, terminal_status)
        side_effect_key = f"mission_control:{run.run_id}:terminal"
        operation = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": run.run_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "status": terminal_status,
            "receipt_id": receipt_id,
            "payload": payload,
        }
        operation_hash = hashlib.sha256(
            json.dumps(
                operation,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        idempotency_metadata = {
            "operation_hash": operation_hash,
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": run.run_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "terminal_status": terminal_status,
        }
        existing_receipts = await self._runtime.list_runtime_receipts(
            run_id=run.run_id,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            limit=100,
        )
        receipt = self._matching_terminal_receipt(
            existing_receipts,
            identity=identity,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status=terminal_status,
            payload=payload,
        )
        claims = await self._claims_for_fencing(task_id)
        self._require_current_claim(
            claim,
            claims,
            now=utc_now(),
            require_active=receipt is None,
        )
        if (
            run.status in OWNER_TERMINAL_ATTEMPT_STATUSES
            and run.status != owner_terminal_status
        ):
            raise MissionControlError(
                f"attempt {run.run_id!r} already has conflicting terminal evidence"
            )
        if receipt is None and run.status != "running":
            raise MissionControlError(
                f"attempt {run.run_id!r} has not been acknowledged as running"
            )

        try:
            ownership_token = (
                await self._runtime.try_begin_idempotent_side_effect_with_token(
                    identity,
                    side_effect_key,
                    metadata=idempotency_metadata,
                    stale_after_seconds=TERMINAL_CAS_STALE_AFTER_SECONDS,
                )
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            raise MissionControlError(
                f"attempt {run.run_id!r} already has conflicting terminal evidence"
            ) from exc

        # Re-read after the compare-and-set. A duplicate can repair projections,
        # but only the holder of the ownership token may create terminal evidence.
        existing_receipts = await self._runtime.list_runtime_receipts(
            run_id=run.run_id,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            limit=100,
        )
        receipt = self._matching_terminal_receipt(
            existing_receipts,
            identity=identity,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status=terminal_status,
            payload=payload,
        )
        ownership_token, ownership_complete = await self._recover_terminal_ownership(
            identity,
            side_effect_key=side_effect_key,
            operation_hash=operation_hash,
            receipt=receipt,
            receipt_id=receipt_id,
            ownership_token=ownership_token,
        )
        if receipt is None:
            receipt = await self._runtime.record_receipt_for_identity(
                identity,
                receipt_type=TERMINAL_RECEIPT_TYPE,
                status=terminal_status,
                side_effect_key=side_effect_key,
                payload=payload,
                receipt_id=receipt_id,
            )
        if not ownership_complete:
            try:
                await self._runtime.complete_idempotent_side_effect(
                    identity,
                    side_effect_key,
                    status="completed",
                    result_receipt_id=receipt.receipt_id,
                    metadata=idempotency_metadata,
                    expected_updated_at=ownership_token,
                )
            except (KeyError, RuntimeError, ValueError) as exc:
                raise MissionControlError(
                    f"terminal ownership for attempt {run.run_id!r} was lost"
                ) from exc
        await self._project_terminal_lineage(
            mission_id,
            task=task,
            run=run,
            claim=claim,
            identity=identity,
            receipt=receipt,
        )
        return receipt_view(receipt, mission_id)

    async def _recover_expired_claim(
        self,
        mission_id: str,
        claim: TaskClaim,
        *,
        recovered_at: datetime,
    ) -> bool:
        """Close an expired lineage through the canonical owner-store CAS."""
        current_claim = await self._runtime.get_task_claim(claim.claim_id)
        if current_claim is None:
            raise MissionControlError(f"claim {claim.claim_id!r} was not found")
        claim = current_claim
        trusted_now = utc_now()
        if (
            claim.status.lower() not in OPEN_CLAIM_STATUSES
            or not claim_is_expired(claim, trusted_now)
            or claim.stale_after is None
        ):
            raise MissionControlError(
                f"claim {claim.claim_id!r} is not an expired open lineage"
            )
        expired_stale_after = claim.stale_after
        attempt_id = str(claim.metadata.get("attempt_id") or "")
        self._require_claim_identity(
            claim, mission_id, claim.task_id, claim.agent_id, attempt_id
        )
        identity = await self._runtime.get_execution_identity(attempt_id)
        if identity is None:
            raise MissionControlError(
                f"execution identity for attempt {attempt_id!r} was not found"
            )
        self._require_identity(
            identity, mission_id, claim.task_id, claim.agent_id, attempt_id
        )
        if identity.claim_id != claim.claim_id:
            raise MissionControlError(
                f"execution identity for {attempt_id!r} has foreign fields"
            )
        run = await self._runtime.get_delegation_run(attempt_id)
        if run is None:
            raise MissionControlError(
                f"expired claim {claim.claim_id!r} has no associated attempt run"
            )
        self._require_attempt_identity(run, mission_id, claim.task_id, claim.agent_id)
        if run.claim_id != claim.claim_id:
            raise MissionControlError(f"attempt {attempt_id!r} has foreign identity")
        task = await self._require_task(mission_id, claim.task_id)
        require_same_completion_contract(
            task.metadata, run.metadata, claim.metadata, identity.metadata
        )

        terminal_receipts = await self._runtime.list_runtime_receipts(
            run_id=attempt_id,
            receipt_type=TERMINAL_RECEIPT_TYPE,
            limit=2,
        )
        recovery_receipts = await self._runtime.list_runtime_receipts(
            run_id=attempt_id,
            receipt_type=RECOVERY_RECEIPT_TYPE,
            limit=2,
        )
        effect_receipts = await self._runtime.list_runtime_receipts(
            run_id=attempt_id,
            receipt_type=EFFECT_RECEIPT_TYPE,
            limit=2,
        )
        await self._validate_observed_patch_effect_receipts(effect_receipts)
        if terminal_receipts:
            if len(terminal_receipts) != 1 or recovery_receipts:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting terminal evidence"
                )
            terminal = terminal_receipts[0]
            terminal_receipt_contract(
                terminal,
                identity,
                mission_id,
                supporting_receipts=effect_receipts,
            )
            operation_hash, idempotency_metadata = terminal_operation_metadata(
                terminal, identity, mission_id
            )
            try:
                ownership_token = (
                    await self._runtime.try_begin_idempotent_side_effect_with_token(
                        identity,
                        terminal.side_effect_key,
                        metadata=idempotency_metadata,
                        stale_after_seconds=TERMINAL_CAS_STALE_AFTER_SECONDS,
                    )
                )
                (
                    ownership_token,
                    ownership_complete,
                ) = await self._recover_terminal_ownership(
                    identity,
                    side_effect_key=terminal.side_effect_key,
                    operation_hash=operation_hash,
                    receipt=terminal,
                    receipt_id=terminal.receipt_id,
                    ownership_token=ownership_token,
                )
                if not ownership_complete:
                    await self._runtime.complete_idempotent_side_effect(
                        identity,
                        terminal.side_effect_key,
                        status="completed",
                        result_receipt_id=terminal.receipt_id,
                        metadata=idempotency_metadata,
                        expected_updated_at=ownership_token,
                    )
            except (KeyError, RuntimeError, ValueError) as exc:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting terminal evidence"
                ) from exc
            await self._project_terminal_lineage(
                mission_id,
                task=task,
                run=run,
                claim=claim,
                identity=identity,
                receipt=terminal,
            )
            return True
        if effect_receipts:
            if len(effect_receipts) != 1 or recovery_receipts:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting effect evidence"
                )
            await self._recover_attempt_from_patch_effect(
                mission_id,
                claim.task_id,
                claim.agent_id,
                attempt_id=attempt_id,
                effect_key=effect_receipts[0].side_effect_key,
            )
            return True
        if run.status in {"completed", "failed"}:
            raise MissionControlError(
                f"attempt {attempt_id!r} has conflicting terminal evidence"
            )

        receipt_id = stable_id("receipt", attempt_id, "stale_recovered")
        side_effect_key = f"mission_control:{attempt_id}:stale_recovery"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": attempt_id,
            "recovered_claim_id": claim.claim_id,
            "reason": "expired_lease",
            "expired_stale_after": expired_stale_after.isoformat(),
        }
        recovery = self._matching_receipt(
            recovery_receipts,
            identity=identity,
            receipt_type=RECOVERY_RECEIPT_TYPE,
            side_effect_key=side_effect_key,
            receipt_id=receipt_id,
            status="stale_recovered",
            payload=payload,
        )
        receipt_at = recovery.created_at if recovery is not None else utc_now()
        transitioned_at = max(recovered_at, trusted_now, receipt_at)
        recovery = recovery or RuntimeReceipt(
            receipt_id=receipt_id,
            receipt_type=RECOVERY_RECEIPT_TYPE,
            status="stale_recovered",
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            side_effect_key=side_effect_key,
            payload=payload,
            created_at=receipt_at,
        )
        try:
            await asyncio.to_thread(
                _recover_stale_lineage_in_owner_transaction,
                Path(self._runtime.db_path),
                Path(self._board._db_path),
                mission_id=mission_id,
                task=task,
                run=run,
                claim=claim,
                identity=identity,
                receipt=recovery,
                recovered_at=transitioned_at,
            )
        except (OSError, RuntimeError, sqlite3.Error, ValueError) as exc:
            raise MissionControlError("expired claim recovery CAS was lost") from exc
        return False

    async def _recover_terminal_ownership(
        self, identity: ExecutionIdentity, *, side_effect_key: str,
        operation_hash: str, receipt: RuntimeReceipt | None, receipt_id: str,
        ownership_token: datetime | None,
    ) -> tuple[datetime | None, bool]:
        if ownership_token is not None:
            return ownership_token, False
        record = await self._runtime.get_idempotency_record(
            identity.idempotency_key, side_effect_key
        )
        if record is None or (
            record.run_id != identity.run_id
            or record.task_id != identity.task_id
            or record.trace_id != identity.trace_id
            or record.correlation_id != identity.correlation_id
            or record.metadata.get("operation_hash") != operation_hash
        ):
            raise MissionControlError(
                f"attempt {identity.run_id!r} already has conflicting terminal evidence"
            )
        if record.status == "stale":
            reclaimed = (
                await self._runtime.try_reclaim_idempotent_side_effect_with_token(
                    identity,
                    side_effect_key,
                    expected_status="stale",
                    expected_updated_at=record.updated_at,
                )
            )
            if reclaimed is None:
                raise MissionControlError(
                    f"terminal ownership for attempt {identity.run_id!r} was lost"
                )
            return reclaimed, False
        if record.status == "completed":
            if receipt is None or record.result_receipt_id != receipt_id:
                raise MissionControlError(
                    f"attempt {identity.run_id!r} has conflicting terminal evidence"
                )
            return None, True
        if record.status == "started":
            raise MissionControlError(
                f"terminal finish for attempt {identity.run_id!r} is already in progress"
            )
        raise MissionControlError(
            f"attempt {identity.run_id!r} already has conflicting terminal evidence"
        )


__all__ = ["MissionControlRecoveryMixin"]
