"""Read-only VentureCell Operator OS projection."""

from __future__ import annotations

from dharma_swarm.venture_cell.operator_os.daily_digest import (
    render_operator_daily_digest,
    write_operator_daily_digest,
)
from dharma_swarm.venture_cell.operator_os.live_loader import (
    load_a2a_task_rows,
    load_live_operator_inputs,
    load_task_board_tasks,
)
from dharma_swarm.venture_cell.operator_os.memory_kernel import (
    MEMORY_KERNEL_EVAL_QUERIES,
    MemoryKernelIndexEntry,
    MemoryKernelQueryEval,
    MemoryKernelQueryResult,
    MemoryKernelReadThroughIndex,
    build_memory_kernel_index,
    evaluate_memory_kernel_queries,
    query_memory_kernel_index,
)
from dharma_swarm.venture_cell.operator_os.projection import (
    OperatorOSInputs,
    build_operator_projection,
)
from dharma_swarm.venture_cell.operator_os.schema import (
    CanvasItem,
    DarshanGoGatePacket,
    GateSummary,
    MemoryKernelRepairPacket,
    MemoryKernelSnapshot,
    OperatorDepartment,
    OperatorNextActionPacket,
    VentureCellOperatorProjection,
)

__all__ = [
    "CanvasItem",
    "DarshanGoGatePacket",
    "GateSummary",
    "MEMORY_KERNEL_EVAL_QUERIES",
    "MemoryKernelIndexEntry",
    "MemoryKernelQueryEval",
    "MemoryKernelQueryResult",
    "MemoryKernelReadThroughIndex",
    "MemoryKernelRepairPacket",
    "MemoryKernelSnapshot",
    "OperatorDepartment",
    "OperatorNextActionPacket",
    "OperatorOSInputs",
    "VentureCellOperatorProjection",
    "build_operator_projection",
    "build_memory_kernel_index",
    "evaluate_memory_kernel_queries",
    "query_memory_kernel_index",
    "load_a2a_task_rows",
    "load_live_operator_inputs",
    "load_task_board_tasks",
    "render_operator_daily_digest",
    "write_operator_daily_digest",
]
