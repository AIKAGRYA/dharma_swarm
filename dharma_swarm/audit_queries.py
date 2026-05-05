"""Governance audit queries over the ontology registry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.ontology_runtime import get_shared_registry


class ObjectSummary(TypedDict):
    id: str
    type_name: str
    created_at: str
    created_by: str
    properties: dict[str, Any]


class ProposalChain(TypedDict):
    proposal_id: str
    proposal: ObjectSummary | None
    gate_decision: ObjectSummary | None
    execution_lease: ObjectSummary | None
    outcome: ObjectSummary | None
    value_event: ObjectSummary | None
    contributions: list[ObjectSummary]


class ProposalChainRefs(TypedDict):
    proposal: str | None
    gate_decision: str | None
    execution_lease: str | None
    outcome: str | None
    value_event: str | None
    contributions: list[str]


class ProposalChainBrief(TypedDict):
    section: str
    text: str
    outcome_id: str | None


class ProposalChainAudit(TypedDict):
    proposal_id: str
    created_at: str
    status: str
    decision: str
    missing: list[str]
    action_type: str
    task_id: str
    agent_id: str
    title: str
    has_execution_lease: bool
    refs: ProposalChainRefs
    brief: ProposalChainBrief
    chain: ProposalChain


class LifecycleLinkGap(TypedDict):
    proposal_id: str
    link_name: str
    source_id: str
    source_type: str
    target_id: str
    target_type: str


class LifecycleAuditReport(TypedDict):
    schema_version: str
    generated_at: str
    cutoff_at: str
    days: int
    total_proposals: int
    complete_chains: int
    incomplete_chains: int
    blocked_chains: int
    missing_gate_decision: int
    missing_outcome: int
    missing_value_event: int
    missing_contribution: int
    with_execution_lease: int
    link_gaps: int
    by_action_type: dict[str, int]
    chains: list[ProposalChainAudit]


def recent_blocks(days: int = 7) -> list[dict[str, Any]]:
    """Return recent GateDecisionRecord rows where decision is ``block``."""
    registry = get_shared_registry(force_reload=True)
    cutoff = _cutoff(days)
    blocks: list[dict[str, Any]] = []
    for obj in registry.get_objects_by_type("GateDecisionRecord"):
        if _as_utc(obj.created_at) < cutoff:
            continue
        if str(obj.properties.get("decision") or "").lower() != "block":
            continue
        blocks.append(_summary(obj))
    return sorted(blocks, key=lambda item: item["created_at"], reverse=True)


def unrecorded_actions(days: int = 7) -> list[dict[str, Any]]:
    """Return recent ActionProposal rows without a has_gate_decision link."""
    registry = get_shared_registry(force_reload=True)
    cutoff = _cutoff(days)
    gaps: list[dict[str, Any]] = []
    for obj in registry.get_objects_by_type("ActionProposal"):
        if _as_utc(obj.created_at) < cutoff:
            continue
        linked_gates = registry.get_links(
            source_id=obj.id,
            link_name="has_gate_decision",
        )
        if linked_gates:
            continue
        if _first_by_property(registry, "GateDecisionRecord", "proposal_id", obj.id):
            continue
        gaps.append(_summary(obj))
    return sorted(gaps, key=lambda item: item["created_at"], reverse=True)


def proposal_to_outcome_chain(proposal_id: str) -> ProposalChain:
    """Walk ActionProposal -> gates -> lease -> outcome -> value -> credit."""
    registry = get_shared_registry(force_reload=True)
    return _proposal_to_outcome_chain(registry, proposal_id)


def lifecycle_chain_audit(proposal_id: str) -> ProposalChainAudit:
    """Return a compact health row for one proposal lifecycle chain."""
    registry = get_shared_registry(force_reload=True)
    return _chain_audit(_proposal_to_outcome_chain(registry, proposal_id))


def lifecycle_chain_audits(
    days: int = 7,
    *,
    limit: int | None = 50,
) -> list[ProposalChainAudit]:
    """Return recent proposal lifecycle health rows.

    ExecutionLease is reported but not required for completion because direct
    AgentRunner pipeline executions do not currently pass through orchestrator
    claim leasing.
    """
    registry = get_shared_registry(force_reload=True)
    return _lifecycle_chain_audits(registry, days, limit=limit)


def _lifecycle_chain_audits(
    registry: OntologyRegistry,
    days: int,
    *,
    limit: int | None,
) -> list[ProposalChainAudit]:
    cutoff = _cutoff(days)
    proposals = [
        obj
        for obj in registry.get_objects_by_type("ActionProposal")
        if _as_utc(obj.created_at) >= cutoff
    ]
    proposals.sort(key=lambda obj: (_as_utc(obj.created_at), obj.id), reverse=True)
    if limit is not None:
        proposals = proposals[:max(0, limit)]
    return [
        _chain_audit(_proposal_to_outcome_chain(registry, proposal.id))
        for proposal in proposals
    ]


def blocked_action_audits(
    days: int = 7,
    *,
    limit: int | None = 50,
) -> list[ProposalChainAudit]:
    """Return recent proposal chains whose gate decision blocked execution."""
    rows = [
        row
        for row in lifecycle_chain_audits(days, limit=None)
        if row["decision"] == "block"
    ]
    rows.sort(key=_chain_gate_created_at, reverse=True)
    if limit is not None:
        rows = rows[:max(0, limit)]
    return rows


def lifecycle_link_gaps(days: int = 7) -> list[LifecycleLinkGap]:
    """Return property-resolved lifecycle edges that are missing ontology links."""
    registry = get_shared_registry(force_reload=True)
    return _lifecycle_link_gaps(registry, days)


def lifecycle_audit_report(
    days: int = 7,
    *,
    limit: int | None = 50,
) -> LifecycleAuditReport:
    """Aggregate recent proposal lifecycle health for operator review."""
    registry = get_shared_registry(force_reload=True)
    return lifecycle_audit_report_for_registry(registry, days=days, limit=limit)


def lifecycle_audit_report_for_registry(
    registry: OntologyRegistry,
    days: int = 7,
    *,
    limit: int | None = 50,
) -> LifecycleAuditReport:
    """Aggregate recent proposal lifecycle health from an explicit registry."""
    all_chains = _lifecycle_chain_audits(registry, days, limit=None)
    chains = all_chains if limit is None else all_chains[:max(0, limit)]
    link_gaps = _lifecycle_link_gaps(registry, days)
    by_action_type: dict[str, int] = {}
    for row in all_chains:
        key = row["action_type"] or "unknown"
        by_action_type[key] = by_action_type.get(key, 0) + 1

    return {
        "schema_version": "telic_lifecycle_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff_at": _cutoff(days).isoformat(),
        "days": days,
        "total_proposals": len(all_chains),
        "complete_chains": sum(1 for row in all_chains if row["status"] == "complete"),
        "incomplete_chains": sum(1 for row in all_chains if row["status"] != "complete"),
        "blocked_chains": sum(1 for row in all_chains if row["decision"] == "block"),
        "missing_gate_decision": sum(
            1 for row in all_chains if "gate_decision" in row["missing"]
        ),
        "missing_outcome": sum(1 for row in all_chains if "outcome" in row["missing"]),
        "missing_value_event": sum(
            1 for row in all_chains if "value_event" in row["missing"]
        ),
        "missing_contribution": sum(
            1 for row in all_chains if "contribution" in row["missing"]
        ),
        "with_execution_lease": sum(
            1 for row in all_chains if row["has_execution_lease"]
        ),
        "link_gaps": len(link_gaps),
        "by_action_type": dict(sorted(by_action_type.items())),
        "chains": chains,
    }


def _proposal_to_outcome_chain(
    registry: OntologyRegistry,
    proposal_id: str,
) -> ProposalChain:
    proposal = registry.get_object(proposal_id)
    gate = _first_linked_object(registry, proposal_id, "has_gate_decision")
    lease = _first_linked_object(registry, proposal_id, "has_execution_lease")
    outcome = _first_linked_object(registry, proposal_id, "has_outcome")
    value_event: OntologyObj | None = None
    contributions: list[ObjectSummary] = []

    if gate is None:
        gate = _first_by_property(registry, "GateDecisionRecord", "proposal_id", proposal_id)
    if lease is None:
        lease = _first_by_property(registry, "ExecutionLease", "proposal_id", proposal_id)
    if outcome is None:
        outcome = _first_by_property(registry, "Outcome", "proposal_id", proposal_id)
    if outcome is not None:
        value_event = _first_linked_object(registry, outcome.id, "has_value_event")
        if value_event is None:
            value_event = _first_by_property(registry, "ValueEvent", "outcome_id", outcome.id)
    if value_event is not None:
        linked = registry.get_links(source_id=value_event.id, link_name="has_contribution")
        for link in linked:
            contribution = registry.get_object(link.target_id)
            if contribution is not None:
                contributions.append(_summary(contribution))
        if not contributions:
            contributions = [
                _summary(obj)
                for obj in registry.get_objects_by_type("Contribution")
                if obj.properties.get("value_event_id") == value_event.id
            ]

    return {
        "proposal_id": proposal_id,
        "proposal": _summary(proposal) if proposal is not None else None,
        "gate_decision": _summary(gate) if gate is not None else None,
        "execution_lease": _summary(lease) if lease is not None else None,
        "outcome": _summary(outcome) if outcome is not None else None,
        "value_event": _summary(value_event) if value_event is not None else None,
        "contributions": sorted(
            contributions,
            key=lambda item: item["created_at"],
        ),
    }


def _chain_audit(chain: ProposalChain) -> ProposalChainAudit:
    proposal = chain["proposal"]
    gate = chain["gate_decision"]
    outcome = chain["outcome"]
    value_event = chain["value_event"]
    contributions = chain["contributions"]

    missing: list[str] = []
    if proposal is None:
        missing.append("proposal")
    if gate is None:
        missing.append("gate_decision")
    if outcome is None:
        missing.append("outcome")
    if value_event is None:
        missing.append("value_event")
    if not contributions:
        missing.append("contribution")

    proposal_props = proposal["properties"] if proposal is not None else {}
    gate_props = gate["properties"] if gate is not None else {}
    decision = str(gate_props.get("decision") or "").lower()
    outcome_id = outcome["id"] if outcome is not None else None

    return {
        "proposal_id": chain["proposal_id"],
        "created_at": proposal["created_at"] if proposal is not None else "",
        "status": "complete" if not missing else "incomplete",
        "decision": decision,
        "missing": missing,
        "action_type": str(proposal_props.get("action_type") or ""),
        "task_id": str(proposal_props.get("task_id") or ""),
        "agent_id": str(proposal_props.get("agent_id") or ""),
        "title": str(proposal_props.get("title") or ""),
        "has_execution_lease": chain["execution_lease"] is not None,
        "refs": {
            "proposal": _ref(proposal),
            "gate_decision": _ref(gate),
            "execution_lease": _ref(chain["execution_lease"]),
            "outcome": _ref(outcome),
            "value_event": _ref(value_event),
            "contributions": [_ref(row) or "" for row in contributions],
        },
        "brief": _chain_brief(
            title=str(proposal_props.get("title") or chain["proposal_id"]),
            agent_id=str(proposal_props.get("agent_id") or ""),
            decision=decision,
            gate_reason=str(gate_props.get("reason") or ""),
            missing=missing,
            outcome_id=outcome_id,
        ),
        "chain": chain,
    }


def _ref(obj: ObjectSummary | None) -> str | None:
    if obj is None:
        return None
    return f"{obj['type_name']}/{obj['id']}"


def _chain_brief(
    *,
    title: str,
    agent_id: str,
    decision: str,
    gate_reason: str,
    missing: list[str],
    outcome_id: str | None,
) -> ProposalChainBrief:
    actor = f" by {agent_id}" if agent_id else ""
    if decision == "block":
        reason = f": {gate_reason}" if gate_reason else ""
        return {
            "section": "Gate Blocks",
            "text": f"Blocked {title}{actor}{reason}",
            "outcome_id": outcome_id,
        }
    if missing:
        return {
            "section": "Lifecycle Breakages",
            "text": f"Lifecycle gap for {title}{actor}: missing {', '.join(missing)}",
            "outcome_id": outcome_id,
        }
    return {
        "section": "Lifecycle Signals",
        "text": f"Complete lifecycle for {title}{actor}",
        "outcome_id": outcome_id,
    }


def _lifecycle_link_gaps(
    registry: OntologyRegistry,
    days: int,
) -> list[LifecycleLinkGap]:
    cutoff = _cutoff(days)
    gaps: list[LifecycleLinkGap] = []
    proposals = [
        obj
        for obj in registry.get_objects_by_type("ActionProposal")
        if _as_utc(obj.created_at) >= cutoff
    ]
    for proposal in proposals:
        proposal_id = proposal.id
        gate = _first_by_property(registry, "GateDecisionRecord", "proposal_id", proposal_id)
        if gate is not None:
            _append_link_gap_if_missing(
                registry,
                gaps,
                proposal_id=proposal_id,
                link_name="has_gate_decision",
                source=proposal,
                target=gate,
            )

        lease = _first_by_property(registry, "ExecutionLease", "proposal_id", proposal_id)
        if lease is not None:
            _append_link_gap_if_missing(
                registry,
                gaps,
                proposal_id=proposal_id,
                link_name="has_execution_lease",
                source=proposal,
                target=lease,
            )

        outcome = _first_by_property(registry, "Outcome", "proposal_id", proposal_id)
        if outcome is None:
            continue
        _append_link_gap_if_missing(
            registry,
            gaps,
            proposal_id=proposal_id,
            link_name="has_outcome",
            source=proposal,
            target=outcome,
        )

        value_event = _first_by_property(registry, "ValueEvent", "outcome_id", outcome.id)
        if value_event is None:
            continue
        _append_link_gap_if_missing(
            registry,
            gaps,
            proposal_id=proposal_id,
            link_name="has_value_event",
            source=outcome,
            target=value_event,
        )

        for contribution in sorted(
            (
                obj
                for obj in registry.get_objects_by_type("Contribution")
                if obj.properties.get("value_event_id") == value_event.id
            ),
            key=lambda obj: (_as_utc(obj.created_at), obj.id),
        ):
            _append_link_gap_if_missing(
                registry,
                gaps,
                proposal_id=proposal_id,
                link_name="has_contribution",
                source=value_event,
                target=contribution,
            )
    return sorted(gaps, key=lambda row: (row["proposal_id"], row["link_name"]))


def _append_link_gap_if_missing(
    registry: OntologyRegistry,
    gaps: list[LifecycleLinkGap],
    *,
    proposal_id: str,
    link_name: str,
    source: OntologyObj,
    target: OntologyObj,
) -> None:
    if registry.get_links(
        source_id=source.id,
        target_id=target.id,
        link_name=link_name,
    ):
        return
    gaps.append(
        {
            "proposal_id": proposal_id,
            "link_name": link_name,
            "source_id": source.id,
            "source_type": source.type_name,
            "target_id": target.id,
            "target_type": target.type_name,
        }
    )


def _chain_gate_created_at(row: ProposalChainAudit) -> datetime:
    gate = row["chain"]["gate_decision"]
    if gate is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _as_utc(gate["created_at"])


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(0, days))


def _as_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _summary(obj: OntologyObj) -> ObjectSummary:
    return {
        "id": obj.id,
        "type_name": obj.type_name,
        "created_at": _as_utc(obj.created_at).isoformat(),
        "created_by": obj.created_by,
        "properties": dict(obj.properties),
    }


def _first_linked_object(
    registry: OntologyRegistry,
    source_id: str,
    link_name: str,
) -> OntologyObj | None:
    links = registry.get_links(source_id=source_id, link_name=link_name)
    linked = [registry.get_object(link.target_id) for link in links]
    objects = [obj for obj in linked if obj is not None]
    if not objects:
        return None
    return sorted(objects, key=lambda obj: (_as_utc(obj.created_at), obj.id))[0]


def _first_by_property(
    registry: OntologyRegistry,
    type_name: str,
    property_name: str,
    value: str,
) -> OntologyObj | None:
    matches = [
        obj
        for obj in registry.get_objects_by_type(type_name)
        if obj.properties.get(property_name) == value
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda obj: (_as_utc(obj.created_at), obj.id))[0]
