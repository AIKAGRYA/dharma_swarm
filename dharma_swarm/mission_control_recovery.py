"""Terminal attempt completion and stale-lineage recovery mechanics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
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
    stable_id,
    terminal_operation_metadata,
    terminal_receipt_contract,
    utc_now,
)
from dharma_swarm.mission_control_lifecycle import _serialized_task
from dharma_swarm.mission_control_projection import receipt_view
from dharma_swarm.runtime_state import RuntimeReceipt, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity


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
        claim = await self._runtime.get_task_claim(run.claim_id)
        if claim is None:
            raise MissionControlError(f"claim {run.claim_id!r} was not found")
        self._require_claim_identity(claim, mission_id, task_id, agent_id, run.run_id)
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
        """Close an expired lineage; no cross-process lease CAS is claimed."""
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
        if terminal_receipts:
            if len(terminal_receipts) != 1 or recovery_receipts:
                raise MissionControlError(
                    f"attempt {attempt_id!r} has conflicting terminal evidence"
                )
            terminal = terminal_receipts[0]
            terminal_receipt_contract(terminal, identity, mission_id)
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
            task = await self._require_task(mission_id, claim.task_id)
            await self._project_terminal_lineage(
                mission_id,
                task=task,
                run=run,
                claim=claim,
                identity=identity,
                receipt=terminal,
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
        if recovery is None:
            await self._runtime.record_receipt_for_identity(
                identity,
                receipt_type=RECOVERY_RECEIPT_TYPE,
                status="stale_recovered",
                side_effect_key=side_effect_key,
                payload=payload,
                receipt_id=receipt_id,
            )
        transitioned_at = max(recovered_at, trusted_now, utc_now())
        if run is not None and run.status != "stale_recovered":
            await self._runtime.record_delegation_run(
                replace(
                    run,
                    status="stale_recovered",
                    completed_at=transitioned_at,
                    failure_code="stale_lease_recovered",
                    metadata={
                        **run.metadata,
                        "recovered_claim_id": claim.claim_id,
                        "recovery_receipt_id": receipt_id,
                    },
                )
            )
        if claim.status != "stale_recovered":
            await self._runtime.record_task_claim(
                replace(
                    claim,
                    status="stale_recovered",
                    recovered_at=transitioned_at,
                    metadata={
                        **claim.metadata,
                        "recovery_receipt_id": receipt_id,
                    },
                )
            )
        return False

    async def _recover_terminal_ownership(
        self,
        identity: ExecutionIdentity,
        *,
        side_effect_key: str,
        operation_hash: str,
        receipt: RuntimeReceipt | None,
        receipt_id: str,
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
