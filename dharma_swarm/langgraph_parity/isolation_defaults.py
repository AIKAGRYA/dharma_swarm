"""Default domain packs for the deterministic isolation benchmark."""

from __future__ import annotations

from collections.abc import Sequence

from dharma_swarm.langgraph_parity.isolation import (
    DomainPack,
    IsolationPolicy,
    SimulatedMemoryKernel,
    SimulatedSemanticCommons,
    ToolSpec,
)


def default_distractor_packs() -> tuple[DomainPack, ...]:
    """Return the distractor pack set used by the local benchmark."""

    return (
        _pack(
            "climate_ops",
            "climate_agent",
            "Evaluate ecological restoration evidence, welfare tons, carbon uplift, and measurement confidence only.",
            (
                ("carbon_project_lookup", "Inspect restoration project carbon claims."),
                ("satellite_restoration_score", "Score geospatial restoration signals."),
                ("welfare_ton_calculator", "Estimate welfare-ton impact ranges."),
            ),
            ("climate", "carbon", "restoration", "welfare"),
        ),
        _pack(
            "finance_risk",
            "finance_agent",
            "Model cash flow, capital risk, drawdown limits, and budget tradeoffs only.",
            (
                ("risk_budget_calculator", "Compute risk budget and drawdown exposure."),
                ("cashflow_projection", "Project cash requirements over time."),
                ("variance_scan", "Detect variance against budget constraints."),
            ),
            ("finance", "cash", "budget", "risk"),
        ),
        _pack(
            "code_security",
            "security_agent",
            "Review code, dependencies, vulnerabilities, and patch evidence only.",
            (
                ("dependency_cve_lookup", "Check dependency vulnerability metadata."),
                ("patch_diff_reader", "Read patch diffs for security regressions."),
                ("semgrep_scan", "Run deterministic static-analysis rules."),
            ),
            ("code", "security", "cve", "patch"),
        ),
        _pack(
            "legal_policy",
            "legal_agent",
            "Analyze contract clauses, jurisdiction, policy constraints, and compliance evidence only.",
            (
                ("contract_clause_search", "Find relevant contract terms."),
                ("jurisdiction_check", "Check jurisdiction-specific policy constraints."),
                ("policy_matrix", "Map obligations to compliance controls."),
            ),
            ("legal", "policy", "contract", "compliance"),
        ),
        _pack(
            "medical_triage",
            "medical_agent",
            "Classify non-diagnostic triage signals, red flags, and care escalation boundaries only.",
            (
                ("symptom_red_flag_check", "Screen for urgent red-flag symptoms."),
                ("care_escalation_boundary", "Map findings to escalation boundaries."),
                ("clinical_source_lookup", "Retrieve high-level clinical source notes."),
            ),
            ("medical", "triage", "symptom", "care"),
        ),
        _pack(
            "travel_logistics",
            "travel_agent",
            "Plan routes, travel windows, visa timing, lodging, and itinerary constraints only.",
            (
                ("route_planner", "Build deterministic route options."),
                ("visa_window_check", "Check visa and stay-window constraints."),
                ("lodging_cost_lookup", "Estimate lodging cost bands."),
            ),
            ("travel", "route", "visa", "lodging"),
        ),
        _pack(
            "supply_chain",
            "supply_agent",
            "Assess vendor timing, inventory buffers, customs delay, and fulfillment risk only.",
            (
                ("vendor_eta_lookup", "Look up vendor lead-time estimates."),
                ("inventory_buffer_model", "Model inventory buffer requirements."),
                ("customs_delay_estimator", "Estimate customs delay risk."),
            ),
            ("supply", "vendor", "inventory", "customs"),
        ),
        _pack(
            "product_growth",
            "growth_agent",
            "Analyze cohorts, activation, funnel dropoff, pricing tests, and growth experiments only.",
            (
                ("cohort_retention_curve", "Build cohort retention curves."),
                ("funnel_dropoff_scan", "Find conversion dropoff points."),
                ("pricing_experiment_reader", "Read pricing experiment evidence."),
            ),
            ("growth", "product", "cohort", "funnel"),
        ),
    )


def default_isolation_policy() -> IsolationPolicy:
    """Return a policy with explicit benchmark handoff routes."""

    return IsolationPolicy(
        default_distractor_packs(),
        allowed_handoffs={
            "climate_agent": ("finance_agent",),
            "finance_agent": ("climate_agent", "legal_agent"),
            "security_agent": ("legal_agent",),
            "legal_agent": ("security_agent", "finance_agent"),
            "medical_agent": (),
            "travel_agent": ("finance_agent",),
            "supply_agent": ("finance_agent", "legal_agent"),
            "growth_agent": ("finance_agent",),
        },
    )


def default_semantic_commons() -> SimulatedSemanticCommons:
    return SimulatedSemanticCommons(default_distractor_packs(), return_all=True)


def default_memory_kernel() -> SimulatedMemoryKernel:
    return SimulatedMemoryKernel.from_packs(default_distractor_packs())


def _pack(
    domain: str,
    agent_name: str,
    instructions: str,
    tools: Sequence[tuple[str, str]],
    keywords: Sequence[str],
) -> DomainPack:
    return DomainPack(
        domain=domain,
        agent_name=agent_name,
        instructions=instructions,
        tools=tuple(
            ToolSpec(name=name, domain=domain, description=description)
            for name, description in tools
        ),
        keywords=tuple(keywords),
    )
