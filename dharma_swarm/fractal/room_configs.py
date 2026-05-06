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
        └── agentops (operations)
    """
    registry = RoomRegistry()
    core = make_core_ops_room()
    registry.register(core)
    registry.register(make_revenue_wedge_cell())
    registry.register(make_agentops_room())
    return registry
