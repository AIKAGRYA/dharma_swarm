"""Tests for the read-only operator production smoke harness."""

from __future__ import annotations

from types import SimpleNamespace

from dharma_swarm.operator_core import control_surface_memory

from scripts.operator_prod_smoke import (
    REQUIRED_MEMORY_ROW_IDS,
    check_burn_in_safety,
    check_context_shadow_report,
    check_memory_home_alignment,
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


def test_smoke_context_shadow_report_accepts_detected_synthetic_canary(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        control_surface_memory,
        "project_context_canary_report",
        lambda: {"hard_failure_count": 1, "warning_count": 0},
    )

    check = check_context_shadow_report()

    assert check.ok is True
    assert "synthetic_canary_detected=true" in check.detail
    assert "synthetic_canary_failures=1" in check.detail


def test_smoke_context_shadow_report_rejects_missing_synthetic_canary(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        control_surface_memory,
        "project_context_canary_report",
        lambda: {"hard_failure_count": 0, "warning_count": 0},
    )

    check = check_context_shadow_report()

    assert check.ok is False
    assert "synthetic_canary_detected=false" in check.detail


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
                "max_ready_tier": "m2_strict_read_only_warning_free",
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
    assert "tier=m2_strict_read_only_warning_free" in check.detail


def test_smoke_readiness_contract_rejects_blocked_readiness() -> None:
    rows = [
        SimpleNamespace(
            id="memory.readiness",
            raw={
                "schema_version": "memory_kernel_readiness.v1",
                "readiness_status": "degraded",
                "strict_readiness_state": "strict_blocked",
                "strict_ready": False,
                "max_ready_tier": "m1_required_semantic_adapters",
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


def test_smoke_readiness_contract_rejects_missing_tier() -> None:
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

    assert check.ok is False
    assert "missing_fields=max_ready_tier" in check.detail


def test_smoke_memory_home_alignment_uses_env(
    tmp_path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("DHARMA_MEMORY_KERNEL_HOME", str(home))
    rows = [
        SimpleNamespace(
            id="memory.census",
            raw={"home": str(home), "home_source": "env"},
        )
    ]

    check = check_memory_home_alignment(rows)

    assert check.ok is True
    assert f"expected={home}" in check.detail


def test_smoke_memory_home_alignment_rejects_mismatch(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DHARMA_MEMORY_KERNEL_HOME", str(tmp_path / "expected"))
    rows = [
        SimpleNamespace(
            id="memory.census",
            raw={"home": str(tmp_path / "observed"), "home_source": "env"},
        )
    ]

    check = check_memory_home_alignment(rows)

    assert check.ok is False


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


def test_smoke_burn_in_safety_rejects_blocked_preview() -> None:
    rows = [
        SimpleNamespace(
            id="memory.rollout_gate",
            observed_state="preview",
            raw={
                "burn_in_safety_state": "blocked",
                "burn_in_safe": False,
                "burn_in_blockers": ("strict_readiness_ready",),
            },
        )
    ]

    check = check_burn_in_safety(rows)

    assert check.ok is False
    assert "rollout=preview" in check.detail
    assert "strict_readiness_ready" in check.detail
