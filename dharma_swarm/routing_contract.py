"""Canonical routing contract facade.

This module is a narrow port over the existing routing substrate. It does not
rank providers, mutate policy, or instantiate a second router. Its job is to
give call sites one stable way to ask for an LLM completion while preserving
the routing plane's telemetry, audit, and resident-handoff semantics.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import ProviderRouteDecision, ProviderRouteRequest
from dharma_swarm.providers import ModelRouter
from dharma_swarm.runtime_provider import create_default_provider_map
from dharma_swarm.telemetry_plane import (
    DEFAULT_TELEMETRY_DB,
    ExternalOutcomeRecord,
    RoutingDecisionRecord,
    TelemetryPlaneStore,
)

RoutingOutcome = Literal["success", "no_route", "all_failed", "error"]


@dataclass(frozen=True, slots=True)
class RoutedCompletion:
    """Result object returned by the routing contract facade."""

    decision: ProviderRouteDecision | None
    response: LLMResponse | None
    outcome: RoutingOutcome
    task_signature: str
    resident_handoff: bool = False
    error: str = ""


def _default_audit_log_path() -> Path:
    configured = os.environ.get("DGC_ROUTER_AUDIT_LOG", "").strip()
    if configured:
        return Path(configured)
    return Path.home() / ".dharma" / "logs" / "router" / "routing_decisions.jsonl"


def _audit_enabled() -> bool:
    return os.environ.get("DGC_ROUTER_AUDIT_DISABLE", "0").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


def _error_outcome(error: BaseException | str) -> RoutingOutcome:
    message = str(error).lower()
    if "no available providers" in message:
        return "no_route"
    if "all providers failed" in message:
        return "all_failed"
    return "error"


def _telemetry_from_router(router: ModelRouter) -> TelemetryPlaneStore | None:
    telemetry = getattr(router, "_telemetry", None)
    return telemetry if isinstance(telemetry, TelemetryPlaneStore) else None


def _append_resident_audit(
    *,
    audit_log_path: Path | None,
    route_request: ProviderRouteRequest,
    task_signature: str,
    caller: str,
    task_type: str,
    outcome: RoutingOutcome,
    error: str,
) -> None:
    if not _audit_enabled():
        return
    path = audit_log_path or _default_audit_log_path()
    row = {
        "row_kind": "resident_handoff",
        "schema_version": "routing_contract_v1",
        "decision_id": f"resident_{uuid4().hex[:16]}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "action_name": route_request.action_name,
        "caller": caller,
        "task_type": task_type,
        "task_signature": task_signature,
        "outcome": outcome,
        "selected_provider": "",
        "selected_model": "resident-control-plane",
        "requires_human": True,
        "metadata": {
            "resident_fallback": True,
            "resident_agent": "resident_control_plane",
            "error": error[:300],
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        return


async def _record_resident_handoff(
    *,
    route_request: ProviderRouteRequest,
    task_signature: str,
    caller: str,
    task_type: str,
    outcome: RoutingOutcome,
    error: BaseException | str,
    telemetry: TelemetryPlaneStore | None,
    audit_log_path: Path | None,
) -> None:
    error_text = str(error)[:300]
    metadata = {
        "resident_fallback": True,
        "resident_agent": "resident_control_plane",
        "caller": caller,
        "task_type": task_type,
        "task_signature": task_signature,
        "outcome": outcome,
        "error": error_text,
        "next_action": "retry_or_escalate_when_provider_lane_recovers",
    }
    if telemetry is not None:
        scope = {
            "session_id": str(route_request.context.get("session_id") or ""),
            "task_id": str(route_request.context.get("task_id") or ""),
            "run_id": str(route_request.context.get("run_id") or ""),
        }
        try:
            await telemetry.record_routing_decision(
                RoutingDecisionRecord(
                    decision_id=f"resident_{uuid4().hex[:16]}",
                    action_name=route_request.action_name,
                    route_path="resident_degraded_handoff",
                    selected_provider="",
                    selected_model_hint="resident-control-plane",
                    confidence=0.0,
                    requires_human=True,
                    session_id=scope["session_id"],
                    task_id=scope["task_id"],
                    run_id=scope["run_id"],
                    reasons=[f"resident_handoff:{outcome}"],
                    metadata=metadata,
                )
            )
            await telemetry.record_external_outcome(
                ExternalOutcomeRecord(
                    outcome_id=f"outcome_{uuid4().hex[:16]}",
                    outcome_kind="resident_degraded_handoff",
                    value=1.0,
                    unit="handoff",
                    confidence=1.0,
                    status="queued",
                    subject_id="resident_control_plane",
                    summary=(
                        f"{route_request.action_name} handed to resident "
                        f"control plane after {outcome}"
                    ),
                    session_id=scope["session_id"],
                    task_id=scope["task_id"],
                    run_id=scope["run_id"],
                    metadata=metadata,
                )
            )
        except Exception:
            pass

    _append_resident_audit(
        audit_log_path=audit_log_path,
        route_request=route_request,
        task_signature=task_signature,
        caller=caller,
        task_type=task_type,
        outcome=outcome,
        error=error_text,
    )

    try:
        from dharma_swarm.stigmergy import leave_stigmergic_mark

        await leave_stigmergic_mark(
            agent="resident_control_plane",
            file_path="dharma_swarm/routing_contract.py",
            observation=(
                f"Routing handoff for {route_request.action_name}: "
                f"{outcome}; resident control plane queued."
            )[:200],
            salience=0.95,
            connections=[task_signature, caller, task_type],
            action="connect",
            channel="action_queue",
        )
    except Exception:
        pass


async def complete_routed(
    *,
    request: LLMRequest,
    action_name: str,
    context: dict[str, Any] | None = None,
    caller: str,
    task_type: str = "unknown",
    router: ModelRouter | None = None,
    telemetry: TelemetryPlaneStore | None = None,
    telemetry_db_path: Path | None = None,
    available_provider_types: list[ProviderType] | None = None,
    audit_log_path: Path | None = None,
    raise_on_failure: bool = True,
    risk_score: float = 0.2,
    uncertainty: float = 0.2,
    novelty: float = 0.2,
    urgency: float = 0.4,
    expected_impact: float = 0.3,
) -> RoutedCompletion:
    """Complete an LLM request through the canonical routing contract.

    Callers may pass an existing ``ModelRouter``. If omitted, the facade creates
    a default router using the current runtime provider map. On terminal
    provider failure the provider error is preserved, but a resident handoff is
    recorded before the error is re-raised unless ``raise_on_failure=False``.
    """

    routed_context = {
        **(context or {}),
        "caller": caller,
        "task_type": task_type,
    }
    route_request = ProviderRouteRequest(
        action_name=action_name,
        risk_score=risk_score,
        uncertainty=uncertainty,
        novelty=novelty,
        urgency=urgency,
        expected_impact=expected_impact,
        estimated_tokens=request.max_tokens,
        context=routed_context,
    )
    effective_telemetry = telemetry
    if effective_telemetry is None and telemetry_db_path is not None:
        effective_telemetry = TelemetryPlaneStore(telemetry_db_path)
    effective_router = router or ModelRouter(
        create_default_provider_map(),
        telemetry=effective_telemetry,
    )
    if effective_telemetry is None:
        effective_telemetry = _telemetry_from_router(effective_router)
        if effective_telemetry is None and telemetry_db_path is None:
            configured = os.environ.get("DGC_ROUTER_TELEMETRY_DB", "").strip()
            if configured:
                effective_telemetry = TelemetryPlaneStore(Path(configured))
            elif os.environ.get("DGC_ROUTER_TELEMETRY_ENABLE", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }:
                effective_telemetry = TelemetryPlaneStore(DEFAULT_TELEMETRY_DB)

    task_signature = effective_router.task_signature_for(route_request, request)
    try:
        decision, response = await effective_router.complete_for_task(
            route_request,
            request,
            available_provider_types=available_provider_types,
        )
        return RoutedCompletion(
            decision=decision,
            response=response,
            outcome="success",
            task_signature=task_signature,
        )
    except Exception as exc:
        outcome = _error_outcome(exc)
        await _record_resident_handoff(
            route_request=route_request,
            task_signature=task_signature,
            caller=caller,
            task_type=task_type,
            outcome=outcome,
            error=exc,
            telemetry=effective_telemetry,
            audit_log_path=audit_log_path,
        )
        if raise_on_failure:
            raise
        return RoutedCompletion(
            decision=None,
            response=None,
            outcome=outcome,
            task_signature=task_signature,
            resident_handoff=True,
            error=str(exc),
        )


__all__ = ["RoutedCompletion", "RoutingOutcome", "complete_routed"]
