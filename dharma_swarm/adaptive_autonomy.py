"""Adaptive Autonomy — agents adjust freedom based on confidence and risk.

Goes beyond static permission levels. Agents start at their profile's
base autonomy level, then dynamically adjust based on:
  - Success/failure history (more failures → more cautious)
  - Risk assessment of the current action
  - Confidence of intent detection
  - Time of day (quiet hours → more cautious)
  - Circuit breaker state

The autonomy engine is the bridge between the telos gates (hard constraints)
and the profile system (soft preferences). Gates say WHAT is forbidden;
autonomy says HOW MUCH freedom the agent gets for everything else.
"""

from __future__ import annotations

import logging
import time
from collections import deque

from pydantic import BaseModel

# The risk vocabulary and RiskLevel enum live in the stdlib-only
# dharma_swarm.risk_patterns (operator ruling 2026-07-30): the referee
# workflow's tier-policy guard imports them on a bare python3 where this
# module's pydantic import is unavailable. Re-exported here so existing
# importers keep working against the same objects.
from dharma_swarm.risk_patterns import (  # noqa: F401 - re-exports are the API
    _CRITICAL_PATTERNS,
    _HIGH_RISK_PATTERNS,
    _LOW_RISK_PATTERNS,
    _MEDIUM_RISK_PATTERNS,
    _SAFE_PATTERNS,
    RiskLevel,
)
from dharma_swarm.risk_patterns import classify_risk as _classify_risk

logger = logging.getLogger(__name__)


class AutonomyDecision(BaseModel):
    """Result of an autonomy check for a specific action."""

    action: str
    risk: RiskLevel
    confidence: float = 0.0
    auto_approve: bool = False
    reason: str = ""
    escalate_to: str = ""  # "human" or agent name for review


# ── Risk Classification ──────────────────────────────────────────────
# Pattern lists moved to dharma_swarm.risk_patterns (stdlib-only) and
# re-exported above; classify_risk below delegates to the same single
# implementation.


class AdaptiveAutonomy:
    """Dynamic autonomy adjustment engine.

    Tracks success/failure history and adjusts how much freedom
    agents get for different risk levels.
    """

    def __init__(
        self,
        base_level: str = "balanced",
        history_size: int = 50,
        quiet_hours: set[int] | None = None,
    ):
        self._base = base_level
        self._history: deque[bool] = deque(maxlen=history_size)
        self._quiet_hours = quiet_hours if quiet_hours is not None else {2, 3, 4}
        self._consecutive_failures: int = 0
        self._total_decisions: int = 0

    @property
    def success_rate(self) -> float:
        """Current success rate from recent history."""
        if not self._history:
            return 1.0
        return sum(1 for x in self._history if x) / len(self._history)

    @property
    def effective_level(self) -> str:
        """Current effective autonomy level (may differ from base)."""
        rate = self.success_rate

        # Downgrade autonomy on poor performance
        if self._consecutive_failures >= 3:
            return "locked"
        if rate < 0.5:
            return "cautious"
        if rate < 0.7 and self._base in ("aggressive", "full"):
            return "balanced"

        # Quiet hours → more cautious
        if time.localtime().tm_hour in self._quiet_hours:
            if self._base in ("aggressive", "full"):
                return "balanced"

        return self._base

    def classify_risk(self, action: str) -> RiskLevel:
        """Classify the risk level of an action (delegates to risk_patterns)."""
        return _classify_risk(action)

    def should_auto_approve(
        self,
        action: str,
        risk: RiskLevel | None = None,
        confidence: float = 0.5,
    ) -> AutonomyDecision:
        """Decide whether to auto-approve an action.

        Combines base autonomy, risk level, confidence, and history.
        """
        if risk is None:
            risk = self.classify_risk(action)

        level = self.effective_level
        self._total_decisions += 1

        # Decision matrix: level × risk → auto_approve
        auto = self._check_matrix(level, risk, confidence)

        reason_parts: list[str] = []
        if not auto:
            reason_parts.append(f"level={level}")
            reason_parts.append(f"risk={risk.value}")
            if confidence < 0.5:
                reason_parts.append(f"low_confidence={confidence:.2f}")
            if self._consecutive_failures > 0:
                reason_parts.append(
                    f"consecutive_failures={self._consecutive_failures}"
                )

        escalate = ""
        if not auto:
            escalate = "human" if risk in (RiskLevel.CRITICAL, RiskLevel.HIGH) else ""

        return AutonomyDecision(
            action=action,
            risk=risk,
            confidence=confidence,
            auto_approve=auto,
            reason="; ".join(reason_parts) if reason_parts else "auto-approved",
            escalate_to=escalate,
        )

    def record_outcome(self, success: bool) -> None:
        """Record the outcome of an action. Updates history and streaks."""
        self._history.append(success)
        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                logger.warning(
                    "Autonomy degraded: %d consecutive failures",
                    self._consecutive_failures,
                )

    def reset(self) -> None:
        """Reset history and streaks."""
        self._history.clear()
        self._consecutive_failures = 0
        self._total_decisions = 0

    def stats(self) -> dict:
        """Return autonomy statistics."""
        return {
            "base_level": self._base,
            "effective_level": self.effective_level,
            "success_rate": round(self.success_rate, 3),
            "consecutive_failures": self._consecutive_failures,
            "total_decisions": self._total_decisions,
            "history_size": len(self._history),
        }

    def _check_matrix(
        self, level: str, risk: RiskLevel, confidence: float
    ) -> bool:
        """The autonomy decision matrix.

        Returns True if the action should be auto-approved.
        """
        # CRITICAL risk — never auto-approve (only human can approve)
        if risk == RiskLevel.CRITICAL:
            return False

        # LOCKED — never auto-approve anything
        if level == "locked":
            return False

        # CAUTIOUS — only auto-approve SAFE actions
        if level == "cautious":
            return risk == RiskLevel.SAFE

        # BALANCED — auto-approve SAFE and LOW, ask for MEDIUM+
        if level == "balanced":
            if risk in (RiskLevel.SAFE, RiskLevel.LOW):
                return True
            # MEDIUM with high confidence → auto
            if risk == RiskLevel.MEDIUM and confidence >= 0.8:
                return True
            return False

        # AGGRESSIVE — auto-approve up to HIGH (with good confidence)
        if level == "aggressive":
            if risk in (RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.MEDIUM):
                return True
            if risk == RiskLevel.HIGH and confidence >= 0.7:
                return True
            return False

        # FULL — auto-approve everything except CRITICAL
        if level == "full":
            return True

        return False
