"""Public facade for the Forge taskbed ledger.

The implementation is split by responsibility (storage, allocation, quality
reporting) so the public API stays stable without growing a god module.
"""
from __future__ import annotations

from .taskbed_campaign_overlay import (
    CAMPAIGN_LOGICAL_SPLITS,
    CAMPAIGN_LOGICAL_TO_PHYSICAL,
    allocate_campaign_pools,
    campaign_overlay_receipt,
)
from .taskbed_allocation import (
    allocate_confirm,
    allocate_explore,
    allocate_task_ids,
    allocate_tasks,
    allocation_receipt,
    allocation_rows,
    task_counts,
    task_for_id,
)
from .taskbed_quality import (
    taskbed_quality_markdown,
    taskbed_quality_report,
    write_taskbed_quality_report,
)
from .taskbed_store import (
    CLEAN_CONFIRM_STATES,
    DEFAULT_DB,
    DEFAULT_GRADE_RECEIPT_ROOTS,
    DEFAULT_QUALITY_ROOT,
    LEGACY_CONTAMINATION_STATE_MAP,
    MIN_CONFIRM_TASKS,
    TaskbedLedgerError,
    connect,
    normalize_contamination_state,
    register_task,
    register_tasks,
)

__all__ = [
    "CLEAN_CONFIRM_STATES",
    "LEGACY_CONTAMINATION_STATE_MAP",
    "normalize_contamination_state",
    "DEFAULT_DB",
    "DEFAULT_GRADE_RECEIPT_ROOTS",
    "DEFAULT_QUALITY_ROOT",
    "MIN_CONFIRM_TASKS",
    "TaskbedLedgerError",
    "CAMPAIGN_LOGICAL_SPLITS",
    "CAMPAIGN_LOGICAL_TO_PHYSICAL",
    "allocate_campaign_pools",
    "allocate_confirm",
    "allocate_explore",
    "allocate_task_ids",
    "allocate_tasks",
    "allocation_receipt",
    "allocation_rows",
    "campaign_overlay_receipt",
    "connect",
    "register_task",
    "register_tasks",
    "taskbed_quality_markdown",
    "taskbed_quality_report",
    "task_for_id",
    "task_counts",
    "write_taskbed_quality_report",
]
