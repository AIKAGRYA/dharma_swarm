"""Public TaskBoard projection API for graph/runtime consumers.

Implementation is split by transaction boundary: ``*_intent`` is runtime
phase one, while ``*_replay`` owns Board CAS plus append-only acknowledgement.
"""

from __future__ import annotations

from dharma_swarm.task_board_projection_intent import (
    GRAPH_PROJECTION_HISTORY_KEY as BOARD_PROJECTION_HISTORY_KEY,
    GRAPH_PROJECTION_KEY as BOARD_PROJECTION_RECEIPT_KEY,
    TASK_BOARD_PROJECTION_INTENT_KEY,
    TASK_BOARD_PROJECTION_WITNESS_KEY,
)

from .reconcile_board_intent import (
    BOARD_COMPLETION_BINDING_KEY,
    BOARD_COMPLETION_BINDING_SCHEMA,
    PROJECTION_WITNESS_SCHEMA,
    build_task_board_completion_binding,
    prepare_task_board_projection_snapshot,
    recovery_task_board_projection_metadata,
    terminal_task_board_projection_metadata,
)
from .reconcile_board_replay import (
    PROJECTION_ACK_SCHEMA,
    ensure_projection_ack_ledger,
    settle_task_board,
)


def has_reserved_task_board_projection(raw: object) -> bool:
    """Whether raw runtime metadata claims either projection namespace."""
    import json

    if isinstance(raw, dict):
        metadata = raw
    elif isinstance(raw, str):
        try:
            loaded = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            loaded = {}
        metadata = loaded if isinstance(loaded, dict) else {}
    else:
        metadata = {}
    return bool(
        TASK_BOARD_PROJECTION_WITNESS_KEY in metadata
        or TASK_BOARD_PROJECTION_INTENT_KEY in metadata
    )


__all__ = [
    "BOARD_COMPLETION_BINDING_KEY",
    "BOARD_COMPLETION_BINDING_SCHEMA",
    "BOARD_PROJECTION_HISTORY_KEY",
    "BOARD_PROJECTION_RECEIPT_KEY",
    "PROJECTION_ACK_SCHEMA",
    "PROJECTION_WITNESS_SCHEMA",
    "TASK_BOARD_PROJECTION_INTENT_KEY",
    "TASK_BOARD_PROJECTION_WITNESS_KEY",
    "build_task_board_completion_binding",
    "ensure_projection_ack_ledger",
    "has_reserved_task_board_projection",
    "prepare_task_board_projection_snapshot",
    "recovery_task_board_projection_metadata",
    "settle_task_board",
    "terminal_task_board_projection_metadata",
]
