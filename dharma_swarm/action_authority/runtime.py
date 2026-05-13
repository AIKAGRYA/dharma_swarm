"""Runtime helpers for applying the Action Authority Gate at side effects."""

from __future__ import annotations

from typing import Any

from dharma_swarm.action_authority.gate import (
    ActionAuthorityDecision,
    ActionAuthorityMode,
    ActionAuthorityRequest,
    AuthoritySurface,
    AuthorityTier,
    build_action_authority_request,
    evaluate_action_authority,
)
from dharma_swarm.models import GateCheckResult, GateDecision, GateResult


def check_action_authority(
    *,
    title: str,
    surface: AuthoritySurface,
    tier: AuthorityTier | None = None,
    action_type: str = "",
    intent: str = "",
    content: str = "",
    target_paths: tuple[str, ...] = (),
    requested_tools: tuple[str, ...] = (),
    command: str | None = None,
    network_targets: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    mode: ActionAuthorityMode | str | None = None,
    **extra: Any,
) -> ActionAuthorityDecision:
    """Build and evaluate an authority request for a runtime call site."""

    request = build_action_authority_request(
        title=title,
        surface=surface,
        tier=tier,
        action_type=action_type,
        intent=intent,
        content=content,
        target_paths=target_paths,
        requested_tools=requested_tools,
        command=command,
        network_targets=network_targets,
        metadata=metadata,
        **extra,
    )
    return evaluate_action_authority(request, mode=mode)


def decision_to_gate_check(decision: ActionAuthorityDecision) -> GateCheckResult:
    """Convert an authority decision into the existing gate result shape."""

    return GateCheckResult(
        decision=decision.effective_decision,
        gate="ACTION_AUTHORITY" if decision.effective_decision is not GateDecision.ALLOW else "",
        reason=decision.reason,
        gate_results={
            "ACTION_AUTHORITY": (_gate_result_for_decision(decision), decision.reason)
        },
    )


def merge_authority_gate_result(
    gate_result: GateCheckResult,
    decision: ActionAuthorityDecision,
) -> GateCheckResult:
    """Attach ACTION_AUTHORITY to an existing Telos gate result."""

    merged_gate_results = dict(gate_result.gate_results)
    merged_gate_results["ACTION_AUTHORITY"] = (
        _gate_result_for_decision(decision),
        decision.reason,
    )
    effective_decision = _dominant_decision(
        gate_result.decision,
        decision.effective_decision,
    )
    reason = gate_result.reason
    if decision.effective_decision is GateDecision.BLOCK:
        reason = decision.reason
    elif gate_result.decision is GateDecision.ALLOW and decision.effective_decision is GateDecision.REVIEW:
        reason = decision.reason
    return GateCheckResult(
        decision=effective_decision,
        gate=gate_result.gate or (
            "ACTION_AUTHORITY"
            if decision.effective_decision is not GateDecision.ALLOW
            else ""
        ),
        reason=reason,
        gate_results=merged_gate_results,
    )


def authority_block_message(decision: ActionAuthorityDecision) -> str:
    """Return a stable operator-facing block message."""

    tier = decision.component_results.get("authority_tier", "")
    surface = decision.component_results.get("authority_surface", "")
    detail = f" tier={tier}" if tier else ""
    detail += f" surface={surface}" if surface else ""
    return f"ACTION AUTHORITY BLOCK{detail}: {decision.reason}"


def request_summary(request: ActionAuthorityRequest) -> dict[str, Any]:
    """Small serializable summary for call-site metadata and tests."""

    return {
        "action_id": request.action_id,
        "surface": request.surface.value,
        "tier": request.tier.value,
        "title": request.title,
        "target_paths": list(request.target_paths),
        "requested_tools": list(request.requested_tools),
    }


def _dominant_decision(left: GateDecision, right: GateDecision) -> GateDecision:
    if GateDecision.BLOCK in {left, right}:
        return GateDecision.BLOCK
    if GateDecision.REVIEW in {left, right}:
        return GateDecision.REVIEW
    return GateDecision.ALLOW


def _gate_result_for_decision(decision: ActionAuthorityDecision) -> GateResult:
    if decision.blocked or decision.effective_decision is GateDecision.BLOCK:
        return GateResult.FAIL
    if decision.would_block or decision.raw_decision is not GateDecision.ALLOW:
        return GateResult.WARN
    return GateResult.PASS
