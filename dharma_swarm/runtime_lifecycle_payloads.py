"""Payload helpers for RuntimeLifecycle receipt truth fields."""

from __future__ import annotations

from typing import Any

from dharma_swarm.models import TaskDispatch


def first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def mission_payload(
    task_metadata: dict[str, Any],
    dispatch_metadata: dict[str, Any],
    identity_metadata: dict[str, Any],
    *,
    task_id: str,
    session_id: str,
) -> dict[str, str]:
    explicit_mission_id = first_text(
        task_metadata.get("mission_id"),
        task_metadata.get("missionId"),
        dispatch_metadata.get("mission_id"),
        dispatch_metadata.get("missionId"),
        identity_metadata.get("mission_id"),
        identity_metadata.get("missionId"),
    )
    explicit_mission = first_text(
        task_metadata.get("mission"),
        dispatch_metadata.get("mission"),
        identity_metadata.get("mission"),
    )
    mission = first_text(explicit_mission, explicit_mission_id, session_id, task_id)
    mission_id = first_text(explicit_mission_id, explicit_mission, mission)
    return {
        "mission_id": mission_id,
        "mission": mission,
        "mission_id_source": (
            "explicit_mission_id"
            if explicit_mission_id
            else "explicit_mission"
            if explicit_mission
            else "runtime_lifecycle_fallback"
        ),
    }


def runtime_metadata(
    td: TaskDispatch,
    *,
    status: str,
    failure_code: str = "",
    error: str = "",
    result: str | None = None,
) -> dict[str, Any]:
    metadata = {
        "source": "orchestrator",
        "status": status,
        "topology": td.topology.value if td.topology else "dispatch",
        "timeout_seconds": td.timeout_seconds,
        "retry_count": td.metadata.get("retry_count", 0),
        "max_retries": td.metadata.get("max_retries", 0),
        "claim_timeout_seconds": td.metadata.get("claim_timeout_seconds", 0),
    }
    generation = td.metadata.get("attempt_generation")
    if (
        isinstance(generation, int)
        and not isinstance(generation, bool)
        and generation >= 0
    ):
        metadata["attempt_generation"] = generation
    if failure_code:
        metadata["failure_code"] = failure_code
    if error:
        metadata["error"] = error[:500]
    if result is not None:
        metadata["result_chars"] = len(result or "")
    for key in (
        "context_bundle_id",
        "context_bundle_status",
        "context_bundle_error",
        "runtime_db_path",
    ):
        value = td.metadata.get(key)
        if value:
            metadata[key] = value
    return metadata


def route_truth(
    task_metadata: dict[str, Any],
    dispatch_metadata: dict[str, Any],
    identity_metadata: dict[str, Any],
    *,
    failure_code: str = "",
    status: str = "",
) -> dict[str, Any]:
    served_provider = first_text(
        task_metadata.get("actual_served_provider"),
        dispatch_metadata.get("actual_served_provider"),
        identity_metadata.get("actual_served_provider"),
        task_metadata.get("served_provider"),
        dispatch_metadata.get("served_provider"),
        identity_metadata.get("served_provider"),
        task_metadata.get("actual_provider"),
        dispatch_metadata.get("actual_provider"),
        identity_metadata.get("actual_provider"),
        task_metadata.get("provider_served"),
        dispatch_metadata.get("provider_served"),
        identity_metadata.get("provider_served"),
    )
    selected_provider = first_text(
        task_metadata.get("selected_provider"),
        dispatch_metadata.get("selected_provider"),
        identity_metadata.get("selected_provider"),
        task_metadata.get("provider_selected"),
        dispatch_metadata.get("provider_selected"),
    )
    ambiguous_provider = first_text(
        task_metadata.get("provider"),
        dispatch_metadata.get("provider"),
        identity_metadata.get("provider"),
    )
    served_model = first_text(
        task_metadata.get("actual_served_model"),
        dispatch_metadata.get("actual_served_model"),
        identity_metadata.get("actual_served_model"),
        task_metadata.get("served_model"),
        dispatch_metadata.get("served_model"),
        identity_metadata.get("served_model"),
        task_metadata.get("actual_model"),
        dispatch_metadata.get("actual_model"),
        identity_metadata.get("actual_model"),
        task_metadata.get("model_served"),
        dispatch_metadata.get("model_served"),
        identity_metadata.get("model_served"),
    )
    selected_model = first_text(
        task_metadata.get("selected_model"),
        dispatch_metadata.get("selected_model"),
        identity_metadata.get("selected_model"),
        task_metadata.get("model_selected"),
        dispatch_metadata.get("model_selected"),
        task_metadata.get("selected_model_hint"),
        dispatch_metadata.get("selected_model_hint"),
    )
    ambiguous_model = first_text(
        task_metadata.get("model"),
        dispatch_metadata.get("model"),
        identity_metadata.get("model"),
    )
    if not selected_provider and not served_provider:
        selected_provider = ambiguous_provider
    if not selected_model and not served_model:
        selected_model = ambiguous_model

    route: dict[str, Any] = {}
    if served_provider:
        route["actual_served_provider"] = served_provider
        route["served_provider"] = served_provider
        route["provider_served"] = served_provider
        route["provider"] = served_provider
    if selected_provider:
        route["selected_provider"] = selected_provider
        route.setdefault("provider", selected_provider)
    if served_model:
        route["actual_served_model"] = served_model
        route["served_model"] = served_model
        route["model_served"] = served_model
        route["model"] = served_model
    if selected_model:
        route["selected_model"] = selected_model
        route["selected_model_hint"] = selected_model
        route.setdefault("model", selected_model)

    source = first_text(
        task_metadata.get("provider_model_truth_source"),
        dispatch_metadata.get("provider_model_truth_source"),
        identity_metadata.get("provider_model_truth_source"),
        task_metadata.get("route_truth_source"),
        dispatch_metadata.get("route_truth_source"),
        identity_metadata.get("route_truth_source"),
    )
    if route and source:
        route["provider_model_truth_source"] = source

    explicit_applicability = first_text(
        task_metadata.get("provider_model_applicability"),
        dispatch_metadata.get("provider_model_applicability"),
        identity_metadata.get("provider_model_applicability"),
    )
    explicit_missing_reason = first_text(
        task_metadata.get("provider_model_missing_reason"),
        dispatch_metadata.get("provider_model_missing_reason"),
        identity_metadata.get("provider_model_missing_reason"),
    )
    explicit_no_provider = _explicit_no_provider_execution(
        task_metadata,
        dispatch_metadata,
        identity_metadata,
    )
    if explicit_no_provider and not _has_served_provider_model(route):
        return explicit_no_provider

    failure_no_provider = _failure_no_provider_execution(failure_code)
    if failure_no_provider and not _has_served_provider_model(route):
        return failure_no_provider

    if route and source and not _has_served_provider_model(route):
        if _is_terminal_status(status):
            route["provider_execution"] = True
            if explicit_applicability:
                applicability = explicit_applicability
            elif source == "agent_runner.provider_chain_failure":
                applicability = "failed_before_serve"
            else:
                applicability = "actual_served_unproven"
            route["provider_model_applicability"] = applicability
            route["provider_model_truth_source"] = source
            if explicit_missing_reason:
                reason = explicit_missing_reason
            elif applicability == "failed_before_serve":
                reason = "provider_chain_failed_before_actual_served_response"
            else:
                reason = "attempted_route_selected_without_actual_served_runtime_evidence"
            route["provider_model_missing_reason"] = reason
            return route
        route["provider_execution"] = "pending"
        route["provider_model_applicability"] = "pending_execution"
        route["provider_model_truth_source"] = source
        route["provider_model_pending_reason"] = "worker_execution_not_terminal"
        return route

    explicit_unproven_provider = _explicit_unproven_provider_execution(
        task_metadata,
        dispatch_metadata,
        identity_metadata,
    )
    if explicit_unproven_provider and not _has_served_provider_model(route):
        return explicit_unproven_provider

    pending_provider = _pending_provider_execution(status=status)
    if pending_provider and not route:
        return pending_provider

    terminal_unproven_provider = _terminal_unproven_provider_execution(status=status)
    if terminal_unproven_provider and not route:
        return terminal_unproven_provider
    return route


def _falseish(value: Any) -> bool:
    if value is False:
        return True
    return str(value or "").strip().lower() in {"false", "0", "no"}


def _trueish(value: Any) -> bool:
    if value is True:
        return True
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _explicit_no_provider_execution(
    task_metadata: dict[str, Any],
    dispatch_metadata: dict[str, Any],
    identity_metadata: dict[str, Any],
) -> dict[str, Any]:
    provider_execution_false = any(
        _falseish(payload.get("provider_execution"))
        for payload in (task_metadata, dispatch_metadata, identity_metadata)
    )
    if not provider_execution_false:
        return {}
    truth_source = first_text(
        task_metadata.get("provider_model_truth_source"),
        dispatch_metadata.get("provider_model_truth_source"),
        identity_metadata.get("provider_model_truth_source"),
        task_metadata.get("route_truth_source"),
        dispatch_metadata.get("route_truth_source"),
        identity_metadata.get("route_truth_source"),
    )
    applicability = first_text(
        task_metadata.get("provider_model_applicability"),
        dispatch_metadata.get("provider_model_applicability"),
        identity_metadata.get("provider_model_applicability"),
    )
    reason = first_text(
        task_metadata.get("no_provider_model_reason"),
        dispatch_metadata.get("no_provider_model_reason"),
        identity_metadata.get("no_provider_model_reason"),
    )
    if not truth_source or not (applicability or reason):
        return {}
    truth: dict[str, Any] = {
        "provider_execution": False,
        "provider_model_truth_source": truth_source,
    }
    if applicability:
        truth["provider_model_applicability"] = applicability
    if reason:
        truth["no_provider_model_reason"] = reason
    return truth


def _explicit_unproven_provider_execution(
    task_metadata: dict[str, Any],
    dispatch_metadata: dict[str, Any],
    identity_metadata: dict[str, Any],
) -> dict[str, Any]:
    provider_execution_true = any(
        _trueish(payload.get("provider_execution"))
        for payload in (task_metadata, dispatch_metadata, identity_metadata)
    )
    if not provider_execution_true:
        return {}
    truth_source = first_text(
        task_metadata.get("provider_model_truth_source"),
        dispatch_metadata.get("provider_model_truth_source"),
        identity_metadata.get("provider_model_truth_source"),
        task_metadata.get("route_truth_source"),
        dispatch_metadata.get("route_truth_source"),
        identity_metadata.get("route_truth_source"),
    )
    if not truth_source:
        return {}
    return {
        "provider_execution": True,
        "provider_model_applicability": first_text(
            task_metadata.get("provider_model_applicability"),
            dispatch_metadata.get("provider_model_applicability"),
            identity_metadata.get("provider_model_applicability"),
            "actual_served_unproven",
        ),
        "provider_model_truth_source": truth_source,
        "provider_model_missing_reason": first_text(
            task_metadata.get("provider_model_missing_reason"),
            dispatch_metadata.get("provider_model_missing_reason"),
            identity_metadata.get("provider_model_missing_reason"),
            "provider_execution_completed_without_actual_served_runtime_evidence",
        ),
    }


def _failure_no_provider_execution(failure_code: str) -> dict[str, Any]:
    normalized = str(failure_code or "").strip()
    reasons = {
        "dispatch_dropoff": "dispatch_dropoff_before_worker_execution",
        "claim_timeout": "claim_timeout_before_worker_execution",
    }
    reason = reasons.get(normalized)
    if not reason:
        return {}
    return {
        "provider_execution": False,
        "provider_model_applicability": "not_applicable",
        "provider_model_truth_source": (
            f"runtime_lifecycle.{normalized}_no_provider_execution"
        ),
        "no_provider_model_reason": reason,
    }


def _is_terminal_status(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return bool(normalized) and normalized not in {
        "accepted",
        "assigned",
        "claimed",
        "created",
        "in_progress",
        "pending",
        "queued",
        "running",
        "started",
        "submitted",
    }


def _terminal_unproven_provider_execution(*, status: str) -> dict[str, Any]:
    if not _is_terminal_status(status):
        return {}
    return {
        "provider_execution": True,
        "provider_model_applicability": "actual_served_unproven",
        "provider_model_truth_source": "runtime_lifecycle.provider_execution_unproven",
        "provider_model_missing_reason": (
            "terminal_receipt_missing_actual_served_or_no_provider_evidence"
        ),
    }


def _pending_provider_execution(*, status: str) -> dict[str, Any]:
    if _is_terminal_status(status):
        return {}
    return {
        "provider_execution": "pending",
        "provider_model_applicability": "pending_execution",
        "provider_model_truth_source": "runtime_lifecycle.provider_execution_pending",
        "provider_model_pending_reason": "worker_execution_not_terminal",
    }


def _has_served_provider_model(route: dict[str, Any]) -> bool:
    provider = any(
        route.get(key)
        for key in (
            "actual_served_provider",
            "served_provider",
            "actual_provider",
            "provider_served",
        )
    )
    model = any(
        route.get(key)
        for key in (
            "actual_served_model",
            "served_model",
            "actual_model",
            "model_served",
        )
    )
    return provider and model
