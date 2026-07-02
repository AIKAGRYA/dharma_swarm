"""Pre-defined room configurations for Dharma Swarm.

These are the canonical room instances. Each function returns a
validated, ready-to-register room. The rooms are defined here
rather than in YAML/JSON so they benefit from type checking and
validation at import time.

See: docs/governance/VENTURE_CELL_REVENUE_WEDGE.md
"""

from __future__ import annotations

from dharma_swarm.fractal.fractal_room import (
    FractalRoom,
    RoomKind,
    RoomRegistry,
    VentureCellV1,
    validate_room,
    validate_venture_cell,
)


def make_core_ops_room() -> FractalRoom:
    """The root room — wraps everything the system already does."""
    room = FractalRoom(
        id="core-ops",
        kind=RoomKind.OPERATIONS,
        purpose="Keep the system operational and governed",
        operator="dhyana",
        budget_tokens=100_000,
        agents=["codex.local", "claude.local"],
        allowed_work=[
            "system maintenance",
            "governance enforcement",
            "test suite management",
            "documentation updates",
            "operator brief generation",
            "kaizen review cycles",
        ],
        forbidden_work=[
            "live autonomy",
            "unsupervised deployment",
            "external outreach without approval",
        ],
        approval_required_for=[
            "budget increase",
            "sub-cell spawn",
            "external outreach",
            "merge to main",
        ],
        gates=["scope_gate", "test_gate", "burn_awareness"],
        memory_namespace="core_ops",
        report_paths={
            "agentops": "reports/agentops/core_ops/",
            "kaizen": "reports/kaizen/core_ops/",
        },
    )
    validate_room(room)
    return room


def make_revenue_wedge_cell() -> VentureCellV1:
    """The first VentureCell — find and prove the first revenue wedge."""
    cell = VentureCellV1(
        id="revenue-wedge",
        kind=RoomKind.VENTURE_CELL,
        parent_id="core-ops",
        purpose="Find and ship the first self-funding offer",
        operator="dhyana",
        budget_tokens=50_000,
        revenue_target=10_000,
        agents=["codex.local", "claude.local", "devin.cloud"],
        allowed_work=[
            "customer research",
            "value proposition drafting",
            "MVP prototyping",
            "pricing experiments",
            "daily operating brief",
            "YDS ledger entries",
            "burn report generation",
            "kaizen review cycles",
        ],
        forbidden_work=[
            # Inherited from core-ops
            "live autonomy",
            "unsupervised deployment",
            "external outreach without approval",
            # Additional constraints
            "dashboard expansion",
            "ontology refactor",
            "memory consolidation",
            "broad v3 implementation",
            "spending without approval",
        ],
        approval_required_for=[
            "spending money",
            "external outreach",
            "merge to main",
            "authoritative YDS rating",
            "budget increase",
            "sub-cell spawn",
        ],
        gates=[
            "scope_gate",
            "test_gate",
            "burn_awareness",
            "human_approval_external",
            "revenue_proof_gate",
        ],
        memory_namespace="revenue_wedge",
        report_paths={
            "agentops": "reports/agentops/revenue_wedge/",
            "kaizen": "reports/kaizen/revenue_wedge/",
        },
        # VentureCell fields
        customer_or_beneficiary="dev teams and solo founders",
        value_proposition="Governed multi-agent operating system that compounds knowledge",
        self_funding_hypothesis="Dev teams will pay for reliable multi-agent orchestration with governance",
        kill_conditions=[
            "no_revenue_after_60_days",
            "budget_exceeded",
            "operator_override",
        ],
        spinout_conditions=[
            "revenue_exceeds_burn",
            "operator_approval",
            "customer_validation",
        ],
        jagat_kalyan_constraint="Revenue without welfare is extraction. Each review must include welfare assessment.",
    )
    validate_venture_cell(cell)
    return cell


def make_livelihood_loom_cell() -> VentureCellV1:
    """Livelihood Loom — informal-economy enablement VentureCell."""
    cell = VentureCellV1(
        id="livelihood-loom",
        kind=RoomKind.VENTURE_CELL,
        parent_id="core-ops",
        purpose="Cultivate informal-economy enablement with consented outcomes",
        operator="dhyana",
        budget_tokens=20_000,
        revenue_target=5_000,
        agents=[
            "loom_conductor",
            "field_cartography",
            "worker_advocate",
            "evidence_auditor",
            "safety_red_team",
        ],
        allowed_work=[
            "public-source livelihood mapping",
            "candidate enrichment",
            "risk scoring",
            "enablement packet drafting",
            "outcome receipt drafting",
            "sponsor brief drafting",
        ],
        forbidden_work=[
            # Inherited from core-ops
            "live autonomy",
            "unsupervised deployment",
            "external outreach without approval",
            # Livelihood-specific constraints
            "autonomous lending decisions",
            "autonomous payments",
            "worker surveillance",
            "raw data sale",
            "trading alpha extraction",
            "publishing sensitive livelihood data",
        ],
        approval_required_for=[
            "budget increase",
            "sub-cell spawn",
            "external outreach",
            "merge to main",
            "spending money",
            "publication",
            "payment",
            "on-chain transaction",
            "procurement intro",
            "partner claim",
            "capital signal",
        ],
        gates=[
            "scope_gate",
            "test_gate",
            "burn_awareness",
            "human_approval_external",
            "consent_gate",
            "public_proof_privacy_gate",
            "worker_harm_gate",
        ],
        memory_namespace="livelihood_loom",
        report_paths={
            "agentops": "reports/agentops/livelihood_loom/",
            "kaizen": "reports/kaizen/livelihood_loom/",
            "outcomes": "reports/livelihood_loom/outcomes/",
        },
        customer_or_beneficiary="informal workers, microenterprises, sponsors, and buyers",
        value_proposition=(
            "Source-backed livelihood maps, enablement packets, and audited "
            "outcome evidence without exploiting vulnerable data"
        ),
        self_funding_hypothesis=(
            "Sponsors and buyers will pay for verified livelihood enablement, "
            "procurement bridges, and outcome reporting"
        ),
        first_revenue_proof="",
        kill_conditions=[
            "no_revenue_after_60_days",
            "budget_exceeded",
            "welfare_tons_negative",
            "operator_override",
        ],
        spinout_conditions=[
            "revenue_exceeds_burn",
            "operator_approval",
            "customer_validation",
        ],
        jagat_kalyan_constraint=(
            "No livelihood record, proof, outreach, payment, or capital signal "
            "may expose sensitive people or convert vulnerability into alpha."
        ),
    )
    validate_venture_cell(cell)
    return cell


def make_agentops_room() -> FractalRoom:
    """The AgentOps room — makes multi-agent repo work safe and repeatable."""
    room = FractalRoom(
        id="agentops",
        kind=RoomKind.OPERATIONS,
        parent_id="core-ops",
        purpose="Make multi-agent repo work safe and repeatable",
        operator="dhyana",
        budget_tokens=30_000,
        agents=["codex.local", "claude.local"],
        allowed_work=[
            "agent safety protocols",
            "work packet management",
            "gate enforcement",
            "witness logging",
            "agent performance review",
        ],
        forbidden_work=[
            # Inherited from core-ops
            "live autonomy",
            "unsupervised deployment",
            "external outreach without approval",
        ],
        approval_required_for=[
            # Inherited from core-ops
            "budget increase",
            "sub-cell spawn",
            "external outreach",
            "merge to main",
            # Additional
            "new agent registration",
            "authority changes",
        ],
        gates=["scope_gate", "test_gate"],
        memory_namespace="agentops",
    )
    validate_room(room)
    return room


def bootstrap_registry() -> RoomRegistry:
    """Create a registry with the standard room hierarchy.

    Returns a RoomRegistry with:
      core-ops (root)
        ├── revenue-wedge (venture cell)
        ├── livelihood-loom (venture cell)
        └── agentops (operations)
    """
    registry = RoomRegistry()
    core = make_core_ops_room()
    registry.register(core)
    registry.register(make_revenue_wedge_cell())
    registry.register(make_livelihood_loom_cell())
    registry.register(make_agentops_room())
    return registry
