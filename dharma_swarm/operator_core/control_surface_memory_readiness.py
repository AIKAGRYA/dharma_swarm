"""MemoryKernel readiness projections for operator control rows.

This helper module keeps the operator row assembly small while preserving the
same read-only burn-in contract for rollout decisions.
"""

from __future__ import annotations

from typing import Any


READINESS_SCHEMA_VERSION = "memory_kernel_readiness.v1"
READINESS_ROW_RAW_FIELDS = (
    "schema_version",
    "readiness_status",
    "strict_readiness_state",
    "strict_ready",
    "summary",
    "accounted_surface_count",
    "accounted_surface_total",
    "accounted_surface_ratio",
    "unaccounted_surface_count",
    "required_surface_count",
    "required_accounted_surface_count",
    "required_accounted_surface_ratio",
    "required_unaccounted_surface_ids",
    "missing_adapter_count",
    "degraded_count",
    "unavailable_count",
    "warning_count",
    "sample_warnings",
)
ROLLOUT_READINESS_RAW_FIELDS = (
    "readiness_status",
    "strict_readiness_state",
    "strict_ready",
    "accounted_surface_count",
    "accounted_surface_total",
    "accounted_surface_ratio",
    "required_surface_count",
    "required_accounted_surface_count",
    "required_accounted_surface_ratio",
    "warning_count",
)
READY_TIERS = (
    "m0_rollout_off",
    "m2_strict_read_only",
    "m3_safe_context_preview",
    "m4_governed_write_receipts",
    "m5_live_promotion_candidate",
)
ROLLOUT_READY_TIER_REQUIREMENTS = {
    "off": "m0_rollout_off",
    "shadow": "m2_strict_read_only",
    "preview": "m3_safe_context_preview",
    "canary": "m4_governed_write_receipts",
    "live": "m5_live_promotion_candidate",
}
BURN_IN_REQUIRED_CHECKS = {
    "off": ("rollout_state_valid",),
    "shadow": ("rollout_state_valid", "readiness_contract_present", "rollback_available"),
    "preview": (
        "rollout_state_valid",
        "readiness_contract_present",
        "strict_readiness_ready",
        "context_canary_visible",
        "burn_in_receipts_ready",
        "parity_eval_zero_hard_failures",
        "rollout_not_above_ready_tier",
        "rollback_available",
    ),
    "canary": (
        "rollout_state_valid",
        "readiness_contract_present",
        "strict_readiness_ready",
        "context_canary_visible",
        "burn_in_receipts_ready",
        "parity_eval_zero_hard_failures",
        "write_receipts_ready",
        "rollout_not_above_ready_tier",
        "rollback_available",
    ),
    "live": (
        "rollout_state_valid",
        "readiness_contract_present",
        "strict_readiness_ready",
        "context_canary_visible",
        "burn_in_receipts_ready",
        "parity_eval_zero_hard_failures",
        "write_receipts_ready",
        "promotion_ready",
        "rollout_not_above_ready_tier",
        "rollback_available",
    ),
}


def readiness_contract(projection: Any) -> dict[str, Any]:
    report = projection.readiness if isinstance(projection.readiness, dict) else {}
    summary = report.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    surfaces = report.get("surfaces", ())
    if not isinstance(surfaces, (tuple, list)):
        surfaces = ()

    surface_count = int_value(summary.get("surface_count"))
    required_count = int_value(summary.get("required_surface_count"))
    adapter_registered_count = int_value(summary.get("adapter_registered_count"))
    uncovered_count = int_value(summary.get("uncovered_count"))
    missing_adapter_count = int_value(summary.get("missing_adapter_count"))
    degraded_count = int_value(summary.get("degraded_count"))
    unavailable_count = int_value(summary.get("unavailable_count"))
    warning_count = int_value(summary.get("warning_count"))

    accounted_count = adapter_registered_count + uncovered_count
    if surface_count > 0:
        accounted_count = min(accounted_count, surface_count)
    required_accounted_count = sum(
        1
        for surface in surfaces
        if isinstance(surface, dict)
        and bool(surface.get("required"))
        and bool(surface.get("adapter_registered"))
    )
    if not surfaces and required_accounted_count == 0 and required_count > 0:
        required_accounted_count = min(adapter_registered_count, required_count)
    required_unaccounted_ids = tuple(
        str(surface.get("surface_id"))
        for surface in surfaces
        if isinstance(surface, dict)
        and bool(surface.get("required"))
        and not bool(surface.get("adapter_registered"))
        and surface.get("surface_id")
    )
    required_surfaces_accounted = required_count > 0 and (
        required_accounted_count >= required_count
    )
    strict_ready = (
        report.get("status") == "ready"
        and required_surfaces_accounted
        and missing_adapter_count == 0
        and degraded_count == 0
        and unavailable_count == 0
        and warning_count == 0
    )
    warnings = report.get("warnings", ())
    if not isinstance(warnings, (tuple, list)):
        warnings = ()

    return {
        "schema_version": str(report.get("schema_version", "")),
        "readiness_status": str(report.get("status", "unavailable")),
        "strict_readiness_state": "strict_ready" if strict_ready else "strict_blocked",
        "strict_ready": strict_ready,
        "contract_present": report.get("schema_version") == READINESS_SCHEMA_VERSION,
        "summary": {
            "surface_count": surface_count,
            "required_surface_count": required_count,
            "adapter_registered_count": adapter_registered_count,
            "ready_count": int_value(summary.get("ready_count")),
            "degraded_count": degraded_count,
            "unavailable_count": unavailable_count,
            "missing_adapter_count": missing_adapter_count,
            "uncovered_count": uncovered_count,
            "warning_count": warning_count,
        },
        "accounted_surface_count": accounted_count,
        "accounted_surface_total": surface_count,
        "accounted_surface_ratio": ratio_text(accounted_count, surface_count),
        "unaccounted_surface_count": missing_adapter_count,
        "required_surface_count": required_count,
        "required_accounted_surface_count": required_accounted_count,
        "required_accounted_surface_ratio": ratio_text(
            required_accounted_count,
            required_count,
        ),
        "required_unaccounted_surface_ids": required_unaccounted_ids,
        "required_surfaces_accounted": required_surfaces_accounted,
        "missing_adapter_count": missing_adapter_count,
        "degraded_count": degraded_count,
        "unavailable_count": unavailable_count,
        "warning_count": warning_count,
        "sample_warnings": tuple(str(item) for item in warnings[:20]),
    }


def burn_in_safety(
    *,
    state: str,
    invalid: bool,
    rollback_engaged: bool,
    readiness: dict[str, Any],
    context_canary_visible: bool,
    burn_in_status: dict[str, Any] | None = None,
    write_receipts_ready: bool = False,
    promotion_ready: bool = False,
) -> dict[str, Any]:
    resolved_burn_in = burn_in_status or {}
    parity_hard_failures = int_value(resolved_burn_in.get("parity_hard_failure_count"))
    burn_in_ready = bool(resolved_burn_in.get("burn_in_ready"))
    max_tier = max_ready_tier(
        readiness=readiness,
        context_canary_visible=context_canary_visible,
        burn_in_ready=burn_in_ready,
        parity_hard_failure_count=parity_hard_failures,
        write_receipts_ready=write_receipts_ready,
        promotion_ready=promotion_ready,
    )
    required_tier = ROLLOUT_READY_TIER_REQUIREMENTS.get(state, "m0_rollout_off")
    checks = {
        "rollout_state_valid": not invalid,
        "readiness_contract_present": bool(readiness["contract_present"]),
        "required_surfaces_accounted": bool(readiness["required_surfaces_accounted"]),
        "readiness_status_ready": readiness["readiness_status"] == "ready",
        "strict_readiness_ready": bool(readiness["strict_ready"]),
        "context_canary_visible": context_canary_visible,
        "burn_in_receipts_ready": burn_in_ready,
        "parity_eval_zero_hard_failures": parity_hard_failures == 0,
        "write_receipts_ready": write_receipts_ready,
        "promotion_ready": promotion_ready,
        "rollout_not_above_ready_tier": tier_allows_state(max_tier, state),
        "rollback_available": not rollback_engaged,
    }
    required_checks = BURN_IN_REQUIRED_CHECKS.get(state, ("rollout_state_valid",))
    blockers = tuple(name for name in required_checks if not checks[name])
    return {
        "burn_in_safety_state": "safe" if not blockers else "blocked",
        "burn_in_safe": not blockers,
        "burn_in_blockers": blockers,
        "burn_in_required_checks": required_checks,
        "max_ready_tier": max_tier,
        "required_ready_tier": required_tier,
        "burn_in_checks": {
            name: {"ok": ok, "required": name in required_checks}
            for name, ok in checks.items()
        },
    }


def max_ready_tier(
    *,
    readiness: dict[str, Any],
    context_canary_visible: bool,
    burn_in_ready: bool,
    parity_hard_failure_count: int,
    write_receipts_ready: bool,
    promotion_ready: bool,
) -> str:
    tier = "m0_rollout_off"
    if not bool(readiness["strict_ready"]):
        return tier
    tier = "m2_strict_read_only"
    if context_canary_visible and burn_in_ready and parity_hard_failure_count == 0:
        tier = "m3_safe_context_preview"
    if tier_index(tier) >= tier_index("m3_safe_context_preview") and write_receipts_ready:
        tier = "m4_governed_write_receipts"
    if tier_index(tier) >= tier_index("m4_governed_write_receipts") and promotion_ready:
        tier = "m5_live_promotion_candidate"
    return tier


def tier_allows_state(max_tier: str, state: str) -> bool:
    required = ROLLOUT_READY_TIER_REQUIREMENTS.get(state, "m0_rollout_off")
    return tier_index(max_tier) >= tier_index(required)


def tier_index(tier: str) -> int:
    try:
        return READY_TIERS.index(tier)
    except ValueError:
        return 0


def context_canary_visible(context_canary: Any) -> bool:
    return (
        context_canary.id == "memory.context_canary"
        and context_canary.coherence_state == "bound"
        and int_value(context_canary.raw.get("projected_failure_count")) > 0
    )


def ratio_text(count: int, total: int) -> str:
    return f"{count}/{total}"


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
