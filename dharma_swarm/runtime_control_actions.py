"""Runtime control action writes backed by the canonical RuntimeStateStore."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.runtime_state import (
    OperatorAction,
    RuntimeStateStore,
    SessionEventRecord,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _serialize_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


def _event_payload(event: SessionEventRecord) -> dict[str, Any]:
    return dict(event.payload) if isinstance(event.payload, dict) else {}


def _is_control_event(event: SessionEventRecord) -> bool:
    name = event.event_name.lower()
    payload = _event_payload(event)
    keys = {str(key).lower() for key in payload}
    control_keys = {
        "approval_id",
        "approval_status",
        "human_approval_required",
        "interrupt_id",
        "requires_human",
        "resume_token",
    }
    return (
        "interrupt" in name
        or "resume" in name
        or "approval" in name
        or bool(keys & control_keys)
    )


def _control_type(event: SessionEventRecord) -> str:
    name = event.event_name.lower()
    payload = _event_payload(event)
    if "interrupt" in name:
        return "interrupt"
    if "resume" in name:
        return "resume"
    if "approval" in name or payload.get("approval_id") or payload.get("approval_status"):
        return "human_approval"
    if payload.get("resume_token"):
        return "resume"
    return "interrupt"


def _control_status(event: SessionEventRecord) -> str:
    payload = _event_payload(event)
    explicit = payload.get("approval_status") or payload.get("status") or payload.get("decision")
    if explicit:
        return str(explicit)
    name = event.event_name.lower()
    if "reject" in name or "denied" in name:
        return "rejected"
    if "grant" in name or "approve" in name:
        return "approved"
    if "resume" in name:
        return "resumed"
    if "resolve" in name:
        return "resolved"
    if "request" in name or "required" in name:
        return "pending"
    return "unknown"


def _control_payload_value(event: SessionEventRecord, key: str) -> str:
    payload = _event_payload(event)
    return str(payload.get(key) or "").strip()


class RuntimeControlActions:
    """Auditable approve/reject/resume writes for runtime control events."""

    def __init__(self, runtime_state: RuntimeStateStore) -> None:
        self.runtime_state = runtime_state

    async def runtime_control_action(
        self,
        *,
        action: str,
        session_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        approval_id: str | None = None,
        interrupt_id: str | None = None,
        resume_token: str | None = None,
        actor: str = "operator",
        reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        action_key = action.strip().lower()
        if action_key not in {"approve", "reject", "resume"}:
            raise ValueError(f"unsupported runtime control action: {action}")

        action_payload = dict(payload or {})
        target = await self._find_control_target(
            session_id=session_id,
            run_id=run_id,
            approval_id=approval_id,
            interrupt_id=interrupt_id,
            resume_token=resume_token,
        )
        target_payload = _event_payload(target) if target is not None else {}
        resolved_session_id = session_id or (target.session_id if target else "")
        resolved_task_id = task_id or (target.task_id if target else "")
        resolved_run_id = run_id or (target.run_id if target else "")
        resolved_approval_id = (
            approval_id or str(target_payload.get("approval_id") or "").strip()
        )
        resolved_interrupt_id = (
            interrupt_id or str(target_payload.get("interrupt_id") or "").strip()
        )
        resolved_resume_token = (
            resume_token or str(target_payload.get("resume_token") or "").strip()
        )
        status = {
            "approve": "approved",
            "reject": "rejected",
            "resume": "resumed",
        }[action_key]
        event_name = {
            "approve": "human_approval_approved",
            "reject": "human_approval_rejected",
            "resume": "runtime_resume_requested",
        }[action_key]
        summary = reason.strip() or f"Runtime control {action_key} recorded"
        now = _utc_now()

        action_record = await self.runtime_state.record_operator_action(
            OperatorAction(
                action_id=self.runtime_state.new_action_id(),
                action_name=f"runtime_control.{action_key}",
                actor=actor.strip() or "operator",
                session_id=resolved_session_id,
                task_id=resolved_task_id,
                run_id=resolved_run_id,
                reason=summary,
                payload={
                    **action_payload,
                    "action": action_key,
                    "status": status,
                    "approval_id": resolved_approval_id,
                    "interrupt_id": resolved_interrupt_id,
                    "resume_token": resolved_resume_token,
                    "target_event_id": target.event_id if target is not None else "",
                },
                created_at=now,
            )
        )
        transport = self._write_interrupt_transport_response(
            action=action_key,
            interrupt_id=resolved_interrupt_id,
            reason=summary,
            payload=action_payload,
        )
        event = await self.runtime_state.record_session_event(
            SessionEventRecord(
                event_id=f"evt_{uuid4().hex[:16]}",
                session_id=resolved_session_id,
                ledger_kind="operator_control",
                event_name=event_name,
                task_id=resolved_task_id,
                run_id=resolved_run_id,
                agent_id=actor.strip() or "operator",
                summary=summary,
                event_text=summary,
                payload={
                    **action_payload,
                    "action": action_key,
                    "status": status,
                    "decision": status,
                    "approval_status": status if action_key != "resume" else "",
                    "approval_id": resolved_approval_id,
                    "interrupt_id": resolved_interrupt_id,
                    "resume_token": resolved_resume_token,
                    "runtime_action_id": action_record.action_id,
                    "target_event_id": target.event_id if target is not None else "",
                    "interrupt_transport": transport,
                },
                created_at=now,
            )
        )
        interrupts = await self._runtime_interrupts(
            session_id=resolved_session_id or session_id,
            limit=20,
        )
        return {
            "schema_version": "runtime_control_action_result.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "action": action_key,
            "status": status,
            "target_found": target is not None,
            "target_control_event": (
                self._control_event_to_dict(target) if target is not None else None
            ),
            "operator_action": _serialize_value(action_record),
            "event": self._event_to_dict(event),
            "interrupt_transport": transport,
            "interrupts": interrupts,
        }

    async def _runtime_interrupts(
        self,
        *,
        session_id: str | None,
        limit: int,
    ) -> dict[str, Any]:
        max_items = max(1, limit)
        events = await self.runtime_state.list_session_events(
            session_id=session_id,
            limit=min(max_items * 20, 1000),
        )
        controls = [
            self._control_event_to_dict(event)
            for event in events
            if _is_control_event(event)
        ][:max_items]
        return {
            "schema_version": "runtime_interrupts_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {"session_id": session_id, "status": None, "limit": max_items},
            "summary": {
                "control_event_count": len(controls),
                "pending_interrupt_count": sum(
                    1
                    for event in controls
                    if event["control_type"] == "interrupt" and event["status"] == "pending"
                ),
                "human_approval_required_count": sum(
                    1 for event in controls if event["requires_human"]
                ),
                "approved_count": sum(1 for event in controls if event["status"] == "approved"),
                "resumed_count": sum(1 for event in controls if event["status"] == "resumed"),
            },
            "control_events": controls,
        }

    async def _find_control_target(
        self,
        *,
        session_id: str | None,
        run_id: str | None,
        approval_id: str | None,
        interrupt_id: str | None,
        resume_token: str | None,
    ) -> SessionEventRecord | None:
        events = await self.runtime_state.list_session_events(
            session_id=session_id,
            limit=1000,
        )
        controls = [event for event in events if _is_control_event(event)]
        identifiers = {
            "run_id": (run_id or "").strip(),
            "approval_id": (approval_id or "").strip(),
            "interrupt_id": (interrupt_id or "").strip(),
            "resume_token": (resume_token or "").strip(),
        }
        matches: list[SessionEventRecord] = []
        for event in controls:
            if identifiers["run_id"] and event.run_id != identifiers["run_id"]:
                continue
            if identifiers["approval_id"] and (
                _control_payload_value(event, "approval_id") != identifiers["approval_id"]
            ):
                continue
            if identifiers["interrupt_id"] and (
                _control_payload_value(event, "interrupt_id") != identifiers["interrupt_id"]
            ):
                continue
            if identifiers["resume_token"] and (
                _control_payload_value(event, "resume_token") != identifiers["resume_token"]
            ):
                continue
            matches.append(event)
        if matches:
            return next(
                (event for event in matches if _control_status(event) == "pending"),
                matches[0],
            )
        if any(identifiers.values()):
            return None
        return next((event for event in controls if _control_status(event) == "pending"), None)

    @staticmethod
    def _write_interrupt_transport_response(
        *,
        action: str,
        interrupt_id: str,
        reason: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not interrupt_id:
            return {"attempted": False, "reason": "no interrupt_id supplied"}
        try:
            from dharma_swarm.checkpoint import (
                InterruptDecision,
                InterruptResponse,
                write_interrupt_response,
            )

            decision = (
                InterruptDecision.REJECT
                if action == "reject"
                else InterruptDecision.APPROVE
            )
            modified_artifact = payload.get("modified_artifact")
            if not isinstance(modified_artifact, dict):
                modified_artifact = None
            response = InterruptResponse(
                request_id=interrupt_id,
                decision=decision,
                reason=reason,
                modified_artifact=modified_artifact,
            )
            response_path = write_interrupt_response(response)
            gate_resolved = False
            try:
                from dharma_swarm.cascade import get_interrupt_gate

                gate_resolved = get_interrupt_gate().resolve(response)
            except Exception as exc:  # pragma: no cover - best-effort live gate
                return {
                    "attempted": True,
                    "response_path": str(response_path),
                    "gate_resolved": False,
                    "gate_error": str(exc),
                }
            return {
                "attempted": True,
                "response_path": str(response_path),
                "gate_resolved": gate_resolved,
            }
        except Exception as exc:
            return {"attempted": True, "error": str(exc)}

    @staticmethod
    def _event_to_dict(event: SessionEventRecord) -> dict[str, Any]:
        return _serialize_value(event)

    @staticmethod
    def _control_event_to_dict(event: SessionEventRecord) -> dict[str, Any]:
        event_view = _serialize_value(event)
        payload = event_view.get("payload") or {}
        control_type = _control_type(event)
        status = _control_status(event)
        requires_human = bool(
            payload.get("requires_human")
            or payload.get("human_approval_required")
            or (control_type == "human_approval" and status == "pending")
        )
        return {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "task_id": event.task_id,
            "run_id": event.run_id,
            "agent_id": event.agent_id,
            "event_name": event.event_name,
            "control_type": control_type,
            "status": status,
            "requires_human": requires_human,
            "interrupt_id": str(payload.get("interrupt_id") or ""),
            "approval_id": str(payload.get("approval_id") or ""),
            "resume_token": str(payload.get("resume_token") or ""),
            "checkpoint_id": str(payload.get("checkpoint_id") or ""),
            "summary": event.summary,
            "created_at": event.created_at.isoformat(),
            "event": event_view,
        }
