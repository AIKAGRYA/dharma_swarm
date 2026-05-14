"""Tests for the read-only operator production smoke harness."""

from __future__ import annotations

from types import SimpleNamespace

from scripts.operator_prod_smoke import (
    REQUIRED_MEMORY_ROW_IDS,
    check_context_shadow_report,
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
