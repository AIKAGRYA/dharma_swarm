"""Session-status policy: condition set, precedence, verdict, and exit.

Policy only — no collection, no rendering, no I/O.  Evidence collection lives
in ``evidence.py``; this module turns a lossless set of observed conditions
into exactly one scalar verdict/exit while retaining every secondary state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import OnboardingContractError

# Check states are exactly these six; anything else is a contract violation.
CHECK_STATES = ("pass", "fail", "warn", "needs_host", "skipped", "not_observed")

# Condition classes drive scalar precedence.  A class is about WHAT failed,
# a state is about HOW it was observed.
CONDITION_CLASSES = ("usage", "config", "toolchain", "blocking", "host", "info")

VERDICT_READY = "READY"
VERDICT_BLOCKED = "BLOCKED"
VERDICT_NEEDS_HOST = "NEEDS_HOST"
VERDICT_CONFIG_ERROR = "CONFIG_ERROR"
VERDICT_TOOLCHAIN_MISSING = "TOOLCHAIN_MISSING"
VERDICT_USAGE_ERROR = "USAGE_ERROR"

EXIT_BY_VERDICT = {
    VERDICT_READY: 0,
    VERDICT_BLOCKED: 1,
    VERDICT_USAGE_ERROR: 2,
    VERDICT_CONFIG_ERROR: 3,
    VERDICT_NEEDS_HOST: 4,
    VERDICT_TOOLCHAIN_MISSING: 5,
}

# Fixed scalar-verdict precedence:
#   usage(2) > CONFIG_ERROR(3) > TOOLCHAIN_MISSING(5) > BLOCKED(1) > NEEDS_HOST(4)
_PRECEDENCE = (
    VERDICT_USAGE_ERROR,
    VERDICT_CONFIG_ERROR,
    VERDICT_TOOLCHAIN_MISSING,
    VERDICT_BLOCKED,
    VERDICT_NEEDS_HOST,
)

_STATES_REQUIRING_REASON = {"skipped", "not_observed"}
_NONPASS_MANDATORY_STATES = {"fail", "warn", "skipped", "not_observed"}


@dataclass(frozen=True)
class Condition:
    """One observed condition.  Immutable, typed, reason-carrying."""

    id: str
    state: str
    condition_class: str = "info"
    reason: str = ""
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise OnboardingContractError("condition id must be a non-empty string")
        if self.state not in CHECK_STATES:
            raise OnboardingContractError(
                f"condition {self.id!r} has unknown state {self.state!r}"
            )
        if self.condition_class not in CONDITION_CLASSES:
            raise OnboardingContractError(
                f"condition {self.id!r} has unknown class {self.condition_class!r}"
            )
        if self.state in _STATES_REQUIRING_REASON and not self.reason:
            raise OnboardingContractError(
                f"condition {self.id!r} state {self.state!r} requires a reason"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "state": self.state,
            "class": self.condition_class,
            "reason": self.reason,
            "mandatory": self.mandatory,
        }


@dataclass(frozen=True)
class Readiness:
    """The lossless outcome: one scalar verdict plus every observed condition."""

    verdict: str
    exit_code: int
    conditions: tuple[Condition, ...]
    blockers: tuple[str, ...]
    host_gaps: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.verdict == VERDICT_READY

    def condition_ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.conditions)


def _verdict_triggers(condition: Condition) -> str | None:
    """Map one condition to the scalar verdict it argues for, if any."""
    if condition.condition_class == "usage":
        return VERDICT_USAGE_ERROR
    if condition.state == "needs_host":
        return VERDICT_NEEDS_HOST
    if condition.condition_class == "config" and condition.state == "fail":
        return VERDICT_CONFIG_ERROR
    if condition.condition_class == "toolchain" and condition.state == "fail":
        return VERDICT_TOOLCHAIN_MISSING
    # A mandatory check that is anything but a clean pass can never READY
    # Mandatory warn/skip/unavailable conditions cannot produce READY.
    if condition.mandatory and condition.state in _NONPASS_MANDATORY_STATES:
        return VERDICT_BLOCKED
    return None


def evaluate(
    conditions: Iterable[Condition],
    *,
    require_live: bool = False,
) -> Readiness:
    """Fold conditions into one scalar verdict without losing any of them.

    ``require_live`` maps required host gaps to exit 4; without it a host gap
    is typed (verdict ``NEEDS_HOST``) but exits 0, matching the run-level
    scalar-verdict precedent defined by ``_PRECEDENCE``.
    """
    ordered = tuple(sorted(conditions, key=lambda c: c.id))
    seen: dict[str, Condition] = {}
    for condition in ordered:
        if condition.id in seen:
            raise OnboardingContractError(
                f"duplicate condition id {condition.id!r}"
            )
        seen[condition.id] = condition

    votes = {_verdict_triggers(c) for c in ordered}
    votes.discard(None)

    verdict = VERDICT_READY
    for candidate in _PRECEDENCE:
        if candidate in votes:
            verdict = candidate
            break

    host_gaps = tuple(c.id for c in ordered if c.state == "needs_host")
    blockers = tuple(
        c.id
        for c in ordered
        if _verdict_triggers(c)
        in {VERDICT_BLOCKED, VERDICT_CONFIG_ERROR, VERDICT_TOOLCHAIN_MISSING,
            VERDICT_USAGE_ERROR}
    )

    exit_code = EXIT_BY_VERDICT[verdict]
    if verdict == VERDICT_NEEDS_HOST and not require_live:
        # Non-required host gap: typed, visible, exit 0 — never pass-like.
        exit_code = 0

    return Readiness(
        verdict=verdict,
        exit_code=exit_code,
        conditions=ordered,
        blockers=blockers,
        host_gaps=host_gaps,
    )


__all__ = [
    "CHECK_STATES",
    "CONDITION_CLASSES",
    "Condition",
    "EXIT_BY_VERDICT",
    "Readiness",
    "VERDICT_BLOCKED",
    "VERDICT_CONFIG_ERROR",
    "VERDICT_NEEDS_HOST",
    "VERDICT_READY",
    "VERDICT_TOOLCHAIN_MISSING",
    "VERDICT_USAGE_ERROR",
    "evaluate",
]
