"""Canonical permission and governance controls for the shared operator core.

Delegates to ``tui.engine.governance`` — the single canonical
implementation.  This module re-exports the public API so existing
callers (tests, operator_core consumers) continue to work unchanged.
"""

from __future__ import annotations

# Re-export the canonical implementations (single source of truth)
from dharma_swarm.tui.engine.governance import (  # noqa: F401
    GovernanceFilter,
    GovernancePolicy,
    _sanitize_control_chars as sanitize_control_chars,
)

__all__ = ["GovernanceFilter", "GovernancePolicy", "sanitize_control_chars"]
