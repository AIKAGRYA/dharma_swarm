"""Code-deterministic reversibility gate for apex/holon wake loops.

This module is the load-bearing safety invariant for an always-on apex holon
(Sarathi) that resolves its cognition model at wake time (``@frontier``). The
whole point of the gate is stated once, plainly:

    Whether an action may run unattended is decided by CODE, never by the
    resolved model's judgment.

A weak model resolved at 3am must still be structurally unable to approve an
irreversible action, because approval is a deterministic function of the action
string and operator reachability -- not an opinion the model can override. The
gate takes NO model, provider, prompt, or cognition input by construction; its
only inputs are the action text and whether the operator is reachable.

Reuse, do not rebuild: risk classification is delegated to the shared
``dharma_swarm.risk_patterns.classify_risk`` / ``RiskLevel`` vocabulary (the
same single implementation behind ``AdaptiveAutonomy.classify_risk``). This
module maps that 5-level enum onto the 4-way action class the wake loop needs,
and adds a hard ``NEVER_AUTO`` override so a handful of irreversible/
side-effecting verbs are *always* operator-gated regardless of how the pattern
classifier scored them.

Import-chain contract (operator ruling 2026-07-30): this module and everything
it imports stay stdlib-only, so the automerge tier-policy guard can call
``classify_action`` from the referee workflow's bare python3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from dharma_swarm.risk_patterns import (
    _LOW_RISK_PATTERNS,
    _SAFE_PATTERNS,
    RiskLevel,
    classify_risk,
)

if TYPE_CHECKING:  # pragma: no cover - typing only; keeps runtime stdlib-only
    from dharma_swarm.adaptive_autonomy import AdaptiveAutonomy


class ActionClass(str, Enum):
    """The 4-way action class the wake loop routes on.

    Ordering (least -> most restrictive) is deliberate and load-bearing:
    only ``REVERSIBLE_SAFE`` ever runs unattended.
    """

    REVERSIBLE_SAFE = "reversible_safe"
    NEEDS_LEASE = "needs_lease"
    IRREVERSIBLE = "irreversible"
    OPERATOR_ONLY = "operator_only"


# Hard override: verbs that are ALWAYS operator-gated no matter what the pattern
# classifier returns. These are the "back door" actions an always-on apex must
# never fire on its own while the operator walks.
NEVER_AUTO_PATTERNS: tuple[str, ...] = (
    "spend",
    "payment",
    "purchase",
    "wire transfer",
    "trade",
    "order execution",
    "external_contact",
    "send email",
    "send message",
    "outbound",
    "git push",
    "force push",
    "merge pr",
    "force merge",
    "launchd",
    "install service",
    "broker topology",
    "delete",
    "drop table",
    "rm -rf",
    "reset --hard",
    "production",
    "credential",
    "secret",
    "api key",
    "self_approve",
    "self-approve",
    "approve lease",
)


# Deterministic RiskLevel -> ActionClass mapping.
_RISK_TO_CLASS: dict[RiskLevel, ActionClass] = {
    RiskLevel.SAFE: ActionClass.REVERSIBLE_SAFE,
    RiskLevel.LOW: ActionClass.REVERSIBLE_SAFE,
    RiskLevel.MEDIUM: ActionClass.NEEDS_LEASE,
    RiskLevel.HIGH: ActionClass.IRREVERSIBLE,
    RiskLevel.CRITICAL: ActionClass.OPERATOR_ONLY,
}


_CLASS_ORDER: tuple[ActionClass, ...] = (
    ActionClass.REVERSIBLE_SAFE,
    ActionClass.NEEDS_LEASE,
    ActionClass.IRREVERSIBLE,
    ActionClass.OPERATOR_ONLY,
)


def _class_rank(action_class: ActionClass) -> int:
    return _CLASS_ORDER.index(action_class)


@dataclass(frozen=True)
class GateDecision:
    """Result of a reversibility-gate evaluation.

    ``may_execute_unattended`` is the single field the wake loop trusts. It is
    True only for ``REVERSIBLE_SAFE`` and is computed here, in code.
    """

    action: str
    risk: RiskLevel
    action_class: ActionClass
    may_execute_unattended: bool
    requires_execution_lease: bool
    operator_reachable: bool
    never_auto_hit: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "dharma.reversibility_gate_decision.v1",
            "action": self.action,
            "risk": self.risk.value,
            "action_class": self.action_class.value,
            "may_execute_unattended": self.may_execute_unattended,
            "requires_execution_lease": self.requires_execution_lease,
            "operator_reachable": self.operator_reachable,
            "never_auto_hit": self.never_auto_hit,
            "reasons": list(self.reasons),
        }


def _never_auto_match(action_lower: str) -> str:
    for pattern in NEVER_AUTO_PATTERNS:
        if pattern in action_lower:
            return pattern
    return ""


def _word_boundary_reversible(action_lower: str) -> bool:
    """True only if a SAFE/LOW verb matches on a WORD BOUNDARY.

    ``adaptive_autonomy.classify_risk`` uses loose substring matching, so
    ``"cat"`` matches inside ``"frobnicate"`` and mis-grades arbitrary text as
    SAFE. That is harmless for a normal autonomy engine but a false grant of
    *unattended execution* for an apex. The gate therefore re-confirms the
    reversible grant at word granularity before trusting it; a mid-word accident
    fails closed. The vocabulary is reused (imported) from adaptive_autonomy, not
    duplicated here.
    """
    for pattern in (*_SAFE_PATTERNS, *_LOW_RISK_PATTERNS):
        # \b handles multi-word patterns too (e.g. "git status", "write note").
        if re.search(r"\b" + re.escape(pattern) + r"\b", action_lower):
            return True
    return False


class ReversibilityGate:
    """Code-deterministic gate. Construct once; call ``classify`` per action.

    The constructor accepts an optional ``AdaptiveAutonomy`` purely to reuse its
    pattern-based ``classify_risk``. It intentionally accepts no model, provider,
    or callable-that-could-be-a-model: the gate cannot be handed cognition even
    by mistake.
    """

    def __init__(self, autonomy: AdaptiveAutonomy | None = None) -> None:
        # Default path is the pure stdlib classifier (same implementation the
        # AdaptiveAutonomy engine delegates to); constructing an engine here
        # would drag pydantic into the referee workflow's import chain.
        self._classify_risk = (
            autonomy.classify_risk if autonomy is not None else classify_risk
        )

    def classify(self, action: str, *, operator_reachable: bool = False) -> GateDecision:
        """Classify a single action string into a :class:`GateDecision`.

        Deterministic and total: any string maps to exactly one decision.
        Unknown actions inherit ``classify_risk``'s fail-closed ``MEDIUM``
        default, i.e. ``NEEDS_LEASE`` -- never ``REVERSIBLE_SAFE``.
        """
        action_lower = (action or "").lower()
        risk = self._classify_risk(action_lower)
        action_class = _RISK_TO_CLASS.get(risk, ActionClass.NEEDS_LEASE)
        reasons: list[str] = [f"risk={risk.value}->class={action_class.value}"]

        # Fail-closed re-confirmation: only trust a reversible_safe grant if a
        # SAFE/LOW verb matched on a word boundary (guards substring accidents
        # like 'cat' inside 'frobnicate'). Mid-word accident -> needs_lease.
        if action_class is ActionClass.REVERSIBLE_SAFE and not _word_boundary_reversible(
            action_lower
        ):
            action_class = ActionClass.NEEDS_LEASE
            reasons.append("reversible_grant_unconfirmed_at_word_boundary->needs_lease")

        never_hit = _never_auto_match(action_lower)
        if never_hit:
            escalated = (
                ActionClass.OPERATOR_ONLY
                if not operator_reachable
                else ActionClass.IRREVERSIBLE
            )
            if _class_rank(escalated) > _class_rank(action_class):
                action_class = escalated
            reasons.append(f"never_auto:{never_hit}->{action_class.value}")

        may_unattended = action_class is ActionClass.REVERSIBLE_SAFE
        requires_lease = action_class is ActionClass.NEEDS_LEASE

        return GateDecision(
            action=action,
            risk=risk,
            action_class=action_class,
            may_execute_unattended=may_unattended,
            requires_execution_lease=requires_lease,
            operator_reachable=operator_reachable,
            never_auto_hit=never_hit,
            reasons=tuple(reasons),
        )


def classify_action(action: str, *, operator_reachable: bool = False) -> GateDecision:
    """Module-level convenience wrapper around a default gate instance."""
    return ReversibilityGate().classify(action, operator_reachable=operator_reachable)
