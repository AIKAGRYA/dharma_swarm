"""Deterministic side-effect tollbooth helpers for runtime-spine adoption.

The tollbooth is intentionally small: it validates that a side-effecting
surface has a canonical ExecutionIdentity and, in required mode, a
RuntimeStateStore capable of recording durable receipts.
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


def require_execution_tollbooth(
    *,
    execution_identity: ExecutionIdentity | None,
    runtime_state: Any | None,
    surface: str,
    action: str,
    require_identity: bool = False,
) -> ExecutionIdentity | None:
    """Return a dispatch-ready identity or fail closed in required mode."""
    if execution_identity is None:
        if require_identity:
            raise MissingExecutionIdentity(
                f"{surface}.{action} requires ExecutionIdentity before side effects"
            )
        return None

    identity = execution_identity.require_for_dispatch()
    if runtime_state is None and require_identity:
        raise MissingExecutionIdentity(
            f"{surface}.{action} requires RuntimeStateStore before side effects"
        )
    return identity
