"""Tests for the read-only operator production smoke harness."""

from __future__ import annotations

from types import SimpleNamespace

from scripts.operator_prod_smoke import (
    REQUIRED_MEMORY_ROW_IDS,
    check_burn_in_safety,
    check_context_shadow_report,
    check_readiness_contract,
    check_rollback_switch_presence,
    check_row_projection,
)


def test_smoke_row_projection_requires_memory_kernel_rows() -> None:
    rows = [SimpleNamespace(id=row_id) for row_id in sorted(REQUIRED_MEMORY_ROW_IDS)]

    check = check_row_projection(rows)

    assert check.ok is True
    assert check.name == "memory_row_projection"


def test_smoke_row_projection_reports_missing_memory_rows() -> None:
    check = check_row_projection([])

    assert check.ok is False
    assert "memory.census" in check.detail


def test_smoke_context_shadow_report_projects_canary_failure() -> None:
    check = check_context_shadow_report()

    assert check.ok is True
    assert "hard_failures=" in check.detail


def test_smoke_rollback_switch_presence() -> None:
    rows = [
        SimpleNamespace(
            id="memory.rollback_switch",
            observed_state="available",
            raw={"switch_present": True},
        ),
        SimpleNamespace(
            id="memory.rollout_gate",
            observed_state="off",
            raw={"allowed_states": ("off", "shadow", "preview", "canary", "live")},
        ),
    ]

    check = check_rollback_switch_presence(rows)

    assert check.ok is True
    assert "rollout=off" in check.detail


def test_smoke_readiness_contract_requires_strict_fields() -> None:
    rows = [
        SimpleNamespace(
            id="memory.readiness",
            raw={
                "schema_version": "memory_kernel_readiness.v1",
                "readiness_status": "degraded",
                "strict_readiness_state": "strict_blocked",
                "accounted_surface_count": 7,
                "accounted_surface_total": 81,
                "required_surface_count": 7,
                "required_accounted_surface_count": 7,
                "warning_count": 95,
            },
        )
    ]

    check = check_readiness_contract(rows)

    assert check.ok is True
    assert "strict=strict_blocked" in check.detail


def test_smoke_burn_in_safety_requires_safe_gate() -> None:
    rows = [
        SimpleNamespace(
            id="memory.rollout_gate",
            observed_state="off",
            raw={
                "burn_in_safety_state": "safe",
                "burn_in_safe": True,
                "burn_in_blockers": (),
            },
        )
    ]

    check = check_burn_in_safety(rows)

    assert check.ok is True
    assert "blockers=<none>" in check.detail
