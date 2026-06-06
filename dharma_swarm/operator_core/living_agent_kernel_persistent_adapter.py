"""PersistentAgent -> LivingAgentKernel wake-payload adapter.

Pure, synchronous translation layer that turns a real
``dharma_swarm.persistent_agent.PersistentAgent`` (plus a concrete task)
into a ``persistent_self_wake`` payload dict shaped for
``LivingAgentKernel.normalize_wake_source('persistent_self_wake', payload)``.

This module is deliberately I/O-free and provider-free: it only reads the
agent's already-resolved identity surface, so importing it never triggers an
AutonomousAgent/Anthropic/OpenAI client construction. It is the dependency
root of the WIRE-IN axis — the seam that lets a live persistent agent route
through the kernel instead of the kernel remaining a zero-importer island.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime provider import
    from dharma_swarm.persistent_agent import PersistentAgent

__all__ = ["build_persistent_wake_payload"]


def _require_attr(agent: Any, attr: str) -> Any:
    if not hasattr(agent, attr):
        raise AttributeError(
            f"persistent wake adapter requires agent.{attr}; "
            f"got {type(agent).__name__} without it"
        )
    return getattr(agent, attr)


def _deterministic_correlation_id(name: str, task: str) -> str:
    digest = hashlib.sha256(f"{name}\x00{task}".encode("utf-8")).hexdigest()[:16]
    return f"persistent-self-wake-{name}-{digest}"


def build_persistent_wake_payload(
    agent: "PersistentAgent",
    *,
    task: str,
    correlation_id: str | None = None,
    work_kind: str | None = None,
    allowed_files: list[str] | None = None,
    autonomy_level: str | None = None,
) -> dict[str, Any]:
    """Build a kernel-native ``persistent_self_wake`` payload from a real agent.

    Reads the agent's resolved identity surface (``.name``, ``.wake_interval``,
    ``._witness_log``) and emits a dict whose keys are exactly the ones the
    kernel reads in ``_normalize_persistent_self_wake`` and
    ``_authority_from_payload``. The default authority stays read-only /
    ``manual``; passing ``work_kind='code_write'`` with ``allowed_files``
    promotes the work kind and populates ``authority.allowed_files``.
    """
    if not isinstance(task, str) or not task.strip():
        raise ValueError("persistent wake adapter requires a non-empty task string")
    task_text = task.strip()

    name = _require_attr(agent, "name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("persistent wake adapter requires a non-empty agent.name")
    name = name.strip()

    wake_interval = _require_attr(agent, "wake_interval")
    witness_log = _require_attr(agent, "_witness_log")

    resolved_correlation = correlation_id or _deterministic_correlation_id(name, task_text)

    payload: dict[str, Any] = {
        "name": name,
        "agent_uid": name,
        "task": task_text,
        "wake_interval_seconds": wake_interval,
        "witness_log": str(witness_log),
        "correlation_id": resolved_correlation,
    }

    if work_kind:
        payload["work_kind"] = work_kind
    if allowed_files:
        payload["allowed_files"] = list(allowed_files)
    if autonomy_level:
        payload["autonomy_level"] = autonomy_level

    return payload
