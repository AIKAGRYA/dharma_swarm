"""Ontology-native operator action lifecycle helpers.

The runtime already has the durable substrate we need: ``operator_actions``
and ``session_events``. This module keeps the first gateway layer narrow by
encoding lifecycle, gate, and warrant metadata inside those existing records
instead of adding a parallel queue.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from dharma_swarm.models import GateDecision
from dharma_swarm.runtime_state import (
    OperatorAction,
    RuntimeStateStore,
    SessionEventRecord,
)

ACTION_GATEWAY_VERSION = "operator_action_gateway.v0"

_APPROVAL_RISKS = {"high", "critical"}
_APPROVED_RESOLUTIONS = {"approved", "resolved", "allow", "accepted"}
_REJECTED_RESOLUTIONS = {"denied", "dismissed", "rejected", "block"}


@dataclass(frozen=True)
class ActionRecordResult:
    """Return value for lifecycle writes."""

    action: OperatorAction
    event: SessionEventRecord


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)


def _hash_payload(value: Any) -> str:
    return hashlib.sha256(_json_dump(value).encode("utf-8")).hexdigest()


def _short_hash(value: Any, length: int = 16) -> str:
    return _hash_payload(value)[:length]


def _normalize_risk(risk: str) -> str:
    normalized = str(risk or "medium").strip().lower()
    return normalized if normalized else "medium"


def _normalize_resolution(resolution: str) -> tuple[str, str]:
    normalized = str(resolution or "").strip().lower()
    if normalized in _APPROVED_RESOLUTIONS:
        return "approved", "runtime_applied"
    if normalized in _REJECTED_RESOLUTIONS:
        return "rejected", "runtime_rejected"
    return "recorded", "runtime_recorded"


def _gateway_action_id(
    *,
    action_name: str,
    actor: str,
    source: str,
    target: str,
    session_id: str,
    task_id: str,
    run_id: str,
    payload: dict[str, Any],
    correlation_id: str,
    idempotency_key: str,
) -> str:
    canonical = {
        "version": ACTION_GATEWAY_VERSION,
        "action_name": action_name,
        "actor": actor,
        "source": source,
        "target": target,
        "session_id": session_id,
        "task_id": task_id,
        "run_id": run_id,
        "payload_hash": _hash_payload(payload),
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
    }
    return f"opact_{_short_hash(canonical)}"


def _event_id_for(action_id: str, status: str, payload: dict[str, Any]) -> str:
    return f"sevt_{_short_hash({'action_id': action_id, 'status': status, 'payload': payload}, 24)}"


def _approval_action_id(action_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in action_id)
    return f"approval_{safe}"


class OperatorActionGateway:
    """Typed lifecycle adapter over ``RuntimeStateStore.operator_actions``."""

    def __init__(self, runtime_state: RuntimeStateStore) -> None:
        self.runtime_state = runtime_state

    async def submit_proposal(
        self,
        *,
        action_name: str,
        actor: str,
        reason: str = "",
        payload: dict[str, Any] | None = None,
        session_id: str = "",
        task_id: str = "",
        run_id: str = "",
        source: str = "operator_action_gateway",
        target: str = "",
        risk: str = "medium",
        side_effecting: bool = True,
        approval_required: bool | None = None,
        telos_check: bool = False,
        gate_content: str = "",
        correlation_id: str = "",
        idempotency_key: str = "",
        expires_in_seconds: int = 3600,
    ) -> ActionRecordResult:
        action = self._build_proposal_action(
            action_name=action_name,
            actor=actor,
            reason=reason,
            payload=payload,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            source=source,
            target=target,
            risk=risk,
            side_effecting=side_effecting,
            approval_required=approval_required,
            telos_check=telos_check,
            gate_content=gate_content,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            expires_in_seconds=expires_in_seconds,
        )
        saved = await self.runtime_state.record_operator_action(action)
        event = await self._record_lifecycle_event(saved)
        return ActionRecordResult(action=saved, event=event)

    def submit_proposal_sync(
        self,
        *,
        action_name: str,
        actor: str,
        reason: str = "",
        payload: dict[str, Any] | None = None,
        session_id: str = "",
        task_id: str = "",
        run_id: str = "",
        source: str = "operator_action_gateway",
        target: str = "",
        risk: str = "medium",
        side_effecting: bool = True,
        approval_required: bool | None = None,
        telos_check: bool = False,
        gate_content: str = "",
        correlation_id: str = "",
        idempotency_key: str = "",
        expires_in_seconds: int = 3600,
    ) -> ActionRecordResult:
        action = self._build_proposal_action(
            action_name=action_name,
            actor=actor,
            reason=reason,
            payload=payload,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            source=source,
            target=target,
            risk=risk,
            side_effecting=side_effecting,
            approval_required=approval_required,
            telos_check=telos_check,
            gate_content=gate_content,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            expires_in_seconds=expires_in_seconds,
        )
        saved = self.runtime_state.record_operator_action_sync(action)
        event = self._record_lifecycle_event_sync(saved)
        return ActionRecordResult(action=saved, event=event)

    async def record_outcome(
        self,
        action_id: str,
        *,
        status: str,
        outcome: dict[str, Any] | None = None,
        reason: str = "",
    ) -> ActionRecordResult:
        action = await self.runtime_state.get_operator_action(action_id)
        if action is None:
            raise KeyError(f"operator action not found: {action_id}")
        updated = self._with_lifecycle_transition(
            action,
            status=status,
            reason=reason or action.reason,
            outcome=outcome or {},
        )
        saved = await self.runtime_state.record_operator_action(updated)
        event = await self._record_lifecycle_event(saved)
        return ActionRecordResult(action=saved, event=event)

    async def record_approval_resolution(
        self,
        action_id: str,
        *,
        resolution: str,
        actor: str = "operator",
        summary: str = "",
        session_id: str = "",
        task_id: str = "",
        run_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status, runtime_outcome = _normalize_resolution(resolution)
        target = await self.runtime_state.get_operator_action(action_id)
        if target is not None:
            target_status = "approved" if status == "approved" else "rejected" if status == "rejected" else "approval_recorded"
            updated_target = self._with_lifecycle_transition(
                target,
                status=target_status,
                reason=summary or target.reason,
                outcome={"resolution": resolution, "resolved_by": actor},
            )
            await self.runtime_state.record_operator_action(updated_target)

        metadata = payload if isinstance(payload, dict) else {}
        approval_payload = {
            "version": ACTION_GATEWAY_VERSION,
            "kind": "approval_resolution",
            "target_action_id": action_id,
            "resolution": resolution,
            "resolution_status": status,
            "outcome": runtime_outcome,
            "enforcement_state": "runtime_recorded",
            "target_found": target is not None,
            "request": metadata,
        }
        approval_action = OperatorAction(
            action_id=_approval_action_id(action_id),
            action_name="approval.resolve",
            actor=actor,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            reason=summary or f"approval resolution {action_id}",
            payload=approval_payload,
        )
        saved_approval = await self.runtime_state.record_operator_action(approval_action)
        event_payload = {
            "action_id": action_id,
            "resolution": resolution,
            "enforcement_state": "runtime_recorded",
            "runtime_action_id": saved_approval.action_id,
            "target_action_id": action_id,
            "target_found": target is not None,
            "outcome": runtime_outcome,
        }
        event = SessionEventRecord(
            event_id=f"evt_{uuid4().hex[:16]}",
            session_id=session_id,
            ledger_kind="operator_control",
            event_name=f"approval.resolve.{runtime_outcome}",
            task_id=task_id,
            run_id=run_id,
            agent_id=actor,
            summary=summary or f"approval resolution {action_id}",
            event_text=summary or f"approval resolution {action_id}",
            payload=event_payload,
        )
        saved_event = await self.runtime_state.record_session_event(event)
        return {
            "enforcement_state": "runtime_recorded",
            "outcome": runtime_outcome,
            "runtime_action_id": saved_approval.action_id,
            "runtime_event_id": saved_event.event_id,
            "target_action_id": action_id,
            "target_found": target is not None,
        }

    def _build_proposal_action(
        self,
        *,
        action_name: str,
        actor: str,
        reason: str,
        payload: dict[str, Any] | None,
        session_id: str,
        task_id: str,
        run_id: str,
        source: str,
        target: str,
        risk: str,
        side_effecting: bool,
        approval_required: bool | None,
        telos_check: bool,
        gate_content: str,
        correlation_id: str,
        idempotency_key: str,
        expires_in_seconds: int,
    ) -> OperatorAction:
        request_payload = dict(payload or {})
        normalized_risk = _normalize_risk(risk)
        gate = self._gate(action_name=action_name, content=gate_content, payload=request_payload, enabled=telos_check)
        requires_approval = (
            bool(approval_required)
            if approval_required is not None
            else gate["decision"] == "review" or normalized_risk in _APPROVAL_RISKS
        )
        blocked = gate["decision"] == "block"
        if blocked:
            lifecycle_status = "blocked"
            warrant_state = "blocked"
        elif requires_approval:
            lifecycle_status = "waiting_approval"
            warrant_state = "pending_approval"
        else:
            lifecycle_status = "warrant_issued"
            warrant_state = "issued"

        created_at = _utc_now()
        input_hash = _hash_payload(request_payload)
        corr_id = correlation_id or f"corr_{_short_hash({'action': action_name, 'payload': request_payload}, 12)}"
        idem_key = idempotency_key or corr_id
        action_id = _gateway_action_id(
            action_name=action_name,
            actor=actor,
            source=source,
            target=target,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            payload=request_payload,
            correlation_id=corr_id,
            idempotency_key=idem_key,
        )
        full_payload = {
            "version": ACTION_GATEWAY_VERSION,
            "kind": "operator_action",
            "source": source,
            "target": target,
            "risk": normalized_risk,
            "side_effecting": bool(side_effecting),
            "correlation_id": corr_id,
            "idempotency_key": idem_key,
            "lifecycle": {
                "status": lifecycle_status,
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
                "approval_required": requires_approval,
                "executable": lifecycle_status == "warrant_issued",
            },
            "warrant": {
                "warrant_id": f"warrant_{_short_hash({'action_id': action_id, 'input_hash': input_hash})}",
                "state": warrant_state,
                "input_hash": input_hash,
                "scope": {
                    "action_name": action_name,
                    "actor": actor,
                    "source": source,
                    "target": target,
                    "session_id": session_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "side_effecting": bool(side_effecting),
                    "risk": normalized_risk,
                },
                "expires_at": (created_at + timedelta(seconds=max(60, expires_in_seconds))).isoformat(),
            },
            "gate": gate,
            "request": request_payload,
        }
        return OperatorAction(
            action_id=action_id,
            action_name=action_name,
            actor=actor,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
            reason=reason,
            payload=full_payload,
            created_at=created_at,
        )

    def _gate(
        self,
        *,
        action_name: str,
        content: str,
        payload: dict[str, Any],
        enabled: bool,
    ) -> dict[str, Any]:
        if not enabled:
            return {
                "decision": "allow",
                "reason": "telos_check_disabled",
                "source": "operator_action_gateway",
            }
        try:
            from dharma_swarm.telos_gates import check_action

            gate_content = content or _json_dump(payload)
            result = check_action(action=action_name, content=gate_content)
            decision = result.decision
            if isinstance(decision, GateDecision):
                decision_value = decision.value
            else:
                decision_value = str(decision).lower()
            return {
                "decision": decision_value,
                "reason": str(getattr(result, "reason", "") or ""),
                "source": "telos_gates.check_action",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "decision": "review",
                "reason": f"telos_check_error: {type(exc).__name__}: {exc}",
                "source": "telos_gates.check_action",
            }

    def _with_lifecycle_transition(
        self,
        action: OperatorAction,
        *,
        status: str,
        reason: str,
        outcome: dict[str, Any],
    ) -> OperatorAction:
        payload = dict(action.payload)
        now = _utc_now().isoformat()
        lifecycle = dict(payload.get("lifecycle") or {})
        history = list(lifecycle.get("history") or [])
        history.append({"status": status, "at": now, "reason": reason})
        lifecycle.update(
            {
                "status": status,
                "updated_at": now,
                "history": history,
                "executable": status in {"warrant_issued", "approved"},
            }
        )
        payload["lifecycle"] = lifecycle
        if outcome:
            payload["outcome"] = outcome
        warrant = dict(payload.get("warrant") or {})
        if status in {"executed", "failed", "cancelled"}:
            warrant["state"] = "consumed" if status == "executed" else status
        elif status == "approved":
            warrant["state"] = "issued"
        elif status == "rejected":
            warrant["state"] = "rejected"
        payload["warrant"] = warrant
        return replace(action, reason=reason, payload=payload)

    async def _record_lifecycle_event(self, action: OperatorAction) -> SessionEventRecord:
        lifecycle = action.payload.get("lifecycle") if isinstance(action.payload, dict) else {}
        status = str((lifecycle or {}).get("status") or "recorded")
        event_payload = {
            "runtime_action_id": action.action_id,
            "action_name": action.action_name,
            "actor": action.actor,
            "status": status,
            "warrant": action.payload.get("warrant", {}),
            "gate": action.payload.get("gate", {}),
            "risk": action.payload.get("risk", ""),
            "source": action.payload.get("source", ""),
            "target": action.payload.get("target", ""),
        }
        event = SessionEventRecord(
            event_id=_event_id_for(action.action_id, status, event_payload),
            session_id=action.session_id,
            ledger_kind="operator_action",
            event_name=f"operator_action.{status}",
            task_id=action.task_id,
            run_id=action.run_id,
            agent_id=action.actor,
            summary=action.reason or action.action_name,
            event_text=f"{action.action_name}: {action.reason}".strip(),
            payload=event_payload,
        )
        return await self.runtime_state.record_session_event(event)

    def _record_lifecycle_event_sync(self, action: OperatorAction) -> SessionEventRecord:
        lifecycle = action.payload.get("lifecycle") if isinstance(action.payload, dict) else {}
        status = str((lifecycle or {}).get("status") or "recorded")
        event_payload = {
            "runtime_action_id": action.action_id,
            "action_name": action.action_name,
            "actor": action.actor,
            "status": status,
            "warrant": action.payload.get("warrant", {}),
            "gate": action.payload.get("gate", {}),
            "risk": action.payload.get("risk", ""),
            "source": action.payload.get("source", ""),
            "target": action.payload.get("target", ""),
        }
        event = SessionEventRecord(
            event_id=_event_id_for(action.action_id, status, event_payload),
            session_id=action.session_id,
            ledger_kind="operator_action",
            event_name=f"operator_action.{status}",
            task_id=action.task_id,
            run_id=action.run_id,
            agent_id=action.actor,
            summary=action.reason or action.action_name,
            event_text=f"{action.action_name}: {action.reason}".strip(),
            payload=event_payload,
        )
        return self.runtime_state.record_session_event_sync(event)
