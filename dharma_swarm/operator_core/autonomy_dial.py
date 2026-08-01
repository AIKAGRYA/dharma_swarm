"""Operator autonomy dial for the Sarathi apex (operator ruling 2026-07-30).

One environment variable, four levels, fail-closed parsing. The dial bounds
what Sarathi's delegation organ may EXECUTE; it never widens what the
reversibility gate (``dharma_swarm.operator_core.reversibility_gate``) allows.
Gate = floor, dial = ceiling: an action must clear BOTH.

Levels, least -> most autonomous:

- ``shadow``   — plan and log only; no mailbox writes, no dispatch.
- ``propose``  — write mailbox tasks and PR/label intents as PROPOSALS; hold
  every dispatch. First-boot default per the ruling.
- ``dispatch`` — execute gate-admissible delegations (mailbox tasks,
  ``invoke_agent`` calls with receipt + lease); merge intents stay proposals.
- ``full``     — everything ``dispatch`` allows, plus arming automerge-label
  intents into Merge Master Mike's lane.

Parsing is fail-closed in the one direction that matters: a MISSING variable
means the operator has not turned the dial, so the ruling's first-boot default
(``propose``) applies; an INVALID value means the operator tried to set the
dial and the setting was lost in transit, so the least-autonomous level
(``shadow``) applies — a garbled instruction must never grant more autonomy
than a missing one.

Stdlib-only by contract, like the reversibility gate.
"""

from __future__ import annotations

import os
from enum import Enum

ENV_VAR = "DGC_SARATHI_AUTONOMY"


class AutonomyLevel(str, Enum):
    """Operator-set autonomy ceiling for Sarathi's delegation organ."""

    SHADOW = "shadow"
    PROPOSE = "propose"
    DISPATCH = "dispatch"
    FULL = "full"


DEFAULT_LEVEL = AutonomyLevel.PROPOSE

_ORDER: tuple[AutonomyLevel, ...] = (
    AutonomyLevel.SHADOW,
    AutonomyLevel.PROPOSE,
    AutonomyLevel.DISPATCH,
    AutonomyLevel.FULL,
)


def parse_level(raw: str | None) -> AutonomyLevel:
    """Parse a raw dial value. Missing -> DEFAULT_LEVEL; invalid -> SHADOW."""
    if raw is None or not raw.strip():
        return DEFAULT_LEVEL
    try:
        return AutonomyLevel(raw.strip().lower())
    except ValueError:
        return AutonomyLevel.SHADOW


def current_autonomy_level(environ: dict[str, str] | None = None) -> AutonomyLevel:
    """The dial as currently set (reads ``DGC_SARATHI_AUTONOMY``)."""
    env = environ if environ is not None else os.environ
    return parse_level(env.get(ENV_VAR))


def at_least(level: AutonomyLevel, floor: AutonomyLevel) -> bool:
    """True when ``level`` grants at least ``floor``'s autonomy."""
    return _ORDER.index(level) >= _ORDER.index(floor)


def may_write_proposals(level: AutonomyLevel) -> bool:
    """May Sarathi write mailbox tasks / PR intents (as proposals or better)?"""
    return at_least(level, AutonomyLevel.PROPOSE)


def may_dispatch_work(level: AutonomyLevel) -> bool:
    """May Sarathi execute gate-admissible delegations?"""
    return at_least(level, AutonomyLevel.DISPATCH)


def may_arm_automerge(level: AutonomyLevel) -> bool:
    """May Sarathi arm automerge-label intents into Mike's lane?"""
    return at_least(level, AutonomyLevel.FULL)


__all__ = [
    "ENV_VAR",
    "AutonomyLevel",
    "DEFAULT_LEVEL",
    "parse_level",
    "current_autonomy_level",
    "at_least",
    "may_write_proposals",
    "may_dispatch_work",
    "may_arm_automerge",
]
