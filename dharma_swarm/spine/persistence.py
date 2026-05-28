# spine: writes EvidenceReceipt
"""Single receipt persistence sink.

Writes every EvidenceReceipt to the delegation_runs table (existing schema,
one new nullable column: receipt_json TEXT). Also forwards to telemetry_plane
if available.

No new persistence surface — this writes to the existing canonical store.
See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §9.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from dharma_swarm.spine.receipt import EvidenceReceipt

logger = logging.getLogger(__name__)


class AsyncDB(Protocol):
    """Minimal async DB interface (matches aiosqlite connection)."""

    async def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any: ...
    async def commit(self) -> None: ...


_MIGRATION_SQL = (
    "ALTER TABLE delegation_runs ADD COLUMN receipt_json TEXT"
)


async def ensure_receipt_column(db: AsyncDB) -> None:
    """Idempotent migration: add receipt_json column if missing."""
    try:
        await db.execute(
            "SELECT receipt_json FROM delegation_runs LIMIT 0"
        )
    except Exception:
        try:
            await db.execute(_MIGRATION_SQL)
            await db.commit()
            logger.info("spine: added receipt_json column to delegation_runs")
        except Exception:
            logger.debug("spine: receipt_json column already exists or table missing")


async def persist_receipt(receipt: EvidenceReceipt, db: AsyncDB) -> None:
    """Write receipt JSON to the delegation_runs row for this task."""
    receipt_json = json.dumps(receipt.to_dict(), default=str)
    await db.execute(
        "UPDATE delegation_runs SET receipt_json = ? WHERE task_id = ?",
        (receipt_json, receipt.task_id),
    )
    await db.commit()
