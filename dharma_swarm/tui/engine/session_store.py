"""Provider-neutral session persistence for DGC TUI.

This module re-exports the canonical SessionStore from operator_core.
The TUI-specific ``_cwd_matches`` helper is preserved as a local alias
for backward compatibility with any code that imports it from here.
"""

from __future__ import annotations

from dharma_swarm.operator_core.session_store import (  # noqa: F401
    SessionStore,
    cwd_matches,
)

# Backward-compatible alias — old TUI code may import the private name.
_cwd_matches = cwd_matches
