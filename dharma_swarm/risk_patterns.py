"""Shared risk-classification vocabulary — stdlib-only by contract.

Extracted from ``dharma_swarm.adaptive_autonomy`` under the operator ruling of
2026-07-30 (Sarathi autonomy ceiling — see
``docs/ops/OPERATOR_RULING_2026-07-30_SARATHI_AUTONOMY_CEILING.md``): the
automerge tier-policy guard (``scripts/governance/check_automerge_tier_policy.py``)
runs on a bare ``python3`` inside the referee workflow — no pip install, no
pydantic — and must consult the same vocabulary the reversibility gate trusts.
One list, one classifier, several importers; ``adaptive_autonomy`` re-exports
these names so its existing importers are unchanged.

Stdlib-only is load-bearing: a third-party import added here (or anywhere in
this module's import chain) breaks the referee workflow's trusted-checkout
evaluation. ``tests/test_reversibility_gate.py::test_gate_import_chain_is_stdlib_only``
pins the property.
"""

from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    """Risk classification for an action."""

    SAFE = "safe"           # Read-only, no side effects
    LOW = "low"             # Minor changes, easily reversible
    MEDIUM = "medium"       # File modifications, config changes
    HIGH = "high"           # Multi-file changes, API calls, deployments
    CRITICAL = "critical"   # Destructive ops, production changes, credentials


_SAFE_PATTERNS = [
    "read", "list", "show", "display", "search", "grep", "find",
    "status", "check", "ls", "cat", "head", "tail", "echo",
]

_LOW_RISK_PATTERNS = [
    "write note", "log", "append", "create test", "add comment",
    "format", "lint", "git status", "git diff", "git log",
]

_MEDIUM_RISK_PATTERNS = [
    "edit", "modify", "update", "change", "refactor", "rename",
    "install", "pip install", "npm install", "git add", "git commit",
]

_HIGH_RISK_PATTERNS = [
    "deploy", "push", "publish", "migrate", "schema change",
    "api call", "http request", "subprocess", "exec",
    "git push", "create pr", "merge",
]

_CRITICAL_PATTERNS = [
    "delete", "rm -rf", "drop table", "force push", "reset --hard",
    "production", "credential", "secret", "api key", "token",
    "chmod 777", "kill", "terminate",
]


def classify_risk(action: str) -> RiskLevel:
    """Classify the risk level of an action string.

    Pure function of the input — the single implementation behind both
    ``AdaptiveAutonomy.classify_risk`` and the reversibility gate. Most-severe
    vocabulary wins; unknown input fails closed to MEDIUM.
    """
    action_lower = action.lower()

    for pattern in _CRITICAL_PATTERNS:
        if pattern in action_lower:
            return RiskLevel.CRITICAL

    for pattern in _HIGH_RISK_PATTERNS:
        if pattern in action_lower:
            return RiskLevel.HIGH

    for pattern in _MEDIUM_RISK_PATTERNS:
        if pattern in action_lower:
            return RiskLevel.MEDIUM

    for pattern in _LOW_RISK_PATTERNS:
        if pattern in action_lower:
            return RiskLevel.LOW

    for pattern in _SAFE_PATTERNS:
        if pattern in action_lower:
            return RiskLevel.SAFE

    return RiskLevel.MEDIUM  # default to medium if unknown


__all__ = [
    "RiskLevel",
    "classify_risk",
    "_SAFE_PATTERNS",
    "_LOW_RISK_PATTERNS",
    "_MEDIUM_RISK_PATTERNS",
    "_HIGH_RISK_PATTERNS",
    "_CRITICAL_PATTERNS",
]
