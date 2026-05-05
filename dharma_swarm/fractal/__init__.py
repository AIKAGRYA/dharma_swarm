"""Fractal Room / Venture Cell — governed, recursive operating containers.

The recursive building block for Dharma Swarm's organizational structure.
Every room has the same S1-S5 viable-system structure (Beer 1972).
VentureCells extend rooms with economic accountability (Haier RenDanHeYi).

Research foundation: docs/research/FRACTAL_VENTURE_CELL_RESEARCH.md
Spec: docs/research/FRACTAL_ROOM_SPEC_V0.md
Build plan: docs/research/BUILD_PLAN_FRACTAL_ROOM_V0.md
"""

from dharma_swarm.fractal.fractal_room import (
    FractalRoom,
    RoomKind,
    RoomRegistry,
    RoomStatus,
    VentureCellV1,
    WorkPacket,
    YDSRating,
)
from dharma_swarm.fractal.room_brief import (
    render_room_section,
    render_room_summary_line,
)
from dharma_swarm.fractal.room_bridge import RoomBridge

__all__ = [
    "FractalRoom",
    "RoomBridge",
    "RoomKind",
    "RoomRegistry",
    "RoomStatus",
    "VentureCellV1",
    "WorkPacket",
    "YDSRating",
    "render_room_section",
    "render_room_summary_line",
]
