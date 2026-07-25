"""Deterministic task catalogue for the LangGraph parity benchmark."""

from __future__ import annotations

from dharma_swarm.langgraph_parity.benchmark_types import BenchmarkTask


_EXPECTED_TOOLS: dict[str, tuple[str, ...]] = {
    "climate_ops": ("carbon_project_lookup", "welfare_ton_calculator"),
    "finance_risk": ("risk_budget_calculator", "cashflow_projection"),
    "code_security": ("dependency_cve_lookup", "patch_diff_reader"),
    "legal_policy": ("contract_clause_search", "jurisdiction_check"),
    "medical_triage": ("symptom_red_flag_check", "care_escalation_boundary"),
    "travel_logistics": ("route_planner", "visa_window_check"),
    "supply_chain": ("vendor_eta_lookup", "inventory_buffer_model"),
    "product_growth": ("cohort_retention_curve", "funnel_dropoff_scan"),
}

_TASK_SPECS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "climate_finance_multihop",
        "Estimate welfare-ton upside for a mangrove restoration pilot, then convert that "
        "into a risk-bounded deployment cash budget.",
        ("climate_ops", "finance_risk"),
        ("fan_out", "swarm", "supervisor", "command_send_routing"),
    ),
    (
        "climate_checkpoint_reload",
        "Resume a restoration scoring thread after checkpoint reload and reuse only "
        "climate-domain memory.",
        ("climate_ops",),
        ("checkpoint_reload", "memory_isolation"),
    ),
    (
        "finance_legal_pipeline",
        "Pipeline a budget cap decision into legal policy review for a customer deployment clause.",
        ("finance_risk", "legal_policy"),
        ("pipeline", "command_send_routing"),
    ),
    (
        "security_legal_retry_patch",
        "Retry a failed patch-review lane, then route confirmed CVE exposure into legal "
        "compliance review.",
        ("code_security", "legal_policy"),
        ("retry", "provider_fallback"),
    ),
    (
        "supply_finance_fan_in",
        "Fan in inventory-delay evidence and cash-buffer estimates for a vendor fulfillment lane.",
        ("supply_chain", "finance_risk"),
        ("fan_in", "subagents_as_tools"),
    ),
    (
        "supply_finance_legal_send",
        "Use Send-style routing from supply analysis to finance and legal workers before "
        "producing a deployment recommendation.",
        ("supply_chain", "finance_risk", "legal_policy"),
        ("command_send_routing", "subagents_as_tools"),
    ),
    (
        "travel_finance_pipeline",
        "Pipeline visa-window and lodging estimates into a cash budget that can resume after restart.",
        ("travel_logistics", "finance_risk"),
        ("pipeline", "checkpoint_reload"),
    ),
    (
        "growth_finance_broadcast",
        "Broadcast cohort-retention signals to pricing and finance risk views for a go/no-go "
        "growth experiment.",
        ("product_growth", "finance_risk"),
        ("broadcast",),
    ),
    (
        "medical_interrupt_resume",
        "Pause a non-diagnostic triage flow for human approval and resume with only "
        "medical-domain context.",
        ("medical_triage",),
        ("interrupt_resume", "memory_isolation"),
    ),
    (
        "a2a_blocker_queue",
        "Classify open, unknown, and unverified A2A task states as hard readiness blockers "
        "with exact task IDs.",
        ("code_security",),
        ("a2a_blocker_semantics",),
    ),
    (
        "vendor_timeout_cancellation",
        "Cancel a vendor ETA watch after timeout while preserving the last durable "
        "supply-chain checkpoint.",
        ("supply_chain",),
        ("timeout", "cancellation"),
    ),
    (
        "security_patch_review",
        "Review a dependency patch for CVE exposure and static-analysis regression risk.",
        ("code_security",),
        ("retry", "timeout"),
    ),
    (
        "climate_broadcast_measurement",
        "Broadcast restoration measurement evidence to parallel scoring workers and compare "
        "carbon versus welfare-ton confidence.",
        ("climate_ops",),
        ("broadcast", "fan_out"),
    ),
    (
        "finance_fan_in_variance",
        "Fan in risk budget, cashflow, and variance scans for a capital allocation decision.",
        ("finance_risk",),
        ("fan_in",),
    ),
    (
        "contract_policy_check",
        "Check a cancellation clause against jurisdiction and compliance policy constraints.",
        ("legal_policy",),
        ("checkpoint_reload", "interrupt_resume"),
    ),
    (
        "growth_provider_fallback",
        "Route a pricing experiment summary through fallback provider selection while preserving "
        "growth-domain tools.",
        ("product_growth",),
        ("provider_fallback",),
    ),
    (
        "travel_memory_isolation",
        "Retrieve route and visa memory while rejecting finance, legal, and medical distractor context.",
        ("travel_logistics",),
        ("memory_isolation",),
    ),
    (
        "medical_tool_boundary",
        "Keep red-flag triage tools isolated from legal, finance, and travel distractors.",
        ("medical_triage",),
        ("memory_isolation",),
    ),
    (
        "security_subagent_tool_review",
        "Expose a security reviewer as a tool to a legal supervisor for a patch-risk compliance answer.",
        ("code_security", "legal_policy"),
        ("subagents_as_tools", "supervisor"),
    ),
    (
        "climate_finance_budget_retry",
        "Retry a failed welfare-ton budget handoff without duplicating provider calls or cross-domain memory.",
        ("climate_ops", "finance_risk"),
        ("retry", "swarm"),
    ),
    (
        "supply_broadcast_inventory",
        "Broadcast vendor and inventory-buffer signals for fulfillment risk review.",
        ("supply_chain",),
        ("broadcast",),
    ),
    (
        "legal_finance_fan_out_policy",
        "Fan out a policy clause to legal and finance reviewers, then compare compliance and budget constraints.",
        ("legal_policy", "finance_risk"),
        ("fan_out", "supervisor"),
    ),
    (
        "growth_finance_command_send",
        "Send pricing-test outputs to finance risk workers for a launch budget decision.",
        ("product_growth", "finance_risk"),
        ("command_send_routing", "swarm"),
    ),
    (
        "travel_finance_a2a_operator",
        "Treat missing operator approval on a travel budget packet as an A2A readiness blocker, not a soft warning.",
        ("travel_logistics", "finance_risk"),
        ("a2a_blocker_semantics", "interrupt_resume"),
    ),
    (
        "climate_cancellation_watch",
        "Cancel a stale restoration-monitoring run and preserve a queryable checkpoint for restart.",
        ("climate_ops",),
        ("cancellation", "checkpoint_reload"),
    ),
    (
        "supply_eta_risk",
        "Assess vendor lead time, customs delay risk, and inventory buffer for a fulfillment lane.",
        ("supply_chain",),
        ("timeout", "pipeline"),
    ),
)


def default_benchmark_tasks() -> tuple[BenchmarkTask, ...]:
    """Return the stable deterministic LangGraph parity case suite."""

    return tuple(
        BenchmarkTask(
            id=task_id,
            prompt=prompt,
            required_domains=required_domains,
            expected_tools={domain: _EXPECTED_TOOLS[domain] for domain in required_domains},
            case_tags=case_tags,
        )
        for task_id, prompt, required_domains, case_tags in _TASK_SPECS
    )
