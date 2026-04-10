"""Compatibility shim for the canonical operator-core session store."""

from __future__ import annotations

from dharma_swarm.operator_core.session_store import (
    DEFAULT_ROOT,
    SessionStore,
    cwd_matches,
)

__all__ = ["DEFAULT_ROOT", "SessionStore", "cwd_matches"]
