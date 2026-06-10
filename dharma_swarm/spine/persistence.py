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
from typing import Any, Protocol, Sequence

from dharma_swarm.spine.receipt import EvidenceReceipt

logger = logging.getLogger(__name__)


class AsyncDB(Protocol):
    """Minimal async DB interface (matches aiosqlite connection)."""

    async def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Any: ...
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


async def persist_receipt(receipt: EvidenceReceipt, db: AsyncDB) -> int:
    """Write receipt JSON to the delegation_runs row for this task.

    Returns the number of rows updated (0 when no delegation_runs row
    exists for the receipt's task_id).
    """
    receipt_json = json.dumps(receipt.to_dict(), default=str)
    cursor = await db.execute(
        "UPDATE delegation_runs SET receipt_json = ? WHERE task_id = ?",
        (receipt_json, receipt.task_id),
    )
    await db.commit()
    return int(getattr(cursor, "rowcount", 0) or 0)


async def persist_receipt_to_store(receipt: EvidenceReceipt, store: Any | None) -> bool:
    """Best-effort durable write of a receipt through a RuntimeStateStore.

    Opens a short-lived connection to the store's database, ensures the
    receipt_json column exists, and writes the receipt via persist_receipt.
    Never raises: dispatch must not crash because evidence persistence
    failed. Returns True only when a delegation_runs row was updated.
    """
    if store is None:
        return False
    db_path = getattr(store, "db_path", None)
    if not db_path:
        return False
    try:
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            await ensure_receipt_column(db)
            rows = await persist_receipt(receipt, db)
        if rows <= 0:
            logger.debug(
                "spine: no delegation_runs row matched task_id=%s; "
                "receipt %s not persisted",
                receipt.task_id,
                receipt.receipt_id,
            )
            return False
        return True
    except Exception:
        logger.warning(
            "spine: failed to persist EvidenceReceipt %s for task %s",
            receipt.receipt_id,
            receipt.task_id,
            exc_info=True,
        )
        return False
