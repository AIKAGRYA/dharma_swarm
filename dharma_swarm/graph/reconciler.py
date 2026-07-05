# spine: reconciles delegation_runs/task_claims orphans (owner: runtime_state) — no new store
"""Boot-time reconciler for orphaned dispatch state.

Single-host doctrine: dispatch lives only as a detached asyncio task inside
the daemon process, so anything still in-flight in ``delegation_runs`` /
``task_claims`` at boot is orphaned by definition. This generalizes the
existing recovery pattern (``operator_bridge.recover_stale_tasks`` +
``_mirror_runtime_recovered``) down to the runtime truth-spine tables.

Rules (dharmagraph-engine-2026-07, Phase 0b):
- torn window: ``receipt_json`` present but claim non-terminal means the
  crash hit between receipt-write and claim-completion — the receipt is
  ground truth, so the run/claim are completed FROM the receipt;
- never-started orphans requeue with ``failure_code='claim_timeout'``;
- started-and-died orphans with retries left requeue (mirroring
  ``orchestrator._handle_task_failure``), incrementing ``retry_count``;
- retry-exhausted orphans are quarantined per ``loop_closure_quarantine``
  doctrine (rows stay auditable, tally always reported, never hidden);
- every reconciled claim gets ``recovered_at`` stamped.

Owner wiring is ``SwarmManager`` only (single-writer discipline): once at the
end of ``SwarmManager.init()`` and periodically from ``SwarmManager.tick()``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from dharma_swarm.loop_closure_quarantine import QUARANTINE_COLUMNS, parse_ts
from dharma_swarm.runtime_state import RuntimeStateStore

__all__ = ["GraphReconciler", "ReconcileReport"]

logger = logging.getLogger(__name__)

IN_FLIGHT_STATUSES = ("claimed", "running")
TERMINAL_CLAIM_STATUSES = frozenset({"completed", "failed", "recovered", "cancelled"})
FAILURE_CODE_NEVER_STARTED = "claim_timeout"
FAILURE_CODE_DIED_MID_DISPATCH = "dispatch_dropoff"
QUARANTINE_REASON = "reconciler_retry_exhausted"
LIVE_ROW_PREDICATE = "(quarantined_at IS NULL OR quarantined_at = '')"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _ensure_quarantine_columns(db: aiosqlite.Connection) -> None:
    """Idempotent migration mirroring loop_closure_quarantine.ensure_quarantine_columns."""
    for name, sql_type in QUARANTINE_COLUMNS:
        try:
            await db.execute(f"SELECT {name} FROM delegation_runs LIMIT 0")
        except aiosqlite.Error:
            try:
                await db.execute(
                    f"ALTER TABLE delegation_runs ADD COLUMN {name} {sql_type}"
                )
                await db.commit()
                logger.info("reconciler: added %s column to delegation_runs", name)
            except aiosqlite.Error:
                logger.debug(
                    "reconciler: %s column already exists or table missing", name
                )


def _load_json(raw: Any) -> dict[str, Any]:
    if not raw or not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class ReconcileReport:
    """Tally of one reconcile pass. The quarantine tally is always reported."""

    requeued_runs: list[str] = field(default_factory=list)
    quarantined_runs: list[str] = field(default_factory=list)
    completed_from_receipt: list[str] = field(default_factory=list)
    recovered_claims: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_reconciled(self) -> int:
        return (
            len(self.requeued_runs)
            + len(self.quarantined_runs)
            + len(self.completed_from_receipt)
        )

    def summary(self) -> dict[str, Any]:
        return {
            "requeued_runs": len(self.requeued_runs),
            "quarantined_runs": len(self.quarantined_runs),
            "completed_from_receipt": len(self.completed_from_receipt),
            "recovered_claims": len(self.recovered_claims),
            "errors": len(self.errors),
        }


class GraphReconciler:
    """Requeue-or-quarantine orphaned dispatch rows at boot and on tick.

    Writes only through the runtime.db owner's tables; a ``task_board`` may
    be supplied so requeued runs also return the underlying task to PENDING.
    """

    def __init__(
        self,
        runtime_state: RuntimeStateStore,
        task_board: Any | None = None,
        *,
        max_retries: int = 3,
        default_heartbeat_window_seconds: float = 60.0,
    ) -> None:
        self._runtime_state = runtime_state
        self._task_board = task_board
        self._max_retries = max_retries
        self._default_heartbeat_window = default_heartbeat_window_seconds

    # -- boot / tick scan ---------------------------------------------------

    async def reconcile(self, *, now: datetime | None = None) -> ReconcileReport:
        """Scan for orphaned in-flight rows and requeue/quarantine/complete them."""
        now = now or _utc_now()
        report = ReconcileReport()
        await self._runtime_state.init_db()
        async with aiosqlite.connect(self._runtime_state.db_path) as db:
            db.row_factory = aiosqlite.Row
            await _ensure_quarantine_columns(db)
            await db.execute("BEGIN IMMEDIATE")
            placeholders = ",".join("?" for _ in IN_FLIGHT_STATUSES)
            rows = await (
                await db.execute(
                    "SELECT run_id, task_id, claim_id, status, failure_code,"
                    " metadata_json, receipt_json FROM delegation_runs"
                    f" WHERE status IN ({placeholders}) AND {LIVE_ROW_PREDICATE}",
                    IN_FLIGHT_STATUSES,
                )
            ).fetchall()
            for row in rows:
                try:
                    await self._reconcile_run_row(db, row, now, report)
                except (aiosqlite.Error, ValueError, KeyError) as exc:
                    logger.error(
                        "reconciler: failed to reconcile run %s: %s",
                        row["run_id"],
                        exc,
                        exc_info=True,
                    )
                    report.errors.append(f"run:{row['run_id']}:{type(exc).__name__}")
            await self._recover_stale_claims(db, now, report)
            await db.commit()

        await self._requeue_tasks(report, now)
        if report.total_reconciled or report.recovered_claims or report.errors:
            logger.info("reconciler: pass complete %s", report.summary())
        if report.quarantined_runs:
            logger.warning(
                "reconciler: quarantined %d retry-exhausted run(s): %s",
                len(report.quarantined_runs),
                report.quarantined_runs,
            )
        return report

    async def _reconcile_run_row(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        now: datetime,
        report: ReconcileReport,
    ) -> None:
        run_id = str(row["run_id"])
        claim_id = str(row["claim_id"] or "")
        claim_row = await self._fetch_claim(db, claim_id) if claim_id else None

        receipt = _load_json(row["receipt_json"])
        if receipt:
            await self._complete_from_receipt(db, row, claim_row, receipt, now)
            report.completed_from_receipt.append(run_id)
            return

        started = claim_row is not None and bool(
            claim_row["acked_at"] or claim_row["heartbeat_at"]
        )
        retry_count = int(claim_row["retry_count"]) if claim_row is not None else 0

        if not started:
            failure_code = FAILURE_CODE_NEVER_STARTED
        else:
            failure_code = FAILURE_CODE_DIED_MID_DISPATCH

        if started and retry_count >= self._max_retries:
            await self._quarantine_run(db, row, now, failure_code)
            report.quarantined_runs.append(run_id)
        else:
            await self._requeue_run(db, row, now, failure_code, retry_count + 1)
            report.requeued_runs.append(run_id)

        if claim_row is not None:
            await self._stamp_claim_recovered(
                db,
                claim_id,
                now,
                retry_count=retry_count + 1,
                recovery_reason=failure_code,
            )
            report.recovered_claims.append(claim_id)

    # -- torn window ----------------------------------------------------------

    async def _complete_from_receipt(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        claim_row: aiosqlite.Row | None,
        receipt: dict[str, Any],
        now: datetime,
    ) -> None:
        """The crash hit between receipt-write and claim-completion.

        The receipt is ground truth: complete the run and its claim from it.
        """
        receipt_ok = str(receipt.get("status", "")) in {"ok", "completed"}
        run_status = "completed" if receipt_ok else "failed"
        failure_code = (
            "" if receipt_ok else str(receipt.get("error_source") or "execution_error")
        )
        metadata = _load_json(row["metadata_json"])
        metadata["reconciled_at"] = now.isoformat()
        metadata["reconciled_from_receipt"] = True
        await db.execute(
            "UPDATE delegation_runs SET status = ?, failure_code = ?,"
            " completed_at = ?, metadata_json = ? WHERE run_id = ?",
            (
                run_status,
                failure_code,
                now.isoformat(),
                json.dumps(metadata, default=str),
                str(row["run_id"]),
            ),
        )
        if claim_row is not None and str(claim_row["status"]) not in TERMINAL_CLAIM_STATUSES:
            claim_metadata = _load_json(claim_row["metadata_json"])
            claim_metadata["reconciled_from_receipt"] = True
            await db.execute(
                "UPDATE task_claims SET status = ?, recovered_at = ?,"
                " metadata_json = ? WHERE claim_id = ?",
                (
                    run_status,
                    now.isoformat(),
                    json.dumps(claim_metadata, default=str),
                    str(claim_row["claim_id"]),
                ),
            )
        logger.info(
            "reconciler: completed run %s from receipt (status=%s)",
            row["run_id"],
            run_status,
        )

    # -- requeue / quarantine ---------------------------------------------------

    async def _requeue_run(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        now: datetime,
        failure_code: str,
        retry_count: int,
    ) -> None:
        metadata = _load_json(row["metadata_json"])
        metadata["reconciled_at"] = now.isoformat()
        metadata["retry_count"] = retry_count
        metadata["last_failure_source"] = failure_code
        await db.execute(
            "UPDATE delegation_runs SET status = 'failed', failure_code = ?,"
            " completed_at = ?, metadata_json = ? WHERE run_id = ?",
            (
                failure_code,
                now.isoformat(),
                json.dumps(metadata, default=str),
                str(row["run_id"]),
            ),
        )
        logger.info(
            "reconciler: requeued orphaned run %s (failure_code=%s retry=%d)",
            row["run_id"],
            failure_code,
            retry_count,
        )

    async def _quarantine_run(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        now: datetime,
        failure_code: str,
    ) -> None:
        metadata = _load_json(row["metadata_json"])
        metadata["reconciled_at"] = now.isoformat()
        await db.execute(
            "UPDATE delegation_runs SET status = 'failed', failure_code = ?,"
            " completed_at = ?, quarantined_at = ?, quarantine_reason = ?,"
            " metadata_json = ? WHERE run_id = ?",
            (
                failure_code,
                now.isoformat(),
                now.isoformat(),
                QUARANTINE_REASON,
                json.dumps(metadata, default=str),
                str(row["run_id"]),
            ),
        )

    async def _requeue_tasks(self, report: ReconcileReport, now: datetime) -> None:
        """Return requeued runs' underlying tasks to PENDING on the task board."""
        if self._task_board is None or not report.requeued_runs:
            return
        for run_id in report.requeued_runs:
            run = await self._runtime_state.get_delegation_run(run_id)
            if run is None or not run.task_id:
                continue
            try:
                await self._task_board.requeue(
                    run.task_id,
                    reason=f"Graph reconciler: orphaned run {run_id[:12]} requeued",
                    metadata={"reconciled_at": now.isoformat()},
                )
            except KeyError:
                logger.warning(
                    "reconciler: task %s for run %s not on board", run.task_id, run_id
                )
            except Exception as exc:
                logger.error(
                    "reconciler: task board requeue failed for %s: %s",
                    run.task_id,
                    exc,
                    exc_info=True,
                )
                report.errors.append(f"task:{run.task_id}:{type(exc).__name__}")

    # -- claims ---------------------------------------------------------------

    async def _fetch_claim(
        self, db: aiosqlite.Connection, claim_id: str
    ) -> aiosqlite.Row | None:
        return await (
            await db.execute(
                "SELECT claim_id, task_id, status, acked_at, heartbeat_at,"
                " stale_after, recovered_at, retry_count, metadata_json"
                " FROM task_claims WHERE claim_id = ?",
                (claim_id,),
            )
        ).fetchone()

    async def _stamp_claim_recovered(
        self,
        db: aiosqlite.Connection,
        claim_id: str,
        now: datetime,
        *,
        retry_count: int,
        recovery_reason: str,
    ) -> None:
        claim_row = await self._fetch_claim(db, claim_id)
        if claim_row is None:
            return
        metadata = _load_json(claim_row["metadata_json"])
        metadata["recovery_reason"] = recovery_reason
        await db.execute(
            "UPDATE task_claims SET status = 'recovered', recovered_at = ?,"
            " retry_count = ?, metadata_json = ? WHERE claim_id = ?",
            (now.isoformat(), retry_count, json.dumps(metadata, default=str), claim_id),
        )

    async def _recover_stale_claims(
        self,
        db: aiosqlite.Connection,
        now: datetime,
        report: ReconcileReport,
    ) -> None:
        """Stamp recovered_at on stale in-flight claims (tz-aware compare)."""
        placeholders = ",".join("?" for _ in IN_FLIGHT_STATUSES)
        rows = await (
            await db.execute(
                "SELECT claim_id, stale_after, retry_count, metadata_json"
                f" FROM task_claims WHERE status IN ({placeholders})"
                " AND recovered_at IS NULL AND stale_after IS NOT NULL",
                IN_FLIGHT_STATUSES,
            )
        ).fetchall()
        for row in rows:
            stale_after = parse_ts(row["stale_after"])
            if stale_after is None or stale_after >= now:
                continue
            claim_id = str(row["claim_id"])
            try:
                await self._stamp_claim_recovered(
                    db,
                    claim_id,
                    now,
                    retry_count=int(row["retry_count"]) + 1,
                    recovery_reason="stale_after_expired",
                )
                report.recovered_claims.append(claim_id)
            except (aiosqlite.Error, ValueError) as exc:
                logger.error(
                    "reconciler: failed to recover claim %s: %s",
                    claim_id,
                    exc,
                    exc_info=True,
                )
                report.errors.append(f"claim:{claim_id}:{type(exc).__name__}")

    # -- heartbeat ---------------------------------------------------------------

    def heartbeat_live_claims(self, *, now: datetime | None = None) -> int:
        """Heartbeat in-flight claims at cadence <= (stale_after - claimed_at)/3.

        Wires the previously-orphaned ``heartbeat_claim_sync``. Single-host:
        any non-recovered in-flight claim belongs to this process (boot
        reconcile already settled prior incarnations), so refreshing
        ``heartbeat_at`` here keeps live work from tripping the stale scan.
        """
        now = now or _utc_now()
        beaten = 0
        self._runtime_state.init_db_sync()
        with sqlite3.connect(self._runtime_state.db_path) as db:
            db.row_factory = sqlite3.Row
            placeholders = ",".join("?" for _ in IN_FLIGHT_STATUSES)
            rows = db.execute(
                "SELECT claim_id, claimed_at, heartbeat_at, stale_after"
                f" FROM task_claims WHERE status IN ({placeholders})"
                " AND recovered_at IS NULL",
                IN_FLIGHT_STATUSES,
            ).fetchall()
        for row in rows:
            claimed_at = parse_ts(row["claimed_at"])
            stale_after = parse_ts(row["stale_after"])
            if claimed_at is not None and stale_after is not None:
                window = max(
                    (stale_after - claimed_at).total_seconds() / 3.0, 1.0
                )
            else:
                window = self._default_heartbeat_window
            last = parse_ts(row["heartbeat_at"]) or claimed_at
            if last is not None and (now - last).total_seconds() < window:
                continue
            try:
                self._runtime_state.heartbeat_claim_sync(str(row["claim_id"]))
                beaten += 1
            except sqlite3.Error as exc:
                logger.error(
                    "reconciler: heartbeat failed for claim %s: %s",
                    row["claim_id"],
                    exc,
                    exc_info=True,
                )
        return beaten
