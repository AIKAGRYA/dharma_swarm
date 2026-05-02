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
        gaps.append(_summary(obj))
    return sorted(gaps, key=lambda item: item["created_at"], reverse=True)


def proposal_to_outcome_chain(proposal_id: str) -> ProposalChain:
    """Walk ActionProposal -> gates -> lease -> outcome -> value -> credit."""
    registry = get_shared_registry(force_reload=True)
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
