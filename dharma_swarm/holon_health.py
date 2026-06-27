"""Holon health/observability surface (U9) — a PURE read-only projection.

Given a holon name, project its current status from files/state ONLY: whether it is
registered (identity.json exists), its model, whether a kill is pending, how many
non-binding compass signals it has logged, and whether a fresh service heartbeat
exists. No live model calls, no animation, no side effects — it just reads what
U7/U3a/the registry/service heartbeat ledger already wrote.

Reuses the canonical owners rather than re-deriving paths:
  - ``holon_killswitch.is_kill_requested`` for the kill state (U7),
  - ``holon_bridge.load_holon`` for the model (U3), degrading to None when the
    identity is absent/malformed/model-less instead of raising,
  - the compass signal log convention (``<name>/compass_signals.jsonl``, U3a).

Canonical agent home: ``~/.dharma/agents/<name>/`` (AGENT_HOME_RECONCILIATION.md).
"""
from __future__ import annotations

from pathlib import Path

from dharma_swarm import holon_bridge, holon_killswitch
from dharma_swarm.holon_service_liveness import assess_service_liveness

AGENTS_ROOT = holon_bridge.AGENTS_ROOT


def _agent_dir(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name


def _read_model(name: str, agents_root: Path | None = None) -> str | None:
    """Best-effort model read via the canonical loader. None on any failure (read-only, never raises)."""
    try:
        return holon_bridge.load_holon(name, agents_root=agents_root).model
    except Exception:
        return None


def _compass_signal_count(name: str, agents_root: Path | None = None) -> int:
    """Count non-blank lines in the holon's compass_signals.jsonl (0 when absent)."""
    path = _agent_dir(name, agents_root) / "compass_signals.jsonl"
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def holon_status(name: str, agents_root: Path | None = None) -> dict:
    """Project one holon's health as a plain dict (pure read; no side effects, never raises).

    Keys: ``name``, ``registered`` (identity.json exists), ``model`` (None if unregistered
    or unreadable), ``kill_requested`` (via holon_killswitch), ``compass_signal_count``,
    ``service_alive``, and ``service_liveness``.
    """
    registered = (_agent_dir(name, agents_root) / "identity.json").exists()
    service_liveness = assess_service_liveness(name, agents_root=agents_root)
    return {
        "name": name,
        "registered": registered,
        "model": _read_model(name, agents_root) if registered else None,
        "kill_requested": holon_killswitch.is_kill_requested(name, agents_root=agents_root),
        "compass_signal_count": _compass_signal_count(name, agents_root),
        "service_alive": bool(service_liveness["service_alive"]),
        "service_liveness": service_liveness,
    }


def holon_health_rows(agents_root: Path | None = None) -> list[dict]:
    """Project health for every registered holon under the agents root (name-sorted, deterministic).

    A directory counts as a registered holon iff it contains ``identity.json``. A missing
    agents root yields an empty list. Pure read — no side effects.
    """
    root = agents_root or AGENTS_ROOT
    if not root.exists():
        return []
    names = sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / "identity.json").exists()
    )
    return [holon_status(name, agents_root=root) for name in names]
