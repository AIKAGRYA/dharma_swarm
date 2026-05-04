"""Pure Action Authority Gate models and classifier.

This module has no runtime call-site wiring. It classifies a proposed action,
evaluates existing Fourfold/PolicyCompiler warrant semantics when requested,
and returns a shadow/enforce decision object that callers may later persist.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

from dharma_swarm.fourfold_action_warrant import (
    FourfoldActionWarrant,
    trigger_reasons_for_action,
)
from dharma_swarm.models import GateDecision, _new_id, _utc_now
from dharma_swarm.policy_compiler import (
    FOURFOLD_ACTION_WARRANT_METADATA_KEY,
    Policy,
)

ACTION_AUTHORITY_GATE_ENV = "DHARMA_ACTION_AUTHORITY_GATE"


class ActionAuthorityMode(str, Enum):
    """Runtime mode for the action authority gate."""

    OFF = "off"
    SHADOW = "shadow"
    ENFORCE = "enforce"


class AuthoritySurface(str, Enum):
    """Known runtime surfaces that can request authority."""

    READ_ONLY = "read_only"
    DISPATCH = "dispatch"
    AGENT_TOOL = "agent_tool"
    AUTONOMOUS_TOOL = "autonomous_tool"
    TOOL_REGISTRY = "tool_registry"
    API_TOOL = "api_tool"
    CRON_DAEMON = "cron_daemon"
    SANDBOX_RUNTIME = "sandbox_runtime"
    ONTOLOGY_ACTION = "ontology_action"
    DIFF_SELF_IMPROVE = "diff_self_improve"
    EXTERNAL_BRIDGE = "external_bridge"
    OPERATOR_UI = "operator_ui"


class AuthorityTier(str, Enum):
    """Authority tier for a proposed action."""

    READ_ONLY = "read_only"
    LOCAL_SIDE_EFFECT = "local_side_effect"
    REPO_MUTATION = "repo_mutation"
    EXECUTION = "execution"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    CROSS_AGENT_DISPATCH = "cross_agent_dispatch"
    GOVERNANCE_MUTATION = "governance_mutation"
    RELEASE_OR_MAIN = "release_or_main"


class AuthorityEvidence(BaseModel):
    """One evidence item attached to an authority decision."""

    source: str
    kind: str
    summary: str = ""
    paths: tuple[str, ...] = ()
    category: str = ""
    theme: str = ""
    why_it_matters: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilitySnapshot(BaseModel):
    """Capability state visible at decision time."""

    skills: tuple[str, ...] = ()
    mcp_tools: tuple[str, ...] = ()
    plugins: tuple[str, ...] = ()
    hooks: tuple[str, ...] = ()
    branch: str = ""
    worktree_status: str = ""
    gitnexus_status: str = ""
    contextplus_status: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionAuthorityRequest(BaseModel):
    """Normalized action authority request."""

    action_id: str = Field(default_factory=_new_id)
    actor_id: str = ""
    actor_type: str = "agent"
    runtime_type: str = "local"
    task_id: str | None = None
    surface: AuthoritySurface = AuthoritySurface.READ_ONLY
    tier: AuthorityTier = AuthorityTier.READ_ONLY
    action_type: str = ""
    title: str
    intent: str = ""
    content: str = ""
    target_paths: tuple[str, ...] = ()
    requested_tools: tuple[str, ...] = ()
    command: str | None = None
    network_targets: tuple[str, ...] = ()
    autonomy_level: str | None = None
    trust_mode: str | None = None
    think_phase: str | None = None
    spec_ref: str | None = None
    requirement_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: tuple[AuthorityEvidence, ...] = ()
    capability_snapshot: CapabilitySnapshot = Field(default_factory=CapabilitySnapshot)
    fourfold_warrant: FourfoldActionWarrant | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)


class ActionAuthorityDecision(BaseModel):
    """Decision returned by the pure action authority gate."""

    decision_id: str = Field(default_factory=_new_id)
    action_id: str
    proposal_id: str | None = None
    mode: ActionAuthorityMode
    raw_decision: GateDecision
    effective_decision: GateDecision
    would_block: bool
    blocked: bool
    reason: str = ""
    component_results: dict[str, Any] = Field(default_factory=dict)
    gate_results: dict[str, Any] = Field(default_factory=dict)
    guardrail_results: dict[str, Any] = Field(default_factory=dict)
    trigger_reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    warrant_id: str | None = None
    semantic_verdict: dict[str, Any] | None = None
    policy_decision: dict[str, Any] | None = None
    witness_reroutes: tuple[dict[str, Any], ...] = ()
    duration_ms: int = 0
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)


HIGH_AUTHORITY_TIERS = frozenset(
    {
        AuthorityTier.REPO_MUTATION,
        AuthorityTier.EXECUTION,
        AuthorityTier.EXTERNAL_SIDE_EFFECT,
        AuthorityTier.CROSS_AGENT_DISPATCH,
        AuthorityTier.GOVERNANCE_MUTATION,
        AuthorityTier.RELEASE_OR_MAIN,
    }
)


def build_action_authority_request(
    *,
    title: str,
    surface: AuthoritySurface = AuthoritySurface.READ_ONLY,
    tier: AuthorityTier | None = None,
    action_type: str = "",
    intent: str = "",
    content: str = "",
    target_paths: tuple[str, ...] = (),
    requested_tools: tuple[str, ...] = (),
    command: str | None = None,
    network_targets: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    fourfold_warrant: FourfoldActionWarrant | None = None,
    **extra: Any,
) -> ActionAuthorityRequest:
    """Build a request and classify its tier if one is not supplied."""

    metadata = dict(metadata or {})
    resolved_tier = tier or classify_authority_tier(
        title=title,
        content=content or intent,
        action_type=action_type,
        surface=surface,
        target_paths=target_paths,
        requested_tools=requested_tools,
        command=command,
        network_targets=network_targets,
        metadata=metadata,
    )
    return ActionAuthorityRequest(
        title=title,
        surface=surface,
        tier=resolved_tier,
        action_type=action_type,
        intent=intent,
        content=content,
        target_paths=target_paths,
        requested_tools=requested_tools,
        command=command,
        network_targets=network_targets,
        metadata=metadata,
        fourfold_warrant=fourfold_warrant,
        **extra,
    )


def classify_authority_tier(
    *,
    title: str,
    content: str = "",
    action_type: str = "",
    surface: AuthoritySurface = AuthoritySurface.READ_ONLY,
    target_paths: tuple[str, ...] = (),
    requested_tools: tuple[str, ...] = (),
    command: str | None = None,
    network_targets: tuple[str, ...] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AuthorityTier:
    """Classify an action into the narrowest authority tier that fits."""

    metadata = metadata or {}
    explicit = _coerce_tier(metadata.get("authority_tier"))
    if explicit is not None:
        return explicit

    text = " ".join(
        [title, content, action_type, command or "", " ".join(target_paths)]
    ).lower()
    tools = {tool.lower() for tool in requested_tools}

    if bool(metadata.get("main_branch")) or _contains_any(
        text, ("merge", "release", "deploy", "git push", "push main")
    ):
        return AuthorityTier.RELEASE_OR_MAIN
    if bool(metadata.get("governance_impact")) or _is_governance_text(text):
        return AuthorityTier.GOVERNANCE_MUTATION
    if surface in {AuthoritySurface.DISPATCH, AuthoritySurface.EXTERNAL_BRIDGE}:
        return AuthorityTier.CROSS_AGENT_DISPATCH
    if bool(metadata.get("cross_agent_authority")) or _contains_any(
        text, ("spawn", "dispatch", "delegate", "assign worker")
    ):
        return AuthorityTier.CROSS_AGENT_DISPATCH
    if network_targets or bool(metadata.get("network_access")):
        return AuthorityTier.EXTERNAL_SIDE_EFFECT
    if tools & {"github", "web_search", "fetch_url", "publish", "mcp"}:
        return AuthorityTier.EXTERNAL_SIDE_EFFECT
    if command or surface in {
        AuthoritySurface.CRON_DAEMON,
        AuthoritySurface.SANDBOX_RUNTIME,
    }:
        return AuthorityTier.EXECUTION
    if tools & {"shell_exec", "bash", "run_command", "python", "subprocess"}:
        return AuthorityTier.EXECUTION
    if bool(metadata.get("mutates_repo")) or bool(metadata.get("writes_code")):
        return AuthorityTier.REPO_MUTATION
    if target_paths or tools & {"write_file", "edit_file", "apply_patch"}:
        return AuthorityTier.REPO_MUTATION
    if bool(metadata.get("local_side_effect")):
        return AuthorityTier.LOCAL_SIDE_EFFECT
    return AuthorityTier.READ_ONLY


def evaluate_action_authority(
    request: ActionAuthorityRequest,
    *,
    mode: ActionAuthorityMode | str | None = None,
) -> ActionAuthorityDecision:
    """Evaluate a request without mutating runtime behavior."""

    resolved_mode = _resolve_mode(mode)
    if resolved_mode is ActionAuthorityMode.OFF:
        return _decision(
            request,
            mode=resolved_mode,
            raw=GateDecision.ALLOW,
            effective=GateDecision.ALLOW,
            reason="action authority gate disabled",
        )

    metadata = _authority_metadata(request)
    trigger_reasons = tuple(
        trigger_reasons_for_action(request.title, request.content or request.intent, metadata)
    )
    warrant_required = request.tier in HIGH_AUTHORITY_TIERS or bool(trigger_reasons)
    raw_decision = GateDecision.ALLOW
    reason = "authority not required"
    blockers: list[str] = []
    warnings: list[str] = []
    component_results: dict[str, Any] = {
        "authority_tier": request.tier.value,
        "authority_surface": request.surface.value,
        "warrant_required": warrant_required,
    }
    policy_payload: dict[str, Any] | None = None

    if warrant_required:
        policy_decision = Policy().check_action(
            request.title,
            request.content or request.intent,
            action_metadata=metadata,
            enforce_fourfold_warrant=True,
        )
        policy_payload = {
            "allowed": policy_decision.allowed,
            "reason": policy_decision.reason,
            "violated_rules": [rule.source for rule in policy_decision.violated_rules],
            "warnings": [rule.source for rule in policy_decision.warnings],
        }
        component_results["fourfold_policy"] = policy_payload
        if not policy_decision.allowed:
            raw_decision = GateDecision.BLOCK
            reason = policy_decision.reason or "fourfold action warrant blocked"
            blockers.append(reason)
        else:
            reason = "fourfold action warrant satisfied"

    ptr_component = _ptr_negative_component(metadata)
    if ptr_component is not None:
        component_results["ptr"] = ptr_component
        if ptr_component["negative"] and raw_decision is GateDecision.ALLOW:
            raw_decision = GateDecision.REVIEW
            reason = ptr_component["reason"]
            warnings.append(ptr_component["reason"])

    effective_decision = raw_decision
    if resolved_mode is ActionAuthorityMode.SHADOW:
        effective_decision = GateDecision.ALLOW

    return _decision(
        request,
        mode=resolved_mode,
        raw=raw_decision,
        effective=effective_decision,
        reason=reason,
        trigger_reasons=trigger_reasons,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        component_results=component_results,
        policy_decision=policy_payload,
    )


def _decision(
    request: ActionAuthorityRequest,
    *,
    mode: ActionAuthorityMode,
    raw: GateDecision,
    effective: GateDecision,
    reason: str,
    trigger_reasons: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    component_results: dict[str, Any] | None = None,
    policy_decision: dict[str, Any] | None = None,
) -> ActionAuthorityDecision:
    would_block = mode is ActionAuthorityMode.SHADOW and raw is GateDecision.BLOCK
    blocked = mode is ActionAuthorityMode.ENFORCE and effective is GateDecision.BLOCK
    gate_result: Literal["PASS", "WARN", "FAIL"]
    if raw is GateDecision.ALLOW:
        gate_result = "PASS"
    elif raw is GateDecision.BLOCK and mode is ActionAuthorityMode.ENFORCE:
        gate_result = "FAIL"
    else:
        gate_result = "WARN"

    return ActionAuthorityDecision(
        action_id=request.action_id,
        mode=mode,
        raw_decision=raw,
        effective_decision=effective,
        would_block=would_block,
        blocked=blocked,
        reason=reason,
        component_results=component_results or {},
        gate_results={
            "ACTION_AUTHORITY": {
                "result": gate_result,
                "reason": reason,
                "mode": mode.value,
                "raw_decision": raw.value,
                "effective_decision": effective.value,
            }
        },
        trigger_reasons=trigger_reasons,
        blockers=blockers,
        warnings=warnings,
        evidence_refs=tuple(e.source for e in request.evidence),
        warrant_id=(
            request.fourfold_warrant.warrant_id
            if request.fourfold_warrant is not None
            else None
        ),
        policy_decision=policy_decision,
        provenance={"authority_gate_version": "aag.pr1"},
    )


def _authority_metadata(request: ActionAuthorityRequest) -> dict[str, Any]:
    metadata = dict(request.metadata)
    metadata["authority_surface"] = request.surface.value
    metadata["authority_tier"] = request.tier.value
    metadata["is_significant_action"] = request.tier in HIGH_AUTHORITY_TIERS
    metadata["autonomy_level"] = request.autonomy_level or metadata.get("autonomy_level")
    if request.fourfold_warrant is not None:
        metadata[FOURFOLD_ACTION_WARRANT_METADATA_KEY] = request.fourfold_warrant
    if request.tier is AuthorityTier.REPO_MUTATION:
        metadata["mutates_repo"] = True
        metadata["writes_code"] = True
    elif request.tier is AuthorityTier.EXTERNAL_SIDE_EFFECT:
        metadata["external_tool_use"] = True
        metadata["network_access"] = True
    elif request.tier is AuthorityTier.CROSS_AGENT_DISPATCH:
        metadata["cross_agent_authority"] = True
        metadata["dispatch_authority"] = True
    elif request.tier is AuthorityTier.GOVERNANCE_MUTATION:
        metadata["governance_impact"] = True
    elif request.tier is AuthorityTier.RELEASE_OR_MAIN:
        metadata["main_branch"] = True
        metadata["mutates_repo"] = True
    return metadata


def _resolve_mode(mode: ActionAuthorityMode | str | None) -> ActionAuthorityMode:
    if isinstance(mode, ActionAuthorityMode):
        return mode
    if isinstance(mode, str) and mode:
        try:
            return ActionAuthorityMode(mode.strip().lower())
        except ValueError:
            return ActionAuthorityMode.OFF
    raw = os.getenv(ACTION_AUTHORITY_GATE_ENV, "").strip().lower()
    if raw in {"1", "true", "yes", "on", "shadow"}:
        return ActionAuthorityMode.SHADOW
    if raw in {"enforce", "block"}:
        return ActionAuthorityMode.ENFORCE
    return ActionAuthorityMode.OFF


def _ptr_negative_component(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    ptr = metadata.get("ptr_score", metadata.get("ptr"))
    if not isinstance(ptr, Mapping):
        return None
    verdict = str(ptr.get("verdict", "")).upper()
    authoritative = bool(ptr.get("authoritative", False))
    caps = [str(cap) for cap in ptr.get("caps", []) if isinstance(cap, str)]
    negative = (
        verdict in {"HOLD", "INSUFFICIENT_EVIDENCE", "REPAIR_MODE"}
        or not authoritative
        or "low_coverage" in caps
    )
    return {
        "verdict": verdict,
        "authoritative": authoritative,
        "caps": caps,
        "negative": negative,
        "reason": f"ptr_negative_evidence:{verdict or 'unknown'}",
    }


def _coerce_tier(value: Any) -> AuthorityTier | None:
    if isinstance(value, AuthorityTier):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return AuthorityTier(value)
    except ValueError:
        return None


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _is_governance_text(text: str) -> bool:
    return _contains_any(
        text,
        (
            "governance",
            "policy",
            "telos",
            "warrant",
            "authority",
            "pre-commit",
            "semgrep",
            "module budget",
            "docs/governance",
            "policy_compiler",
            "telos_gates",
        ),
    )
