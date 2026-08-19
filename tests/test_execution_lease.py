from __future__ import annotations

from pathlib import Path

from dharma_swarm.operator_core.execution_lease import (
    DEFAULT_FORBIDDEN_ACTIONS,
    build_execution_lease,
    validate_execution_lease,
)


def test_requested_action_fails_closed_when_action_scope_is_empty() -> None:
    lease = build_execution_lease(issued_to="agent", allowed_actions=[])

    result = validate_execution_lease(
        lease,
        agent_uid="agent",
        requested_actions=["wake_loop_start"],
    )

    assert result.valid is False
    assert any("non-empty allowed_actions" in error for error in result.errors)


def test_non_object_lease_returns_invalid_instead_of_raising() -> None:
    result = validate_execution_lease([])  # type: ignore[arg-type]

    assert result.valid is False
    assert result.errors == ("lease must be an object",)


def test_requested_path_fails_closed_when_path_scope_is_empty(tmp_path: Path) -> None:
    lease = build_execution_lease(issued_to="agent", allowed_paths=[])

    result = validate_execution_lease(
        lease,
        agent_uid="agent",
        requested_paths=[tmp_path / "artifact"],
    )

    assert result.valid is False
    assert any("non-empty allowed_paths" in error for error in result.errors)


def test_custom_denials_cannot_remove_baseline_denials() -> None:
    lease = build_execution_lease(
        issued_to="agent",
        forbidden_actions=["custom_denial"],
    )

    assert set(DEFAULT_FORBIDDEN_ACTIONS).issubset(lease["forbidden_actions"])
    assert "custom_denial" in lease["forbidden_actions"]
    assert validate_execution_lease(lease, agent_uid="agent").valid is True


def test_explicit_action_and_path_scopes_validate(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    lease = build_execution_lease(
        issued_to="agent",
        allowed_actions=["write_artifact"],
        allowed_paths=[root],
    )

    result = validate_execution_lease(
        lease,
        agent_uid="agent",
        requested_actions=["write_artifact"],
        requested_paths=[root / "receipt.json"],
    )

    assert result.valid is True
