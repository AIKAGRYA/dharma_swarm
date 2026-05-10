"""Canonical UTC clock for dharma_swarm.

Replaces the 50+ local copies of `_utc_now` scattered across the codebase
(see audit ~/.dharma/audit/ten_megafiles_survey_2026-05-07.md).

Migration path (per docs/plans/2026-05-09-dharma-slop-governance-weave.md
Phase 9.4): each module's local `_utc_now` should be replaced with an import
from this module, then the local copy deleted. Done one module per PR to
keep blast radius small.

Two flavors are exposed because the codebase historically had two return
types: most callers want `datetime`; some want pre-formatted ISO strings.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC instant as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC instant as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


__all__ = ["utc_now", "utc_now_iso"]
