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
    """Project receipt JSON onto its exact delegation run.

    Surface split (do not conflate): receipt_json is the ORCHESTRATOR-surface
    witness column (GATE-1 watches it). The A2A surface persists canonically
    via RuntimeReceipt + IdempotencyRecord and leaves receipt_json empty —
    an empty blob on an A2A row is success, not failure (see
    tests/test_spine_persistence_invariant.py invariant 7).

    ``task_id`` is deliberately insufficient because retries share it. The
    runtime-owned ``attributes.run_id`` is mandatory. When the store exposes
    the canonical ``claim_id`` and ``assigned_to`` columns, those authority
    bindings are mandatory too; compatibility schemas that predate those
    columns retain task/run scoping. Exactly one fully bound row must match.
    Callers' fail-open handlers turn any projection failure into a visible
    warning.
    """
    run_id = str(receipt.attributes.get("run_id", "") or "").strip()
    if not run_id:
        raise RuntimeError(
            "persist_receipt: missing receipt.attributes.run_id — refusing "
            "task-scoped projection"
        )
    columns_cur = await db.execute("PRAGMA table_info(delegation_runs)")
    columns = {str(row[1]) for row in await columns_cur.fetchall()}
    if not {"task_id", "run_id", "receipt_json"} <= columns:
        raise RuntimeError(
            "persist_receipt: delegation_runs lacks task/run/receipt columns"
        )

    predicates = ["task_id = ?", "run_id = ?"]
    identity: list[str] = [receipt.task_id, run_id]
    if "claim_id" in columns:
        claim_id = str(receipt.claim_id or "").strip()
        if not claim_id:
            raise RuntimeError(
                "persist_receipt: authoritative claim_id is missing"
            )
        predicates.append("claim_id = ?")
        identity.append(claim_id)
    if "assigned_to" in columns:
        agent_id = str(receipt.agent_id or "").strip()
        if not agent_id:
            raise RuntimeError(
                "persist_receipt: authoritative agent_id is missing"
            )
        predicates.append("assigned_to = ?")
        identity.append(agent_id)

    receipt_json = json.dumps(receipt.to_dict(), default=str)
    authority_clause = " AND ".join(predicates)
    cur = await db.execute(
        "UPDATE delegation_runs SET receipt_json = ?"
        f" WHERE {authority_clause}"
        " AND 1 = (SELECT COUNT(*) FROM delegation_runs"
        f" WHERE {authority_clause})",
        (receipt_json, *identity, *identity),
    )
    rowcount = getattr(cur, "rowcount", None)
    if rowcount != 1:
        raise RuntimeError(
            "persist_receipt: expected exactly one authoritative delegation_runs "
            "row for "
            f"task_id={receipt.task_id!r}, run_id={run_id!r}; matched "
            f"{rowcount!r} — receipt produced but NOT persisted"
        )
    await db.commit()
