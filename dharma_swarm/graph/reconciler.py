# spine: reconciles delegation_runs/task_claims orphans (owner: runtime_state)
"""Boot and periodic recovery for the runtime truth spine.

Ordinary legacy rows retain their historical requeue/quarantine behavior.
Campaign rows are stricter: only an exact orchestrator-owned V4 identity may
be consumed, and absence of terminal receipt authority produces a durable
effect-indeterminate hold rather than inferred cessation or retry authority.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any

import aiosqlite

from dharma_swarm.graph.receipt_authority import claim_run_match, has_runtime_completion
from dharma_swarm.loop_closure_quarantine import QUARANTINE_COLUMNS, parse_ts
from dharma_swarm.runtime_state import RuntimeStateStore
from .reconcile_board import (
    BOARD_COMPLETION_BINDING_KEY,
    has_reserved_task_board_projection,
    prepare_task_board_projection_snapshot,
    recovery_task_board_projection_metadata,
    settle_task_board,
    terminal_task_board_projection_metadata,
)
from .reconcile_board_campaign import (
    campaign_attempt_classification,
    campaign_hold_metadata,
    canonical_claim_execution,
    canonical_orchestrator_execution,
    explicit_legacy_runtime_compatibility,
    explicit_legacy_runtime_execution,
    heartbeat_live_claims_exact,
)
from .reconcile_board_legacy import (
    authoritative_effect_board,
    ensure_legacy_settlement_ledger,
    explicit_weak_test_board,
    prepare_legacy_settlement,
    settle_legacy_task_board,
)
from .reconcile_board_only import snapshot_board_recovery_census

__all__ = ["ClaimHeartbeatError", "GraphReconciler", "ReconcileReport"]

logger = logging.getLogger(__name__)

IN_FLIGHT_STATUSES = ("claimed", "running")
TERMINAL_CLAIM_STATUSES = frozenset({"completed", "failed", "recovered", "cancelled"})
FAILURE_CODE_NEVER_STARTED = "claim_timeout"
FAILURE_CODE_DIED_MID_DISPATCH = "dispatch_dropoff"
QUARANTINE_REASON = "reconciler_retry_exhausted"
LIVE_ROW_PREDICATE = "(quarantined_at IS NULL OR quarantined_at = '')"


class ClaimHeartbeatError(RuntimeError):
    """A heartbeat batch could not preserve exact live-claim authority."""


def _invalidate_census_on_exception(method: Any) -> Any:
    @wraps(method)
    async def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await method(self, *args, **kwargs)
        except BaseException:
            self.invalidate_boot_census()
            raise

    return guarded


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


async def _ensure_quarantine_columns(db: aiosqlite.Connection) -> None:
    for name, sql_type in QUARANTINE_COLUMNS:
        try:
            await db.execute(f"SELECT {name} FROM delegation_runs LIMIT 0")
        except aiosqlite.Error:
            try:
                await db.execute(
                    f"ALTER TABLE delegation_runs ADD COLUMN {name} {sql_type}"
                )
                await db.commit()
            except aiosqlite.Error:
                logger.debug("reconciler: quarantine migration raced for %s", name)


@dataclass
class ReconcileReport:
    """Tally of one pass; errors always fence readiness."""

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
    """Recover orphaned dispatch state and replay terminal Board intents."""

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
        self._boot_census_succeeded = False
        self._boot_recovery_completed = False

    @property
    def boot_census_succeeded(self) -> bool:
        return self._boot_census_succeeded

    @property
    def boot_recovery_completed(self) -> bool:
        return self._boot_recovery_completed

    def invalidate_boot_census(self) -> None:
        self._boot_census_succeeded = False

    @_invalidate_census_on_exception
    async def reconcile(
        self,
        *,
        now: datetime | None = None,
        stale_only: bool = False,
    ) -> ReconcileReport:
        now = now or _utc_now()
        first_boot_sweep = not stale_only and not self._boot_recovery_completed
        effective_stale_only = stale_only or self._boot_recovery_completed
        if first_boot_sweep:
            self._boot_census_succeeded = False
        report = ReconcileReport()
        await self._runtime_state.init_db()
        board_tasks, board_read_errors, board_only_errors = (
            await snapshot_board_recovery_census(
                runtime_state=self._runtime_state,
                task_board=self._task_board,
                now=now,
            )
        )
        for error in board_only_errors:
            self._append_error(report, error)

        async with aiosqlite.connect(self._runtime_state.db_path) as db:
            db.row_factory = aiosqlite.Row
            await _ensure_quarantine_columns(db)
            await ensure_legacy_settlement_ledger(db)
            await db.commit()
            await db.execute("BEGIN IMMEDIATE")
            rows = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                    " assigned_by, assigned_to, status, failure_code, metadata_json,"
                    " receipt_json FROM delegation_runs"
                    f" WHERE status IN ({','.join('?' for _ in IN_FLIGHT_STATUSES)})"
                    f" AND {LIVE_ROW_PREDICATE}",
                    IN_FLIGHT_STATUSES,
                )
            ).fetchall()
            for row in rows:
                await db.execute("SAVEPOINT reconcile_run")
                try:
                    await self._reconcile_run_row(
                        db,
                        row,
                        now,
                        report,
                        stale_only=effective_stale_only,
                        board_task=board_tasks.get(str(row["task_id"])),
                        board_read_failed=str(row["task_id"]) in board_read_errors,
                    )
                except (aiosqlite.Error, KeyError, TypeError, ValueError) as exc:
                    await db.execute("ROLLBACK TO SAVEPOINT reconcile_run")
                    report.errors.append(f"run:{row['run_id']}:{type(exc).__name__}")
                    logger.error(
                        "reconciler: failed run %s: %s",
                        row["run_id"],
                        exc,
                        exc_info=True,
                    )
                finally:
                    await db.execute("RELEASE SAVEPOINT reconcile_run")
            await self._recover_stale_claims(
                db,
                now,
                report,
                stale_only=effective_stale_only,
                board_tasks=board_tasks,
                board_read_errors=board_read_errors,
            )
            await db.commit()

        # Phase two/three happens after the runtime transaction is gone.
        await settle_task_board(
            runtime_state=self._runtime_state,
            task_board=self._task_board,
            report=report,
            now=now,
            logger=logger,
        )
        await self._settle_legacy_board(report, now)
        if board_only_errors:
            _, _, final_board_only_errors = await snapshot_board_recovery_census(
                runtime_state=self._runtime_state,
                task_board=self._task_board,
                now=now,
            )
            report.errors = [
                error for error in report.errors if error not in board_only_errors
            ]
            for error in final_board_only_errors:
                self._append_error(report, error)

        if report.errors:
            self._boot_census_succeeded = False
        elif first_boot_sweep:
            self._boot_recovery_completed = True
            self._boot_census_succeeded = True
        elif self._boot_recovery_completed:
            self._boot_census_succeeded = True
        if report.total_reconciled or report.recovered_claims or report.errors:
            logger.info("reconciler: pass complete %s", report.summary())
        return report

    async def _reconcile_run_row(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        now: datetime,
        report: ReconcileReport,
        *,
        stale_only: bool,
        board_task: Any | None,
        board_read_failed: bool,
    ) -> None:
        run_id = str(row["run_id"])
        task_id = str(row["task_id"])
        if has_reserved_task_board_projection(row["metadata_json"]):
            self._append_error(report, f"projection:{run_id}:reserved_on_in_flight")
            return
        claim_id = str(row["claim_id"] or "")
        observed_claim = await self._fetch_claim(db, claim_id) if claim_id else None
        claim = observed_claim
        if claim is not None and not claim_run_match(claim, row):
            claim = None

        campaign_bound, campaign_error = campaign_attempt_classification(
            task_id=task_id,
            board_task=board_task,
            runtime_raws=(
                row["metadata_json"],
                (
                    observed_claim["metadata_json"]
                    if observed_claim is not None
                    else None
                ),
            ),
        )
        canonical = canonical_orchestrator_execution(row, row["metadata_json"])
        legacy_compatible = explicit_legacy_runtime_execution(
            row, row["metadata_json"]
        )
        if board_read_failed:
            self._append_error(report, f"task:{task_id}:board_read_failed")
            return
        if (
            canonical is not None
            and observed_claim is not None
            and (
                claim is None
                or not canonical_claim_execution(observed_claim, canonical)
            )
        ):
            self._append_error(report, f"claim:{claim_id}:attempt_identity_mismatch")
            return
        if campaign_bound and canonical is None:
            self._append_error(report, f"campaign_run:{run_id}:unknown_runtime_owner")
            return
        if not campaign_bound and canonical is None and not legacy_compatible:
            self._append_error(report, f"run:{run_id}:unknown_runtime_owner")
            return
        if campaign_error:
            self._append_error(report, f"campaign_task:{task_id}:{campaign_error}")
        if canonical is None and self._task_board is not None:
            strong_board = authoritative_effect_board(self._task_board)
            weak_test_board = explicit_weak_test_board(self._task_board)
            if not (strong_board or weak_test_board):
                self._append_error(
                    report,
                    f"legacy_projection:{run_id}:unsupported_board_effect_mode",
                )
                return
            if strong_board and board_task is None:
                self._append_error(
                    report,
                    f"legacy_projection:{run_id}:missing_exact_predecessor",
                )
                return

        receipt = _load_json(row["receipt_json"])
        receipt_bound = bool(
            receipt
            and await has_runtime_completion(
                db,
                run_id=run_id,
                task_id=task_id,
                claim_id=claim_id,
                receipt=receipt,
            )
        )
        if receipt_bound:
            if canonical is not None:
                await self._complete_from_receipt_exact(
                    db, row, claim, receipt, now
                )
                if not await prepare_task_board_projection_snapshot(db, run_id=run_id):
                    raise ValueError("receipt ProjectionIntent prepare failed")
            else:
                await self._complete_from_receipt_legacy(
                    db,
                    row,
                    claim,
                    receipt,
                    now,
                    board_task=board_task,
                )
            report.completed_from_receipt.append(run_id)
            return
        if receipt:
            logger.warning("reconciler: ignoring unbound receipt for run %s", run_id)

        # A malformed campaign carrier is itself a claim of governed
        # authority.  It can never degrade into ordinary legacy recovery;
        # only an exact durable receipt above may resolve the runtime truth.
        if campaign_error:
            return

        if campaign_bound:
            if claim is None:
                self._append_error(report, f"campaign_run:{run_id}:missing_exact_claim")
                await self._hold_campaign_dispatch(db, row, None, now)
                return
            if stale_only and not self._claim_is_stale(claim, now):
                return
            self._append_error(report, f"campaign_run:{run_id}:effect_indeterminate")
            await self._hold_campaign_dispatch(db, row, claim, now)
            return
        if canonical is not None and self._task_board is not None and board_task is None:
            self._append_error(report, f"task:{task_id}:board_task_missing")
            return
        if stale_only and not self._claim_is_stale(claim, now):
            return

        started = claim is not None and bool(claim["acked_at"] or claim["heartbeat_at"])
        retry_count = int(claim["retry_count"]) if claim is not None else 0
        failure_code = (
            FAILURE_CODE_DIED_MID_DISPATCH if started else FAILURE_CODE_NEVER_STARTED
        )
        quarantined = started and retry_count >= self._max_retries
        strict_projection = canonical is not None and board_task is not None
        board_binding = None
        if strict_projection:
            board_metadata = getattr(board_task, "metadata", {})
            if isinstance(board_metadata, dict):
                raw_binding = board_metadata.get(BOARD_COMPLETION_BINDING_KEY)
                board_binding = dict(raw_binding) if isinstance(raw_binding, dict) else None
        result = self._recovery_result(
            action="quarantine" if quarantined else "requeue",
            run_id=run_id,
        )
        if quarantined:
            await self._quarantine_run(
                db,
                row,
                now,
                failure_code,
                projection=strict_projection,
                board_result=result,
                board_completion_binding=board_binding,
                board_task=board_task,
            )
        else:
            await self._requeue_run(
                db,
                row,
                now,
                failure_code,
                retry_count + 1,
                projection=strict_projection,
                board_result=result,
                board_completion_binding=board_binding,
                board_task=board_task,
            )
        if claim is not None:
            await self._stamp_claim_recovered(
                db,
                claim_id,
                now,
                retry_count=retry_count + 1,
                recovery_reason=failure_code,
            )
        if strict_projection and not await prepare_task_board_projection_snapshot(
            db, run_id=run_id
        ):
            raise ValueError("recovery ProjectionIntent prepare failed")
        (report.quarantined_runs if quarantined else report.requeued_runs).append(run_id)
        if claim is not None:
            report.recovered_claims.append(claim_id)

    async def _receipt_projection_inputs(
        self,
        db: aiosqlite.Connection,
        *,
        row: aiosqlite.Row,
        receipt: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        receipt_id = str(receipt.get("receipt_id") or "")
        record = await (
            await db.execute(
                "SELECT idempotency_key, side_effect_key, metadata_json"
                " FROM idempotency_records WHERE run_id = ? AND task_id = ?"
                " AND result_receipt_id = ?",
                (str(row["run_id"]), str(row["task_id"]), receipt_id),
            )
        ).fetchone()
        if record is None:
            raise ValueError("bound receipt lacks idempotency carrier")
        record_metadata = _load_json(record["metadata_json"])
        if receipt.get("status") == "ok":
            encoded = record_metadata.get("result_json")
            try:
                result = json.loads(encoded) if isinstance(encoded, str) else None
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError("successful receipt lacks exact result") from exc
            if not isinstance(result, str):
                raise ValueError("successful receipt result is not a string")
        else:
            error_source = receipt.get("error_source")
            detail = receipt.get("error_detail")
            if not (
                isinstance(error_source, str)
                and error_source.strip()
                and error_source != "none"
                and isinstance(detail, str)
                and detail.strip()
            ):
                raise ValueError("failed receipt lacks exact error detail")
            result = detail
        attributes = receipt.get("attributes")
        attributes = attributes if isinstance(attributes, dict) else {}
        binding = {
            "schema_version": "dharma.graph.task_board_completion_binding.v1",
            "task_id": str(row["task_id"]),
            "run_id": str(row["run_id"]),
            "claim_id": str(receipt.get("claim_id") or ""),
            "agent_id": str(receipt.get("agent_id") or ""),
            "receipt_id": receipt_id,
            "side_effect_key": str(record["side_effect_key"] or ""),
            "idempotency_key": str(record["idempotency_key"] or ""),
            "dispatch_idempotency_key": str(
                attributes.get("dispatch_idempotency_key") or ""
            ),
            "result_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
        }
        return result, binding

    async def _complete_from_receipt_exact(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        claim: aiosqlite.Row | None,
        receipt: dict[str, Any],
        now: datetime,
    ) -> None:
        result, binding = await self._receipt_projection_inputs(
            db, row=row, receipt=receipt
        )
        receipt_ok = receipt.get("status") == "ok"
        run_status = "completed" if receipt_ok else "failed"
        failure_code = "" if receipt_ok else str(receipt["error_source"])
        metadata = _load_json(row["metadata_json"])
        metadata.pop("campaign_recovery_hold", None)
        metadata.update(
            {
                "status": run_status,
                "error": "" if receipt_ok else result,
                "reconciled_at": now.isoformat(),
                "reconciled_from_receipt": True,
            }
        )
        metadata = terminal_task_board_projection_metadata(
            metadata,
            task_id=str(row["task_id"]),
            run_id=str(row["run_id"]),
            run_status=run_status,
            board_result=result,
            completion_binding=binding,
            now=now,
            source="graph_reconciler.bound_idempotency_receipt",
            board_metadata_set={
                "reconciled_at": now.isoformat(),
                "reconciled_from_receipt": True,
            },
            board_metadata_remove=["active_claim"],
        )
        await db.execute(
            "UPDATE delegation_runs SET status = ?, failure_code = ?,"
            " completed_at = ?, metadata_json = ? WHERE run_id = ?",
            (
                run_status,
                failure_code,
                now.isoformat(),
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                str(row["run_id"]),
            ),
        )
        await self._close_claim_from_receipt(db, claim, run_status, now)

    async def _complete_from_receipt_legacy(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        claim: aiosqlite.Row | None,
        receipt: dict[str, Any],
        now: datetime,
        *,
        board_task: Any | None,
    ) -> None:
        receipt_ok = receipt.get("status") == "ok"
        status = "completed" if receipt_ok else "failed"
        failure = "" if receipt_ok else str(receipt.get("error_source") or "execution_error")
        metadata = _load_json(row["metadata_json"])
        metadata["reconciled_at"] = now.isoformat()
        metadata["reconciled_from_receipt"] = True
        await db.execute(
            "UPDATE delegation_runs SET status = ?, failure_code = ?,"
            " completed_at = ?, metadata_json = ? WHERE run_id = ?",
            (status, failure, now.isoformat(), json.dumps(metadata), str(row["run_id"])),
        )
        if self._task_board is not None:
            await prepare_legacy_settlement(
                db,
                run_id=str(row["run_id"]),
                task_id=str(row["task_id"]),
                claim_id=str(row["claim_id"] or ""),
                agent_id=str(row["assigned_to"] or ""),
                action="complete" if status == "completed" else "fail",
                result=self._recovery_result(
                    action="receipt",
                    run_id=str(row["run_id"]),
                    run_status=status,
                ),
                metadata_set={"reconciled_at": now.isoformat()},
                board_task=board_task,
                weak_test_mode=explicit_weak_test_board(self._task_board),
                now=now,
            )
        await self._close_claim_from_receipt(db, claim, status, now)

    async def _close_claim_from_receipt(
        self,
        db: aiosqlite.Connection,
        claim: aiosqlite.Row | None,
        status: str,
        now: datetime,
    ) -> None:
        if claim is None:
            return
        current = str(claim["status"])
        if current in TERMINAL_CLAIM_STATUSES and current != status:
            raise ValueError("terminal claim conflicts with receipt")
        metadata = _load_json(claim["metadata_json"])
        metadata.pop("campaign_recovery_hold", None)
        metadata["reconciled_from_receipt"] = True
        await db.execute(
            "UPDATE task_claims SET status = ?, recovered_at = ?, metadata_json = ?"
            " WHERE claim_id = ?",
            (status, now.isoformat(), json.dumps(metadata), str(claim["claim_id"])),
        )

    async def _requeue_run(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        now: datetime,
        failure_code: str,
        retry_count: int,
        *,
        projection: bool,
        board_result: str,
        board_completion_binding: dict[str, Any] | None,
        board_task: Any | None,
    ) -> None:
        metadata = _load_json(row["metadata_json"])
        metadata.update(
            {
                "status": "failed",
                "error": board_result,
                "reconciled_at": now.isoformat(),
                "retry_count": retry_count,
                "last_failure_source": failure_code,
            }
        )
        if projection:
            metadata = recovery_task_board_projection_metadata(
                metadata,
                task_id=str(row["task_id"]),
                run_id=str(row["run_id"]),
                board_result=board_result,
                now=now,
                action="requeue",
                completion_binding=board_completion_binding,
            )
        await db.execute(
            "UPDATE delegation_runs SET status = 'failed', failure_code = ?,"
            " completed_at = ?, metadata_json = ? WHERE run_id = ?",
            (
                failure_code,
                now.isoformat(),
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                str(row["run_id"]),
            ),
        )
        if not projection and self._task_board is not None:
            await prepare_legacy_settlement(
                db,
                run_id=str(row["run_id"]),
                task_id=str(row["task_id"]),
                claim_id=str(row["claim_id"] or ""),
                agent_id=str(row["assigned_to"] or ""),
                action="requeue",
                result=board_result,
                metadata_set={"reconciled_at": now.isoformat()},
                board_task=board_task,
                weak_test_mode=explicit_weak_test_board(self._task_board),
                now=now,
            )

    async def _quarantine_run(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        now: datetime,
        failure_code: str,
        *,
        projection: bool,
        board_result: str,
        board_completion_binding: dict[str, Any] | None,
        board_task: Any | None,
    ) -> None:
        metadata = _load_json(row["metadata_json"])
        metadata.update(
            {
                "status": "failed",
                "error": board_result,
                "reconciled_at": now.isoformat(),
            }
        )
        if projection:
            metadata = recovery_task_board_projection_metadata(
                metadata,
                task_id=str(row["task_id"]),
                run_id=str(row["run_id"]),
                board_result=board_result,
                now=now,
                action="quarantine",
                completion_binding=board_completion_binding,
            )
        await db.execute(
            "UPDATE delegation_runs SET status = 'failed', failure_code = ?,"
            " completed_at = ?, quarantined_at = ?, quarantine_reason = ?,"
            " metadata_json = ? WHERE run_id = ?",
            (
                failure_code,
                now.isoformat(),
                now.isoformat(),
                QUARANTINE_REASON,
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                str(row["run_id"]),
            ),
        )
        if not projection and self._task_board is not None:
            await prepare_legacy_settlement(
                db,
                run_id=str(row["run_id"]),
                task_id=str(row["task_id"]),
                claim_id=str(row["claim_id"] or ""),
                agent_id=str(row["assigned_to"] or ""),
                action="fail",
                result=board_result,
                metadata_set={"reconciled_at": now.isoformat()},
                board_task=board_task,
                weak_test_mode=explicit_weak_test_board(self._task_board),
                now=now,
            )

    async def _hold_campaign_dispatch(
        self,
        db: aiosqlite.Connection,
        row: aiosqlite.Row,
        claim: aiosqlite.Row | None,
        now: datetime,
    ) -> None:
        task_id = str(row["task_id"])
        claim_id = str(row["claim_id"] or "")
        run_id = str(row["run_id"])
        await db.execute(
            "UPDATE delegation_runs SET metadata_json = ? WHERE run_id = ?",
            (
                json.dumps(
                    campaign_hold_metadata(
                        row["metadata_json"],
                        now,
                        task_id=task_id,
                        claim_id=claim_id,
                        run_id=run_id,
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                run_id,
            ),
        )
        if claim is not None:
            await db.execute(
                "UPDATE task_claims SET metadata_json = ? WHERE claim_id = ?",
                (
                    json.dumps(
                        campaign_hold_metadata(
                            claim["metadata_json"],
                            now,
                            task_id=task_id,
                            claim_id=claim_id,
                            run_id=run_id,
                        ),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    claim_id,
                ),
            )

    async def _fetch_claim(
        self,
        db: aiosqlite.Connection,
        claim_id: str,
    ) -> aiosqlite.Row | None:
        return await (
            await db.execute(
                "SELECT claim_id, task_id, session_id, status, acked_at, heartbeat_at,"
                " agent_id, claimed_at, stale_after, recovered_at, retry_count,"
                " metadata_json FROM task_claims WHERE claim_id = ?",
                (claim_id,),
            )
        ).fetchone()

    def _claim_is_stale(self, claim: Any | None, now: datetime) -> bool:
        if claim is None:
            return False
        stale_after = parse_ts(claim["stale_after"])
        if stale_after is None or stale_after >= now:
            return False
        heartbeat = parse_ts(claim["heartbeat_at"])
        if heartbeat is None:
            return True
        claimed = parse_ts(claim["claimed_at"])
        lease = (
            (stale_after - claimed).total_seconds()
            if claimed is not None and stale_after > claimed
            else self._default_heartbeat_window * 3.0
        )
        return (now - heartbeat).total_seconds() >= lease

    async def _stamp_claim_recovered(
        self,
        db: aiosqlite.Connection,
        claim_id: str,
        now: datetime,
        *,
        retry_count: int,
        recovery_reason: str,
    ) -> None:
        claim = await self._fetch_claim(db, claim_id)
        if claim is None:
            return
        metadata = _load_json(claim["metadata_json"])
        metadata["recovery_reason"] = recovery_reason
        await db.execute(
            "UPDATE task_claims SET status = 'recovered', recovered_at = ?,"
            " retry_count = ?, metadata_json = ? WHERE claim_id = ?",
            (now.isoformat(), retry_count, json.dumps(metadata), claim_id),
        )

    async def _recover_stale_claims(
        self,
        db: aiosqlite.Connection,
        now: datetime,
        report: ReconcileReport,
        *,
        stale_only: bool,
        board_tasks: dict[str, Any],
        board_read_errors: set[str],
    ) -> None:
        rows = await (
            await db.execute(
                "SELECT claim_id, task_id, session_id, agent_id, claimed_at,"
                " heartbeat_at, stale_after, retry_count, metadata_json"
                " FROM task_claims WHERE status IN ('claimed', 'running')"
                " AND recovered_at IS NULL"
            )
        ).fetchall()
        for claim in rows:
            task_id = str(claim["task_id"])
            runs = await (
                await db.execute(
                    "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                    " assigned_by, assigned_to, status, metadata_json"
                    " FROM delegation_runs WHERE task_id = ? AND claim_id = ?"
                    " AND status IN ('claimed', 'running')"
                    f" AND {LIVE_ROW_PREDICATE}",
                    (task_id, str(claim["claim_id"])),
                )
            ).fetchall()
            exact_runs = [run for run in runs if claim_run_match(claim, run)]
            run = exact_runs[0] if len(exact_runs) == 1 else None
            campaign_bound, campaign_error = campaign_attempt_classification(
                task_id=task_id,
                board_task=board_tasks.get(task_id),
                runtime_raws=(
                    claim["metadata_json"],
                    run["metadata_json"] if run is not None else None,
                ),
            )
            if task_id in board_read_errors:
                self._append_error(report, f"task:{task_id}:board_read_failed")
                continue
            if campaign_error:
                self._append_error(
                    report,
                    f"campaign_claim:{claim['claim_id']}:{campaign_error}",
                )
                # Unknown/malformed governed authority is never ordinary
                # stale-claim recovery authority.
                continue
            canonical = (
                canonical_orchestrator_execution(run, run["metadata_json"])
                if run is not None
                else None
            )
            legacy_pair = bool(
                run is not None
                and explicit_legacy_runtime_compatibility(claim["metadata_json"])
                and explicit_legacy_runtime_execution(run, run["metadata_json"])
            )
            if run is not None and (
                canonical is None and not legacy_pair
                or canonical is not None
                and not canonical_claim_execution(claim, canonical)
            ):
                self._append_error(
                    report,
                    f"claim:{claim['claim_id']}:unknown_runtime_owner",
                )
                continue
            if campaign_bound:
                if (
                    run is None
                    or canonical is None
                    or not canonical_claim_execution(claim, canonical)
                ):
                    self._append_error(
                        report,
                        f"campaign_claim:{claim['claim_id']}:missing_canonical_run",
                    )
                    continue
                if stale_only and not self._claim_is_stale(claim, now):
                    continue
                await self._hold_campaign_dispatch(db, run, claim, now)
                continue
            if run is None and not explicit_legacy_runtime_compatibility(
                claim["metadata_json"]
            ):
                self._append_error(
                    report,
                    f"claim:{claim['claim_id']}:unknown_runtime_owner",
                )
                continue
            # A bare ordinary claim is recoverable only after its durable
            # lease expires.  Boot process loss is proven for detached runs,
            # not for an unexpired claim that may be externally owned.
            if not self._claim_is_stale(claim, now):
                continue
            claim_id = str(claim["claim_id"])
            await self._stamp_claim_recovered(
                db,
                claim_id,
                now,
                retry_count=int(claim["retry_count"]) + 1,
                recovery_reason=(
                    "stale_after_expired" if stale_only else "boot_process_loss"
                ),
            )
            if claim_id not in report.recovered_claims:
                report.recovered_claims.append(claim_id)

    async def _settle_legacy_board(
        self,
        report: ReconcileReport,
        now: datetime,
    ) -> None:
        await settle_legacy_task_board(
            runtime_state=self._runtime_state,
            task_board=self._task_board,
            report=report,
            now=now,
            logger=logger,
        )

    @staticmethod
    def _recovery_result(
        *,
        action: str,
        run_id: str,
        run_status: str = "failed",
    ) -> str:
        short = run_id[:12]
        if action == "requeue":
            return f"Graph reconciler: orphaned run {short} requeued"
        if action == "receipt" and run_status == "completed":
            return f"Graph reconciler: run {short} completed from receipt"
        detail = "quarantined (retry-exhausted)" if action == "quarantine" else "failed per receipt"
        return f"Graph reconciler: run {short} {detail}"

    @staticmethod
    def _append_error(report: ReconcileReport, value: str) -> None:
        if value not in report.errors:
            report.errors.append(value)

    def heartbeat_live_claims(self, *, now: datetime | None = None) -> int:
        """Heartbeat live claims only after a fresh successful graph census."""
        try:
            return heartbeat_live_claims_exact(
                runtime_state=self._runtime_state,
                task_board=self._task_board,
                census_succeeded=self._boot_census_succeeded,
                invalidate_census=self.invalidate_boot_census,
                default_window=self._default_heartbeat_window,
                now=now or _utc_now(),
            )
        except RuntimeError as exc:
            raise ClaimHeartbeatError(str(exc)) from exc
