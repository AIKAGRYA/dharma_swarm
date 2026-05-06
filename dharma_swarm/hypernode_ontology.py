"""Ontology schema additions for revenue hypernodes."""

from __future__ import annotations

from dharma_swarm.ontology import (
    ActionDef,
    LinkCardinality,
    LinkDef,
    ObjectType,
    OntologyRegistry,
    PropertyDef,
    PropertyType,
    SecurityLevel,
    SecurityPolicy,
    ShaktiEnergy,
)


_HYPERNODE = ObjectType(
    name="Hypernode",
    description="A worldview-backed revenue cell with public artifact, provenance, gates, and value trace",
    properties={
        "hypernode_id": PropertyDef(
            name="hypernode_id",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "slug": PropertyDef(
            name="slug",
            property_type=PropertyType.STRING,
            required=True,
            searchable=True,
            immutable=True,
        ),
        "title": PropertyDef(
            name="title",
            property_type=PropertyType.STRING,
            required=True,
            searchable=True,
        ),
        "thesis": PropertyDef(
            name="thesis",
            property_type=PropertyType.TEXT,
            required=True,
            searchable=True,
        ),
        "quadrant": PropertyDef(
            name="quadrant",
            property_type=PropertyType.ENUM,
            required=True,
            enum_values=[
                "low_governance_extraction",
                "high_governance_extraction",
                "low_governance_welfare",
                "high_governance_welfare",
            ],
        ),
        "status": PropertyDef(
            name="status",
            property_type=PropertyType.ENUM,
            required=True,
            enum_values=["seeded", "gated", "public_artifact_ready", "revenue_validated", "archived"],
        ),
        "public_path": PropertyDef(name="public_path", property_type=PropertyType.PATH),
        "object_chain": PropertyDef(name="object_chain", property_type=PropertyType.DICT),
        "provenance_refs": PropertyDef(name="provenance_refs", property_type=PropertyType.LIST),
        "next_actions": PropertyDef(name="next_actions", property_type=PropertyType.LIST),
    },
    actions=[
        ActionDef(
            name="SeedHypernode",
            object_type="Hypernode",
            description="Create a new public/internal hypernode seed",
            creates=["RevenueCell", "CouncilVerdict", "FitnessVector"],
            telos_gates=["AHIMSA", "SATYA", "ANEKANTA", "STEELMAN"],
        ),
        ActionDef(
            name="PromoteHypernode",
            object_type="Hypernode",
            description="Promote after quorum, provenance, and fitness thresholds pass",
            modifies=["status"],
            requires_approval=True,
            telos_gates=["AHIMSA", "SATYA", "DOGMA_DRIFT", "STEELMAN"],
        ),
    ],
    security=SecurityPolicy(
        read_roles=["*"],
        create_roles=["orchestrator", "operator", "system"],
        write_roles=["orchestrator", "operator", "system"],
        delete_roles=[],
        classification=SecurityLevel.PUBLIC,
        audit_all=True,
        telos_required=True,
    ),
    telos_alignment=0.98,
    shakti_energy=ShaktiEnergy.MAHALAKSHMI,
    icon="H",
)

_REVENUE_CELL = ObjectType(
    name="RevenueCell",
    description="Market-facing metabolic cell; revenue is tracked as trustee flow, not private possession",
    properties={
        "revenue_cell_id": PropertyDef(
            name="revenue_cell_id",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "hypernode_ref": PropertyDef(
            name="hypernode_ref",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "name": PropertyDef(
            name="name",
            property_type=PropertyType.STRING,
            required=True,
            searchable=True,
        ),
        "market_category": PropertyDef(name="market_category", property_type=PropertyType.STRING),
        "target_customer": PropertyDef(name="target_customer", property_type=PropertyType.STRING),
        "revenue_model": PropertyDef(name="revenue_model", property_type=PropertyType.TEXT),
        "verified_revenue_usd": PropertyDef(name="verified_revenue_usd", property_type=PropertyType.FLOAT),
        "expected_value_usd": PropertyDef(name="expected_value_usd", property_type=PropertyType.FLOAT),
        "evidence_tier": PropertyDef(
            name="evidence_tier",
            property_type=PropertyType.ENUM,
            enum_values=[
                "internal_estimate",
                "market_signal",
                "invoice_paid",
                "stripe_event",
                "bank_transaction",
            ],
        ),
        "trustee_principle": PropertyDef(name="trustee_principle", property_type=PropertyType.TEXT),
        "status": PropertyDef(
            name="status",
            property_type=PropertyType.ENUM,
            enum_values=["seeded", "validating", "earning", "paused", "archived"],
        ),
        "next_actions": PropertyDef(name="next_actions", property_type=PropertyType.LIST),
    },
    actions=[
        ActionDef(
            name="RecordRevenueSignal",
            object_type="RevenueCell",
            description="Record market evidence without treating estimates as verified revenue",
            modifies=["verified_revenue_usd", "expected_value_usd", "evidence_tier"],
            telos_gates=["SATYA", "DOGMA_DRIFT"],
        ),
    ],
    security=SecurityPolicy(
        create_roles=["orchestrator", "operator", "system"],
        write_roles=["orchestrator", "operator", "system"],
        delete_roles=[],
        audit_all=True,
    ),
    telos_alignment=0.94,
    shakti_energy=ShaktiEnergy.MAHALAKSHMI,
    icon="$",
)

_COUNCIL_VERDICT = ObjectType(
    name="CouncilVerdict",
    description="Quorum result for a hypernode, including Anekanta, steelman, dogma drift, and MIROFISH trace",
    properties={
        "verdict_id": PropertyDef(
            name="verdict_id",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "hypernode_ref": PropertyDef(
            name="hypernode_ref",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "decision": PropertyDef(
            name="decision",
            property_type=PropertyType.ENUM,
            required=True,
            enum_values=["pass", "warn", "fail", "review"],
        ),
        "reason": PropertyDef(name="reason", property_type=PropertyType.TEXT),
        "gate_results": PropertyDef(name="gate_results", property_type=PropertyType.DICT),
        "anekanta_frames": PropertyDef(name="anekanta_frames", property_type=PropertyType.LIST),
        "steelman_summary": PropertyDef(name="steelman_summary", property_type=PropertyType.TEXT),
        "dogma_drift_summary": PropertyDef(name="dogma_drift_summary", property_type=PropertyType.TEXT),
        "mirofish_activated": PropertyDef(name="mirofish_activated", property_type=PropertyType.BOOLEAN),
        "mirofish_reason": PropertyDef(name="mirofish_reason", property_type=PropertyType.TEXT),
        "quorum_participants": PropertyDef(name="quorum_participants", property_type=PropertyType.LIST),
        "recorded_at": PropertyDef(name="recorded_at", property_type=PropertyType.DATETIME),
    },
    actions=[
        ActionDef(
            name="RecordCouncilVerdict",
            object_type="CouncilVerdict",
            description="Record the quorum trace for a hypernode",
            telos_gates=["ANEKANTA", "STEELMAN", "DOGMA_DRIFT"],
        ),
    ],
    security=SecurityPolicy(audit_all=True, delete_roles=[]),
    telos_alignment=1.0,
    shakti_energy=ShaktiEnergy.MAHESHWARI,
    icon="Q",
)

_FITNESS_VECTOR = ObjectType(
    name="FitnessVector",
    description="Hypernode promotion score from AutoGrade, council verdicts, provenance, market, and welfare dimensions",
    properties={
        "fitness_id": PropertyDef(
            name="fitness_id",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "hypernode_ref": PropertyDef(
            name="hypernode_ref",
            property_type=PropertyType.STRING,
            required=True,
            immutable=True,
        ),
        "auto_grade_score": PropertyDef(name="auto_grade_score", property_type=PropertyType.FLOAT),
        "council_score": PropertyDef(name="council_score", property_type=PropertyType.FLOAT),
        "provenance_score": PropertyDef(name="provenance_score", property_type=PropertyType.FLOAT),
        "market_value_score": PropertyDef(name="market_value_score", property_type=PropertyType.FLOAT),
        "welfare_score": PropertyDef(name="welfare_score", property_type=PropertyType.FLOAT),
        "composite_score": PropertyDef(name="composite_score", property_type=PropertyType.FLOAT),
        "promotion_threshold": PropertyDef(name="promotion_threshold", property_type=PropertyType.FLOAT),
        "threshold_met": PropertyDef(name="threshold_met", property_type=PropertyType.BOOLEAN),
        "promotion_state": PropertyDef(
            name="promotion_state",
            property_type=PropertyType.ENUM,
            enum_values=[
                "candidate",
                "quorum_ready",
                "public_artifact_ready",
                "revenue_validated",
                "revise",
            ],
        ),
        "scoring_method": PropertyDef(name="scoring_method", property_type=PropertyType.STRING),
    },
    actions=[
        ActionDef(
            name="ScoreHypernode",
            object_type="FitnessVector",
            description="Score a hypernode for artifact and revenue-cell promotion",
            telos_gates=["SATYA", "DOGMA_DRIFT"],
        ),
    ],
    security=SecurityPolicy(audit_all=True, delete_roles=[]),
    telos_alignment=0.9,
    shakti_energy=ShaktiEnergy.MAHASARASWATI,
    icon="F",
)

_HYPERNODE_LINKS: list[LinkDef] = [
    LinkDef(
        name="has_revenue_cell",
        source_type="Hypernode",
        target_type="RevenueCell",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="cell_of_hypernode",
    ),
    LinkDef(
        name="has_council_verdict",
        source_type="Hypernode",
        target_type="CouncilVerdict",
        cardinality=LinkCardinality.ONE_TO_MANY,
        inverse_name="verdict_for_hypernode",
    ),
    LinkDef(
        name="has_fitness_vector",
        source_type="Hypernode",
        target_type="FitnessVector",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="fitness_for_hypernode",
    ),
    LinkDef(
        name="grounded_in_signal",
        source_type="Hypernode",
        target_type="Signal",
        cardinality=LinkCardinality.MANY_TO_ONE,
        inverse_name="grounds_hypernode",
    ),
    LinkDef(
        name="answers_question",
        source_type="Hypernode",
        target_type="Question",
        cardinality=LinkCardinality.MANY_TO_ONE,
        inverse_name="answered_by_hypernode",
    ),
    LinkDef(
        name="asserts_claim",
        source_type="Hypernode",
        target_type="Claim",
        cardinality=LinkCardinality.MANY_TO_ONE,
        inverse_name="asserted_by_hypernode",
    ),
    LinkDef(
        name="cites_evidence",
        source_type="Hypernode",
        target_type="Evidence",
        cardinality=LinkCardinality.ONE_TO_MANY,
        inverse_name="cited_by_hypernode",
    ),
    LinkDef(
        name="codifies_doctrine",
        source_type="Hypernode",
        target_type="Doctrine",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="codified_by_hypernode",
    ),
    LinkDef(
        name="has_action_proposal",
        source_type="Hypernode",
        target_type="ActionProposal",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="proposal_for_hypernode",
    ),
    LinkDef(
        name="has_gate_record",
        source_type="Hypernode",
        target_type="GateDecisionRecord",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="gate_record_for_hypernode",
    ),
    LinkDef(
        name="has_execution_record",
        source_type="Hypernode",
        target_type="ExecutionLease",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="execution_record_for_hypernode",
    ),
    LinkDef(
        name="has_outcome_record",
        source_type="Hypernode",
        target_type="Outcome",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="outcome_record_for_hypernode",
    ),
    LinkDef(
        name="has_value_event",
        source_type="Hypernode",
        target_type="ValueEvent",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="value_event_for_hypernode",
    ),
    LinkDef(
        name="has_contribution",
        source_type="Hypernode",
        target_type="Contribution",
        cardinality=LinkCardinality.ONE_TO_ONE,
        inverse_name="contribution_for_hypernode",
    ),
]


def register_hypernode_types(registry: OntologyRegistry) -> None:
    """Register hypernode types and links idempotently."""
    for obj_type in (_HYPERNODE, _REVENUE_CELL, _COUNCIL_VERDICT, _FITNESS_VECTOR):
        registry.register_type(obj_type)
    for link_def in _HYPERNODE_LINKS:
        registry.register_link(link_def)
