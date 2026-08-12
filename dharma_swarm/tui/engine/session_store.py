"""Legacy TUI session-store compatibility import.

Canonical owner: dharma_swarm.operator_core.session_store.SessionStore.
Compatibility expiry: 2026-11-01.

Migrate the remaining TUI callers to the canonical owner before expiry. This
module must remain a persistence-free re-export until the legacy import path is
retired.
"""

from dharma_swarm.operator_core import SessionStore

__all__ = ["SessionStore"]
