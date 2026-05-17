"""Tests for the read-only operator production smoke harness."""

from __future__ import annotations

from types import SimpleNamespace

from scripts.operator_prod_smoke import (
    REQUIRED_MEMORY_ROW_IDS,
    check_burn_in_safety,
    check_context_shadow_report,
    check_knowledgeops_bridge_contract,
    check_memory_home_contract,
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


def test_smoke_readiness_contract_accepts_strict_ready() -> None:
    rows = [
        SimpleNamespace(
            id="memory.readiness",
            raw={
                "schema_version": "memory_kernel_readiness.v1",
                "readiness_status": "ready",
                "strict_readiness_state": "strict_ready",
                "strict_ready": True,
                "accounted_surface_count": 81,
                "accounted_surface_total": 81,
                "required_surface_count": 7,
                "required_accounted_surface_count": 7,
                "warning_count": 0,
            },
        )
    ]

    check = check_readiness_contract(rows)

    assert check.ok is True
    assert "strict=strict_ready" in check.detail


def test_smoke_readiness_contract_rejects_blocked_readiness() -> None:
    rows = [
        SimpleNamespace(
            id="memory.readiness",
            raw={
                "schema_version": "memory_kernel_readiness.v1",
                "readiness_status": "degraded",
                "strict_readiness_state": "strict_blocked",
                "strict_ready": False,
                "accounted_surface_count": 7,
                "accounted_surface_total": 81,
                "required_surface_count": 7,
                "required_accounted_surface_count": 7,
                "warning_count": 95,
            },
        )
    ]

    check = check_readiness_contract(rows)

    assert check.ok is False
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
                "max_ready_tier": "m2_strict_read_only",
                "rollout_exceeds_ready_tier": False,
            },
        )
    ]

    check = check_burn_in_safety(rows)

    assert check.ok is True
    assert "blockers=<none>" in check.detail


def test_smoke_burn_in_safety_rejects_tier_exceeded() -> None:
    rows = [
        SimpleNamespace(
            id="memory.rollout_gate",
            observed_state="live",
            raw={
                "burn_in_safety_state": "blocked",
                "burn_in_safe": False,
                "burn_in_blockers": ("rollout_not_above_ready_tier",),
                "max_ready_tier": "m3_safe_context_preview",
                "rollout_exceeds_ready_tier": True,
            },
        )
    ]

    check = check_burn_in_safety(rows)

    assert check.ok is False
    assert "max_ready_tier=m3_safe_context_preview" in check.detail


def test_smoke_knowledgeops_bridge_contract_accepts_linked_receipt() -> None:
    rows = [
        SimpleNamespace(
            id="memory.knowledgeops_bridge",
            raw={
                "schema_version": "memory_kernel_knowledgeops_bridge.v1",
                "ready": True,
                "linked_canonical_receipt_count": 1,
                "matched_write_receipt_link_count": 1,
                "latest_source_proposal_id": "memory_promotion_proposal:abc",
                "latest_source_decision_id": "knowledgeops_promotion_decision:def",
                "latest_source_write_receipt_id": "memory_kernel_write_receipt:ghi",
                "latest_canonical_receipt_id": "memory_kernel_canonical_receipt:jkl",
            },
        )
    ]

    check = check_knowledgeops_bridge_contract(rows)

    assert check.ok is True
    assert "linked=1" in check.detail


def test_smoke_knowledgeops_bridge_contract_rejects_missing_linkage() -> None:
    rows = [
        SimpleNamespace(
            id="memory.knowledgeops_bridge",
            raw={
                "schema_version": "memory_kernel_knowledgeops_bridge.v1",
                "ready": False,
                "linked_canonical_receipt_count": 0,
                "matched_write_receipt_link_count": 0,
                "blockers": ("no_linked_knowledgeops_canonical_receipt",),
            },
        )
    ]

    check = check_knowledgeops_bridge_contract(rows)

    assert check.ok is False
    assert "no_linked_knowledgeops_canonical_receipt" in check.detail


def test_smoke_memory_home_contract_accepts_env_match(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_MEMORY_KERNEL_HOME", "/tmp/memory-home")
    rows = [
        SimpleNamespace(
            id="memory.census",
            raw={"home": "/tmp/memory-home"},
        )
    ]

    check = check_memory_home_contract(rows)

    assert check.ok is True
