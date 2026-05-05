"""dharma_swarm uplift harness — pre-commit guards.

Each guard is a callable returning (ok: bool, message: str). The pre-commit
hook composes them; CI runs the same composition. The guards are the
executable form of INTERFACE_MISMATCH_MAP, CYBERNETIC_LOOP_MAP, and the
autonomous-build damage post-mortem (commit d7af817).
"""
from __future__ import annotations

from .autonomous_guard import check_autonomous_destruction
from .shakti_warrant_guard import check_fourfold_shakti_warrant
from .kernel_guard import check_kernel_integrity
from .secrets_guard import check_no_secrets
from .hotpath_guard import check_hotpath_acknowledged
from .mismatch_registry import (
    load_mismatch_registry,
    check_mismatch_adjacency,
)

__all__ = [
    "check_autonomous_destruction",
    "check_fourfold_shakti_warrant",
    "check_kernel_integrity",
    "check_no_secrets",
    "check_hotpath_acknowledged",
    "load_mismatch_registry",
    "check_mismatch_adjacency",
]
