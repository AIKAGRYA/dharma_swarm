"""Action router: threshold table → human-gated remediation.

NEVER auto-merges. NEVER auto-deletes. NEVER mutates source files.
Refactor proposals are emitted as branch+PR specs for human review.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from dharma_swarm.slop.models import ModuleScore


class Action(str, Enum):
    LEDGER_ONLY = "ledger_only"
    PR_WARNING = "pr_warning"
    BLOCK_ON_REGRESSION = "block_on_regression"
    REFACTOR_PROPOSAL = "refactor_proposal"


@dataclass(frozen=True, slots=True)
class Threshold:
    lo: float
    hi: float
    action: Action

    def contains(self, p: float) -> bool:
        return self.lo <= p < self.hi


THRESHOLDS: tuple[Threshold, ...] = (
    Threshold(0.00, 0.30, Action.LEDGER_ONLY),
    Threshold(0.30, 0.50, Action.PR_WARNING),
    Threshold(0.50, 0.80, Action.BLOCK_ON_REGRESSION),
    Threshold(0.80, 1.01, Action.REFACTOR_PROPOSAL),
)


def route_score(score: ModuleScore) -> Action:
    for t in THRESHOLDS:
        if t.contains(score.p):
            return t.action
    return Action.LEDGER_ONLY


def route_all(scores: Iterable[ModuleScore]) -> Mapping[str, Action]:
    return {s.path: route_score(s) for s in scores}


def severity_summary(scores: Iterable[ModuleScore]) -> dict[str, int]:
    counts: dict[str, int] = {a.value: 0 for a in Action}
    for s in scores:
        counts[route_score(s).value] += 1
    return counts


__all__ = [
    "Action",
    "THRESHOLDS",
    "Threshold",
    "route_all",
    "route_score",
    "severity_summary",
]
