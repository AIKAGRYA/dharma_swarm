"""Write-through ontology seed for the Empty Quadrant hypernode."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.hypernode import (
    ACTION_PROPOSAL_ID,
    CLAIM_ID,
    CONTRIBUTION_ID,
    COUNCIL_VERDICT_ID,
    DOCTRINE_ID,
    EMPTY_QUADRANT_PUBLIC_PATH,
    EVIDENCE_ID,
    EXECUTION_LEASE_ID,
    FITNESS_VECTOR_ID,
    GATE_RECORD_ID,
    HYPERNODE_ID,
    OUTCOME_ID,
    PRINCIPAL_AGENT_ID,
    PUBLIC_ARTIFACT_ID,
    QUESTION_ID,
    REVENUE_CELL_ID,
    SIGNAL_ID,
    VALUE_EVENT_ID,
    HypernodePayload,
    TypedLinkPayload,
    build_empty_quadrant_payload,
)
from dharma_swarm.models import GateDecision
from dharma_swarm.ontology import Link, OntologyObj, OntologyRegistry


class HypernodeSeedResult(BaseModel):
    payload: HypernodePayload
    objects: dict[str, str]
    links: list[TypedLinkPayload]
    errors: list[str] = Field(default_factory=list)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _put_object(
    registry: OntologyRegistry,
    obj_id: str,
    type_name: str,
    properties: dict[str, Any],
    *,
    created_by: str,
) -> tuple[OntologyObj | None, list[str]]:
    existing = registry.get_object(obj_id)
    if existing is not None and existing.type_name == type_name and existing.properties == properties:
        return existing, []
    return registry.put_object(
        OntologyObj(id=obj_id, type_name=type_name, properties=properties, created_by=created_by)
    )


def _ensure_link(
    registry: OntologyRegistry,
    link_name: str,
    source_id: str,
    target_id: str,
    *,
    created_by: str,
) -> tuple[Link | None, list[str]]:
    existing = registry.get_links(source_id=source_id, target_id=target_id, link_name=link_name)
    if existing:
        return existing[0], []
    return registry.create_link(link_name, source_id, target_id, created_by=created_by)


def _object_specs(payload: HypernodePayload, now: str) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (
            PRINCIPAL_AGENT_ID,
            "AgentIdentity",
            {"name": "dhyana", "role": "operator", "status": "idle", "is_principal": True},
        ),
        (
            PUBLIC_ARTIFACT_ID,
            "KnowledgeArtifact",
            {
                "title": "Empty Quadrant Revenue Cell public page",
                "artifact_type": "visualization",
                "domain": "dharma_swarm",
                "content": payload.thesis,
                "file_path": "dashboard/src/app/dashboard/hypernodes/empty-quadrant/page.tsx",
                "provenance": ",".join(item.id for item in payload.provenance),
                "confidence": payload.fitness_vector.auto_grade_score,
                "verified": True,
                "audience": "public",
                "published_path": payload.public_path,
                "published_at": now,
                "published_channel": "dashboard",
            },
        ),
        (
            SIGNAL_ID,
            "Signal",
            {
                "signal_id": SIGNAL_ID,
                "source": "operator_plan",
                "captured_at": now,
                "payload": payload.thesis,
                "observer_ref": "dhyana",
                "source_kind": "manual",
                "sensitivity": "public",
            },
        ),
        (
            QUESTION_ID,
            "Question",
            {
                "question_id": QUESTION_ID,
                "text": "Can dharma_swarm create market value in the high-governance welfare quadrant?",
                "opener_ref": "dhyana",
                "opened_at": now,
                "lifecycle_state": "answered",
                "domain": "revenue",
                "priority": "urgent",
            },
        ),
        (
            CLAIM_ID,
            "Claim",
            {
                "claim_id": CLAIM_ID,
                "statement": payload.thesis,
                "lifecycle_state": "accepted",
                "confidence": payload.fitness_vector.composite_score,
                "proposer_ref": "dhyana",
                "evidence_refs": [EVIDENCE_ID],
            },
        ),
        (
            EVIDENCE_ID,
            "Evidence",
            {
                "evidence_id": EVIDENCE_ID,
                "claim_ref": CLAIM_ID,
                "kind": "witness_chain",
                "direction": "supports",
                "source_artifact_ref": PUBLIC_ARTIFACT_ID,
                "attached_at": now,
                "attached_by_ref": "hypernode.seed",
                "strength": payload.fitness_vector.provenance_score,
            },
        ),
        (
            DOCTRINE_ID,
            "Doctrine",
            {
                "doctrine_id": DOCTRINE_ID,
                "text": "Revenue may serve Jagat Kalyan only when governed as trustee flow and audited against extraction drift.",
                "lifecycle_state": "draft",
                "kernel_signature": "pending-human-signature",
                "version": 1,
            },
        ),
        (
            HYPERNODE_ID,
            "Hypernode",
            {
                "hypernode_id": HYPERNODE_ID,
                "slug": payload.slug,
                "title": payload.title,
                "thesis": payload.thesis,
                "quadrant": "high_governance_welfare",
                "status": payload.fitness_vector.promotion_state,
                "public_path": payload.public_path,
                "object_chain": payload.object_chain,
                "provenance_refs": [item.id for item in payload.provenance],
                "next_actions": payload.next_actions,
            },
        ),
        (
            REVENUE_CELL_ID,
            "RevenueCell",
            {
                **payload.revenue_cell.model_dump(),
                "revenue_cell_id": REVENUE_CELL_ID,
                "hypernode_ref": HYPERNODE_ID,
            },
        ),
        (
            COUNCIL_VERDICT_ID,
            "CouncilVerdict",
            {
                **payload.council_verdict.model_dump(),
                "verdict_id": COUNCIL_VERDICT_ID,
                "hypernode_ref": HYPERNODE_ID,
                "recorded_at": now,
            },
        ),
        (
            FITNESS_VECTOR_ID,
            "FitnessVector",
            {
                **payload.fitness_vector.model_dump(),
                "fitness_id": FITNESS_VECTOR_ID,
                "hypernode_ref": HYPERNODE_ID,
            },
        ),
        (
            ACTION_PROPOSAL_ID,
            "ActionProposal",
            {
                "task_id": ACTION_PROPOSAL_ID,
                "agent_id": PRINCIPAL_AGENT_ID,
                "action_type": "manual",
                "title": "Publish Empty Quadrant hypernode surface",
                "description": payload.thesis,
                "status": "approved",
                "priority": "urgent",
            },
        ),
        (
            GATE_RECORD_ID,
            "GateDecisionRecord",
            {
                "proposal_id": ACTION_PROPOSAL_ID,
                "decision": GateDecision.ALLOW.value,
                "reason": payload.council_verdict.reason,
                "gate_results": payload.council_verdict.gate_results,
                "witness_reroutes": 1,
            },
        ),
        (
            EXECUTION_LEASE_ID,
            "ExecutionLease",
            {
                "proposal_id": ACTION_PROPOSAL_ID,
                "claim_id": CLAIM_ID,
                "agent_id": PRINCIPAL_AGENT_ID,
                "claimed_at": now,
                "claim_timeout_seconds": 3600.0,
                "claim_expires_at_epoch": 0.0,
                "dispatch_timeout_seconds": 3600.0,
                "dispatch_attempt": 1,
            },
        ),
        (
            OUTCOME_ID,
            "Outcome",
            {
                "proposal_id": ACTION_PROPOSAL_ID,
                "task_id": ACTION_PROPOSAL_ID,
                "agent_id": PRINCIPAL_AGENT_ID,
                "success": True,
                "result_summary": "Ontology-backed public hypernode artifact seeded.",
                "error": "",
                "duration_ms": 0.0,
                "fitness_score": payload.fitness_vector.composite_score,
            },
        ),
        (
            VALUE_EVENT_ID,
            "ValueEvent",
            {
                "outcome_id": OUTCOME_ID,
                "agent_id": PRINCIPAL_AGENT_ID,
                "cell_id": REVENUE_CELL_ID,
                "task_id": ACTION_PROPOSAL_ID,
                "task_type": "build",
                "behavioral_signal": payload.fitness_vector.welfare_score,
                "success_value": 1.0,
                "duration_efficiency": 1.0,
                "composite_value": payload.fitness_vector.composite_score,
                "scoring_method": payload.fitness_vector.scoring_method,
            },
        ),
        (
            CONTRIBUTION_ID,
            "Contribution",
            {
                "value_event_id": VALUE_EVENT_ID,
                "agent_id": PRINCIPAL_AGENT_ID,
                "cell_id": REVENUE_CELL_ID,
                "task_type": "build",
                "credit_share": 1.0,
                "attributed_value": payload.fitness_vector.composite_score,
            },
        ),
    ]


def _link_specs() -> list[tuple[str, str, str]]:
    return [
        ("observed_by", SIGNAL_ID, PRINCIPAL_AGENT_ID),
        ("opens_question", SIGNAL_ID, QUESTION_ID),
        ("opened_by", QUESTION_ID, PRINCIPAL_AGENT_ID),
        ("answered_by_claim", QUESTION_ID, CLAIM_ID),
        ("claim_proposed_by", CLAIM_ID, PRINCIPAL_AGENT_ID),
        ("claim_has_evidence", CLAIM_ID, EVIDENCE_ID),
        ("evidence_from_artifact", EVIDENCE_ID, PUBLIC_ARTIFACT_ID),
        ("derived_from_claim", DOCTRINE_ID, CLAIM_ID),
        ("has_revenue_cell", HYPERNODE_ID, REVENUE_CELL_ID),
        ("has_council_verdict", HYPERNODE_ID, COUNCIL_VERDICT_ID),
        ("has_fitness_vector", HYPERNODE_ID, FITNESS_VECTOR_ID),
        ("grounded_in_signal", HYPERNODE_ID, SIGNAL_ID),
        ("answers_question", HYPERNODE_ID, QUESTION_ID),
        ("asserts_claim", HYPERNODE_ID, CLAIM_ID),
        ("cites_evidence", HYPERNODE_ID, EVIDENCE_ID),
        ("codifies_doctrine", HYPERNODE_ID, DOCTRINE_ID),
        ("has_action_proposal", HYPERNODE_ID, ACTION_PROPOSAL_ID),
        ("has_gate_record", HYPERNODE_ID, GATE_RECORD_ID),
        ("has_execution_record", HYPERNODE_ID, EXECUTION_LEASE_ID),
        ("has_outcome_record", HYPERNODE_ID, OUTCOME_ID),
        ("has_value_event", HYPERNODE_ID, VALUE_EVENT_ID),
        ("has_contribution", HYPERNODE_ID, CONTRIBUTION_ID),
        ("has_gate_decision", ACTION_PROPOSAL_ID, GATE_RECORD_ID),
        ("has_execution_lease", ACTION_PROPOSAL_ID, EXECUTION_LEASE_ID),
        ("has_outcome", ACTION_PROPOSAL_ID, OUTCOME_ID),
        ("has_value_event", OUTCOME_ID, VALUE_EVENT_ID),
        ("has_contribution", VALUE_EVENT_ID, CONTRIBUTION_ID),
    ]


def ensure_empty_quadrant_hypernode(
    registry: OntologyRegistry,
    *,
    created_by: str = "hypernode.seed",
) -> HypernodeSeedResult:
    payload = build_empty_quadrant_payload()
    now = _utc_iso()
    errors: list[str] = []
    objects: dict[str, str] = {}

    for obj_id, type_name, properties in _object_specs(payload, now):
        obj, errs = _put_object(registry, obj_id, type_name, properties, created_by=created_by)
        if errs:
            errors.extend([f"{obj_id}: {err}" for err in errs])
        elif obj is not None:
            objects[obj_id] = obj.type_name

    links: list[TypedLinkPayload] = []
    for link_name, source_id, target_id in _link_specs():
        link, errs = _ensure_link(registry, link_name, source_id, target_id, created_by=created_by)
        if errs:
            errors.extend([f"{link_name}: {err}" for err in errs])
        elif link is not None:
            links.append(
                TypedLinkPayload(
                    source_id=link.source_id,
                    source_type=link.source_type,
                    link_name=link.link_name,
                    target_id=link.target_id,
                    target_type=link.target_type,
                )
            )

    stats = registry.stats()
    payload.public_path = EMPTY_QUADRANT_PUBLIC_PATH
    payload.typed_links = links
    payload.ontology_counts = {
        "objects": stats["total_objects"],
        "links": stats["total_links"],
        "registered_types": stats["registered_types"],
    }
    return HypernodeSeedResult(payload=payload, objects=objects, links=links, errors=errors)
