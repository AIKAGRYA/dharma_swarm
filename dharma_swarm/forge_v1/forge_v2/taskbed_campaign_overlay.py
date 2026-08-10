"""Frozen four-way campaign overlays on the two-pool taskbed ledger."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.forge_lab.ids import content_digest

from .taskbed_allocation import (
    CAMPAIGN_LOGICAL_SPLITS, CAMPAIGN_LOGICAL_TO_PHYSICAL,
    _eligible_rows, _insert_allocations, _rollback,
)
from .taskbed_store import (
    CLEAN_CONFIRM_STATES, DEFAULT_DB, MIN_CONFIRM_TASKS,
    TaskbedLedgerError, connect, utc_seconds,
)

def allocate_campaign_pools(
    *,
    campaign_id: str,
    train_count: int,
    explore_count: int,
    confirm_count: int,
    holdout_count: int,
    epoch_id: str,
    lane_id: str,
    db_path: Path | str = DEFAULT_DB,
    campaign_seed: int = 0,
    candidate_id: str = "",
    min_decision_count: int = MIN_CONFIRM_TASKS,
    now: float | None = None,
) -> dict[str, Any]:
    """Atomically allocate and persist a frozen four-way campaign overlay.

    ``train`` and ``explore`` share the historic physical EXPLORE pool;
    ``confirm`` and ``holdout`` share the clean physical CONFIRM pool.  The
    additive overlay table records the logical assignment without weakening
    the existing two-value CHECK constraint on ``taskbed_allocations.split``.
    Retries with identical terms are idempotent; changed terms fail closed.
    """
    campaign_id = str(campaign_id).strip()
    epoch_id = str(epoch_id).strip()
    lane_id = str(lane_id)
    if not campaign_id or not epoch_id:
        raise ValueError("campaign_id and epoch_id are required")
    counts = {
        "train": _positive_count(train_count, "train_count"),
        "explore": _positive_count(explore_count, "explore_count"),
        "confirm": _positive_count(confirm_count, "confirm_count"),
        "holdout": _positive_count(holdout_count, "holdout_count"),
    }
    min_decision_count = _positive_count(min_decision_count, "min_decision_count")
    if counts["confirm"] < min_decision_count or counts["holdout"] < min_decision_count:
        raise TaskbedLedgerError(
            "campaign decision splits below minimum: "
            f"confirm={counts['confirm']} holdout={counts['holdout']} minimum={min_decision_count}"
        )
    if (
        isinstance(campaign_seed, bool)
        or not isinstance(campaign_seed, int)
        or not -(2**63) <= campaign_seed < 2**63
    ):
        raise ValueError("campaign_seed must be a signed 64-bit integer")

    digest = hashlib.sha256(campaign_id.encode("utf-8")).hexdigest()[:24]
    allocation_ids = {
        "explore": f"campaign_{digest}_explore",
        "confirm": f"campaign_{digest}_confirm",
    }
    ts = utc_seconds() if now is None else now
    with closing(connect(db_path)) as conn:
        _ensure_campaign_overlay_schema(conn)
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = _campaign_overlay_rows(conn, campaign_id)
            if existing:
                _validate_existing_campaign_overlay(
                    conn,
                    existing,
                    campaign_id=campaign_id,
                    counts=counts,
                    epoch_id=epoch_id,
                    lane_id=lane_id,
                    campaign_seed=campaign_seed,
                    candidate_id=candidate_id,
                    allocation_ids=allocation_ids,
                )
                conn.execute("COMMIT")
                return _campaign_overlay_receipt_from_rows(campaign_id, existing)

            physical_existing = _physical_rows_for_allocation_ids(conn, allocation_ids.values())
            if physical_existing:
                raise TaskbedLedgerError(
                    "campaign overlay missing for pre-existing physical allocation IDs"
                )

            explore_rows = _eligible_rows(
                conn,
                split="explore",
                epoch_id=epoch_id,
                limit=counts["train"] + counts["explore"],
                exclude_campaign_overlays=True,
            )
            required_explore = counts["train"] + counts["explore"]
            if len(explore_rows) != required_explore:
                raise TaskbedLedgerError(
                    "insufficient_campaign_explore_tasks: "
                    f"requested={required_explore} available={len(explore_rows)}"
                )
            _insert_allocations(
                conn,
                explore_rows,
                allocation_ids["explore"],
                "explore",
                epoch_id,
                lane_id,
                candidate_id,
                ts,
            )

            # This query observes the just-inserted EXPLORE rows and therefore
            # cannot select the same task for CONFIRM inside the transaction.
            confirm_rows = _eligible_rows(
                conn,
                split="confirm",
                epoch_id=epoch_id,
                limit=counts["confirm"] + counts["holdout"],
                exclude_campaign_overlays=True,
            )
            required_confirm = counts["confirm"] + counts["holdout"]
            if len(confirm_rows) != required_confirm:
                raise TaskbedLedgerError(
                    "insufficient_campaign_confirm_tasks: "
                    f"requested={required_confirm} available={len(confirm_rows)}"
                )
            _insert_allocations(
                conn,
                confirm_rows,
                allocation_ids["confirm"],
                "confirm",
                epoch_id,
                lane_id,
                candidate_id,
                ts,
            )

            logical_rows: dict[str, list[sqlite3.Row]] = {}
            logical_rows.update(
                _partition_physical_rows(
                    explore_rows,
                    first_split="train",
                    first_count=counts["train"],
                    second_split="explore",
                    campaign_seed=campaign_seed,
                    physical_split="explore",
                )
            )
            logical_rows.update(
                _partition_physical_rows(
                    confirm_rows,
                    first_split="confirm",
                    first_count=counts["confirm"],
                    second_split="holdout",
                    campaign_seed=campaign_seed,
                    physical_split="confirm",
                )
            )
            conn.executemany(
                """
                INSERT INTO taskbed_campaign_overlays (
                  campaign_id, task_id, logical_split, physical_split,
                  allocation_id, epoch_id, lane_id, campaign_seed, allocated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        campaign_id,
                        row["task_id"],
                        logical_split,
                        CAMPAIGN_LOGICAL_TO_PHYSICAL[logical_split],
                        allocation_ids[CAMPAIGN_LOGICAL_TO_PHYSICAL[logical_split]],
                        epoch_id,
                        lane_id,
                        campaign_seed,
                        ts,
                    )
                    for logical_split in CAMPAIGN_LOGICAL_SPLITS
                    for row in logical_rows[logical_split]
                ],
            )
            persisted = _campaign_overlay_rows(conn, campaign_id)
            conn.execute("COMMIT")
        except Exception:
            _rollback(conn)
            raise
    return _campaign_overlay_receipt_from_rows(campaign_id, persisted)


def campaign_overlay_receipt(
    campaign_id: str,
    *,
    db_path: Path | str = DEFAULT_DB,
) -> dict[str, Any]:
    """Load a previously frozen campaign overlay without allocating tasks."""
    with closing(connect(db_path)) as conn:
        _ensure_campaign_overlay_schema(conn)
        rows = _campaign_overlay_rows(conn, str(campaign_id))
    if not rows:
        raise TaskbedLedgerError(f"unknown_campaign_overlay: {campaign_id}")
    return _campaign_overlay_receipt_from_rows(str(campaign_id), rows)


def _ensure_campaign_overlay_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS taskbed_campaign_overlays (
          campaign_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          logical_split TEXT NOT NULL
            CHECK(logical_split IN ('train', 'explore', 'confirm', 'holdout')),
          physical_split TEXT NOT NULL
            CHECK(physical_split IN ('explore', 'confirm')),
          allocation_id TEXT NOT NULL,
          epoch_id TEXT NOT NULL,
          lane_id TEXT NOT NULL DEFAULT '',
          campaign_seed INTEGER NOT NULL,
          allocated_at REAL NOT NULL,
          PRIMARY KEY (campaign_id, task_id),
          FOREIGN KEY(task_id) REFERENCES taskbed_tasks(task_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_taskbed_campaign_overlay_split "
        "ON taskbed_campaign_overlays(campaign_id, logical_split, task_id)"
    )
    conn.commit()


def _campaign_overlay_rows(conn: sqlite3.Connection, campaign_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT o.*, t.task_json, t.contamination_state, t.source, t.taskbed, t.created_at
          FROM taskbed_campaign_overlays o
          JOIN taskbed_tasks t ON t.task_id=o.task_id
         WHERE o.campaign_id=?
         ORDER BY o.logical_split ASC, o.task_id ASC
        """,
        (campaign_id,),
    ).fetchall()


def _physical_rows_for_allocation_ids(
    conn: sqlite3.Connection,
    allocation_ids: Iterable[str],
) -> list[sqlite3.Row]:
    values = tuple(allocation_ids)
    return conn.execute(
        "SELECT * FROM taskbed_allocations WHERE allocation_id IN (?, ?)",
        values,
    ).fetchall()


def _partition_physical_rows(
    rows: list[sqlite3.Row],
    *,
    first_split: str,
    first_count: int,
    second_split: str,
    campaign_seed: int,
    physical_split: str,
) -> dict[str, list[sqlite3.Row]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            hashlib.sha256(
                f"{campaign_seed}:{physical_split}:{row['task_id']}".encode("utf-8")
            ).hexdigest(),
            str(row["task_id"]),
        ),
    )
    return {
        first_split: ordered[:first_count],
        second_split: ordered[first_count:],
    }


def _validate_existing_campaign_overlay(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    campaign_id: str,
    counts: dict[str, int],
    epoch_id: str,
    lane_id: str,
    campaign_seed: int,
    candidate_id: str,
    allocation_ids: dict[str, str],
) -> None:
    actual_counts = {
        split: sum(row["logical_split"] == split for row in rows)
        for split in CAMPAIGN_LOGICAL_SPLITS
    }
    terms_match = all(
        str(row["campaign_id"]) == campaign_id
        and str(row["epoch_id"]) == epoch_id
        and str(row["lane_id"]) == lane_id
        and int(row["campaign_seed"]) == campaign_seed
        and str(row["physical_split"]) == CAMPAIGN_LOGICAL_TO_PHYSICAL[str(row["logical_split"])]
        and str(row["allocation_id"])
        == allocation_ids[CAMPAIGN_LOGICAL_TO_PHYSICAL[str(row["logical_split"])]]
        for row in rows
    )
    if actual_counts != counts or not terms_match:
        raise TaskbedLedgerError("campaign overlay already exists with different frozen terms")
    physical = _physical_rows_for_allocation_ids(conn, allocation_ids.values())
    expected_ids = {str(row["task_id"]) for row in rows}
    physical_ids = {str(row["task_id"]) for row in physical if row["status"] == "allocated"}
    physical_terms_match = all(
        str(row["split"]) in {"explore", "confirm"}
        and str(row["allocation_id"]) == allocation_ids[str(row["split"])]
        and str(row["epoch_id"]) == epoch_id
        and str(row["lane_id"]) == lane_id
        and str(row["candidate_id"]) == candidate_id
        for row in physical
    )
    if expected_ids != physical_ids or len(physical) != len(rows) or not physical_terms_match:
        raise TaskbedLedgerError("campaign overlay physical allocation integrity failure")

    physical_by_split = {
        split: [row for row in physical if row["split"] == split]
        for split in ("explore", "confirm")
    }
    expected_logical: dict[str, list[sqlite3.Row]] = {}
    expected_logical.update(
        _partition_physical_rows(
            physical_by_split["explore"],
            first_split="train",
            first_count=counts["train"],
            second_split="explore",
            campaign_seed=campaign_seed,
            physical_split="explore",
        )
    )
    expected_logical.update(
        _partition_physical_rows(
            physical_by_split["confirm"],
            first_split="confirm",
            first_count=counts["confirm"],
            second_split="holdout",
            campaign_seed=campaign_seed,
            physical_split="confirm",
        )
    )
    persisted_logical = {
        split: {str(row["task_id"]) for row in rows if row["logical_split"] == split}
        for split in CAMPAIGN_LOGICAL_SPLITS
    }
    recomputed_logical = {
        split: {str(row["task_id"]) for row in expected_logical[split]}
        for split in CAMPAIGN_LOGICAL_SPLITS
    }
    if persisted_logical != recomputed_logical:
        raise TaskbedLedgerError("campaign overlay deterministic partition integrity failure")


def _campaign_overlay_receipt_from_rows(
    campaign_id: str,
    rows: list[sqlite3.Row],
) -> dict[str, Any]:
    logical_splits = {
        split: sorted(str(row["task_id"]) for row in rows if row["logical_split"] == split)
        for split in CAMPAIGN_LOGICAL_SPLITS
    }
    allocation_ids = {
        physical: next(
            str(row["allocation_id"])
            for row in rows
            if row["physical_split"] == physical
        )
        for physical in ("explore", "confirm")
    }
    clean_confirm = all(
        str(row["contamination_state"]) in CLEAN_CONFIRM_STATES
        for row in rows
        if row["physical_split"] == "confirm"
    )
    receipt = {
        "schema": "forge_v2.campaign_task_overlay.v1",
        "campaign_id": campaign_id,
        "epoch_id": str(rows[0]["epoch_id"]),
        "lane_id": str(rows[0]["lane_id"]),
        "campaign_seed": int(rows[0]["campaign_seed"]),
        "logical_to_physical": dict(CAMPAIGN_LOGICAL_TO_PHYSICAL),
        "logical_splits": logical_splits,
        "physical_allocation_ids": allocation_ids,
        "task_count": len(rows),
        "task_ids": sorted(str(row["task_id"]) for row in rows),
        "all_splits_disjoint": sum(len(ids) for ids in logical_splits.values())
        == len({task_id for ids in logical_splits.values() for task_id in ids}),
        "confirm_pool_contamination_clean": clean_confirm,
        "full_decision_min_n": MIN_CONFIRM_TASKS,
        "promotion_eligible_taskbed": (
            clean_confirm
            and len(logical_splits["confirm"]) >= MIN_CONFIRM_TASKS
            and len(logical_splits["holdout"]) >= MIN_CONFIRM_TASKS
        ),
        "frozen": True,
        "positive_lift_claimed": False,
        "claim_scope": "research_only",
    }
    receipt["overlay_sha256"] = content_digest(receipt)
    return receipt


def _positive_count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value



__all__ = ["allocate_campaign_pools", "campaign_overlay_receipt"]
