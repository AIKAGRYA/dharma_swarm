"""Fourfold Action Warrant gate.

This module gives high-authority actions a deterministic pre-action contract:
prove enough context was gathered, name the active capabilities, and produce a
compact three-paragraph warrant before the action is allowed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.models import GateDecision, _new_id, _utc_now


MIN_EVIDENCE_FILES = 50
REQUIRED_EVIDENCE_CATEGORIES = frozenset(
    {"root", "code", "tests", "history", "tools"}
)

_TRIGGER_KEYWORDS = {
    "autonomous": "autonomy",
    "dispatch": "dispatch_authority",
    "execute": "execution_authority",
    "governance": "governance_impact",
    "gate": "governance_impact",
    "hook": "hook_or_tooling",
    "main": "main_branch_or_release",
    "merge": "main_branch_or_release",
    "mcp": "external_tool_use",
    "network": "external_tool_use",
    "policy": "governance_impact",
    "push": "main_branch_or_release",
    "spawn": "cross_agent_authority",
    "tool": "external_tool_use",
    "worktree": "code_mutation",
    "write": "code_mutation",
}

_METADATA_TRIGGERS = {
    "is_significant_action": "significant_action",
    "writes_code": "code_mutation",
    "mutates_repo": "code_mutation",
    "governance_impact": "governance_impact",
    "external_tool_use": "external_tool_use",
    "network_access": "external_tool_use",
    "cross_agent_authority": "cross_agent_authority",
    "dispatch_authority": "dispatch_authority",
    "main_branch": "main_branch_or_release",
    "operator_visible": "operator_visible",
}


class EvidenceItem(BaseModel):
    """One file, tool, or memory surface inspected before action."""

    path: str
    category: str
    theme: str = ""
    why: str = ""


class CapabilityInventory(BaseModel):
    """Capabilities available to the acting agent at decision time."""

    skills: list[str] = Field(default_factory=list)
    mcp_tools: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)

    @property
    def total_count(self) -> int:
        return (
            len(self.skills)
            + len(self.mcp_tools)
            + len(self.plugins)
            + len(self.hooks)
        )


class ActionWarrantRequest(BaseModel):
    """Input facts for evaluating whether an action may proceed."""

    title: str
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    capabilities: CapabilityInventory = Field(default_factory=CapabilityInventory)
    zeitgeist_signal_ids: list[str] = Field(default_factory=list)
    integrated_vision: str = ""
    connection_map: str = ""
    meaningful_action: str = ""


class FourfoldActionWarrant(BaseModel):
    """Gate result for a proposed high-authority action."""

    warrant_id: str = Field(default_factory=_new_id)
    title: str
    required: bool
    decision: GateDecision
    trigger_reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    evidence_categories: list[str] = Field(default_factory=list)
    capabilities: CapabilityInventory = Field(default_factory=CapabilityInventory)
    zeitgeist_signal_ids: list[str] = Field(default_factory=list)
    four_levels: dict[str, str] = Field(default_factory=dict)
    integrated_vision: str = ""
    connection_map: str = ""
    meaningful_action: str = ""
    created_at: datetime = Field(default_factory=_utc_now)

    @property
    def allowed(self) -> bool:
        return self.decision is GateDecision.ALLOW


def trigger_reasons_for_action(
    title: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic reasons that the action needs a warrant."""

    reasons: set[str] = set()
    meta = metadata or {}
    for key, reason in _METADATA_TRIGGERS.items():
        if bool(meta.get(key)):
            reasons.add(reason)

    autonomy = str(meta.get("autonomy_level") or "").strip().lower()
    if autonomy in {"aggressive", "full", "self_authorized", "autonomous"}:
        reasons.add("high_autonomy")

    text = f"{title}\n{description}".lower()
    for keyword, reason in _TRIGGER_KEYWORDS.items():
        if keyword in text and not _keyword_negated(text, keyword):
            reasons.add(reason)

    return sorted(reasons)


def requires_fourfold_warrant(
    title: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Whether the action must pass the Fourfold Action Warrant gate."""

    return bool(trigger_reasons_for_action(title, description, metadata))


def build_fourfold_action_warrant(
    request: ActionWarrantRequest,
    *,
    min_evidence_files: int = MIN_EVIDENCE_FILES,
) -> FourfoldActionWarrant:
    """Evaluate a request and return a hard allow/block/review decision."""

    reasons = trigger_reasons_for_action(
        request.title,
        request.description,
        request.metadata,
    )
    required = bool(reasons)
    categories = sorted({item.category for item in request.evidence if item.category})
    unique_paths = {str(Path(item.path)) for item in request.evidence if item.path}

    blockers: list[str] = []
    if required and len(unique_paths) < min_evidence_files:
        blockers.append(
            f"evidence_files<{min_evidence_files} ({len(unique_paths)})"
        )
    if required:
        missing = sorted(REQUIRED_EVIDENCE_CATEGORIES - set(categories))
        if missing:
            blockers.append("missing_evidence_categories:" + ",".join(missing))
    if required and request.capabilities.total_count == 0:
        blockers.append("missing_capability_inventory")

    narrative_missing = _missing_narrative_fields(request)
    if required and narrative_missing:
        blockers.append("missing_warrant_paragraphs:" + ",".join(narrative_missing))

    decision = GateDecision.ALLOW
    if blockers:
        decision = GateDecision.BLOCK
    elif required and not request.zeitgeist_signal_ids:
        decision = GateDecision.REVIEW

    return FourfoldActionWarrant(
        title=request.title,
        required=required,
        decision=decision,
        trigger_reasons=reasons,
        blockers=blockers,
        evidence_count=len(unique_paths),
        evidence_categories=categories,
        capabilities=request.capabilities,
        zeitgeist_signal_ids=list(request.zeitgeist_signal_ids),
        four_levels=_four_levels(request),
        integrated_vision=request.integrated_vision.strip(),
        connection_map=request.connection_map.strip(),
        meaningful_action=request.meaningful_action.strip(),
    )


def _missing_narrative_fields(request: ActionWarrantRequest) -> list[str]:
    fields = {
        "integrated_vision": request.integrated_vision,
        "connection_map": request.connection_map,
        "meaningful_action": request.meaningful_action,
    }
    return [name for name, value in fields.items() if len(value.strip()) < 80]


def _keyword_negated(text: str, keyword: str) -> bool:
    plural = f"{keyword}s"
    negations = (
        f"no {keyword}",
        f"no {plural}",
        f"no external {keyword}",
        f"no external {plural}",
        f"not {keyword}",
        f"not {plural}",
        f"without {keyword}",
        f"without {plural}",
        f"does not {keyword}",
        f"does not {plural}",
        f"do not {keyword}",
        f"do not {plural}",
    )
    return any(phrase in text for phrase in negations)


def _four_levels(request: ActionWarrantRequest) -> dict[str, str]:
    return {
        "vision": request.integrated_vision.strip(),
        "authority": "; ".join(trigger_reasons_for_action(
            request.title,
            request.description,
            request.metadata,
        )),
        "relationship": request.connection_map.strip(),
        "precision": request.meaningful_action.strip(),
    }


__all__ = [
    "ActionWarrantRequest",
    "CapabilityInventory",
    "EvidenceItem",
    "FourfoldActionWarrant",
    "MIN_EVIDENCE_FILES",
    "REQUIRED_EVIDENCE_CATEGORIES",
    "build_fourfold_action_warrant",
    "requires_fourfold_warrant",
    "trigger_reasons_for_action",
]
