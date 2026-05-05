"""Compatibility shim for canonical operator-core governance controls."""

from __future__ import annotations

from dharma_swarm.operator_core.permissions import (
    GovernanceFilter,
    GovernancePolicy,
    sanitize_control_chars,
)

_sanitize_control_chars = sanitize_control_chars

__all__ = [
    "GovernanceFilter",
    "GovernancePolicy",
    "sanitize_control_chars",
    "_sanitize_control_chars",
]
