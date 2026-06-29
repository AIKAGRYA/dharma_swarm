#!/usr/bin/env python3
"""Backfill missing idempotency_records from already-keyed runtime receipts.

This repair is intentionally narrow: it never invents ``side_effect_key`` or
``idempotency_key`` values and never rewrites ``runtime_receipts``. It only
adds the join rows that current receipt coverage expects when the canonical
runtime receipt already contains both keys.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB, RuntimeStateStore


SCHEMA_VERSION = "runtime_idempotency_backfill.v1"
DEFAULT_RECEIPT_TYPES = ("delegation_run", "a2a_task")


@dataclass(frozen=True)
class BackfillCandidate:
    receipt_id: str
    receipt_type: str
    run_id: str
    task_id: str
    trace_id: str
    correlation_id: str
    idempotency_key: str
    side_effect_key: str
    receipt_status: str
    receipt_created_at: str


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db


def _receipt_type_placeholders(receipt_types: tuple[str, ...]) -> str:
    return ", ".join("?" for _ in receipt_types)


def find_candidates(
    db_path: Path,
    *,
    receipt_types: tuple[str, ...] = DEFAULT_RECEIPT_TYPES,
    limit: int | None = None,
) -> list[BackfillCandidate]:
    """Return keyed runtime receipts that lack an idempotency_records join."""

    if not receipt_types:
        raise ValueError("receipt_types must not be empty")
    RuntimeStateStore(db_path, include_memory_plane=False).init_db_sync()
    placeholders = _receipt_type_placeholders(receipt_types)
    sql = f"""
        SELECT
          rr.receipt_id,
          rr.receipt_type,
          rr.run_id,
          rr.task_id,
          rr.trace_id,
          rr.correlation_id,
          rr.idempotency_key,
          rr.side_effect_key,
          rr.status AS receipt_status,
          rr.created_at AS receipt_created_at
        FROM runtime_receipts rr
        LEFT JOIN idempotency_records ir
          ON rr.idempotency_key = ir.idempotency_key
         AND rr.side_effect_key = ir.side_effect_key
        WHERE rr.receipt_type IN ({placeholders})
          AND coalesce(rr.idempotency_key, '') != ''
          AND coalesce(rr.side_effect_key, '') != ''
          AND ir.idempotency_key IS NULL
        ORDER BY rr.created_at ASC, rr.receipt_id ASC
    """
    params: list[Any] = list(receipt_types)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(max(0, int(limit)))
    with _connect(db_path) as db:
        rows = db.execute(sql, params).fetchall()
    return [
        BackfillCandidate(
            receipt_id=str(row["receipt_id"]),
            receipt_type=str(row["receipt_type"]),
            run_id=str(row["run_id"] or ""),
            task_id=str(row["task_id"] or ""),
            trace_id=str(row["trace_id"] or ""),
            correlation_id=str(row["correlation_id"] or ""),
            idempotency_key=str(row["idempotency_key"]),
            side_effect_key=str(row["side_effect_key"]),
            receipt_status=str(row["receipt_status"]),
            receipt_created_at=str(row["receipt_created_at"]),
        )
        for row in rows
    ]


def _candidate_metadata(candidate: BackfillCandidate) -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "source": "runtime_receipt_historical_idempotency_backfill",
            "receipt_id": candidate.receipt_id,
            "receipt_type": candidate.receipt_type,
            "receipt_status": candidate.receipt_status,
            "receipt_created_at": candidate.receipt_created_at,
            "created_from_existing_runtime_receipt": True,
            "side_effect_key_was_derived": False,
            "runtime_receipt_was_rewritten": False,
        },
        sort_keys=True,
    )


def _candidate_counts(candidates: list[BackfillCandidate]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for candidate in candidates:
        by_type[candidate.receipt_type] = by_type.get(candidate.receipt_type, 0) + 1
        key = f"{candidate.receipt_type}:{candidate.receipt_status}"
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "candidate_count": len(candidates),
        "by_receipt_type": dict(sorted(by_type.items())),
        "by_receipt_type_status": dict(sorted(by_status.items())),
    }


def backfill_missing_idempotency_records(
    db_path: Path,
    *,
    apply: bool = False,
    receipt_types: tuple[str, ...] = DEFAULT_RECEIPT_TYPES,
    limit: int | None = None,
) -> dict[str, Any]:
    """Dry-run or apply the historical idempotency_records backfill."""

    db_path = db_path.expanduser()
    candidates = find_candidates(db_path, receipt_types=receipt_types, limit=limit)
    counts = _candidate_counts(candidates)
    inserted = 0
    applied_at = ""
    if apply and candidates:
        applied_at = _utc_now_iso()
        rows = [
            (
                candidate.idempotency_key,
                candidate.side_effect_key,
                candidate.run_id,
                candidate.task_id,
                candidate.trace_id,
                candidate.correlation_id,
                "completed",
                candidate.receipt_id,
                _candidate_metadata(candidate),
                applied_at,
                applied_at,
            )
            for candidate in candidates
        ]
        with sqlite3.connect(db_path) as db:
            cur = db.executemany(
                "INSERT OR IGNORE INTO idempotency_records ("
                " idempotency_key, side_effect_key, run_id, task_id, trace_id,"
                " correlation_id, status, result_receipt_id, metadata_json,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            db.commit()
            inserted = int(cur.rowcount or 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "db_path": str(db_path),
        "mode": "apply" if apply else "dry_run",
        "receipt_types": list(receipt_types),
        "limit": limit,
        "candidate_count": counts["candidate_count"],
        "inserted_count": inserted,
        "applied_at": applied_at,
        "counts": counts,
        "sample_candidates": [asdict(item) for item in candidates[:10]],
        "safety": {
            "updates_runtime_receipts": False,
            "derives_missing_side_effect_keys": False,
            "requires_existing_idempotency_key": True,
            "requires_existing_side_effect_key": True,
        },
    }


def _parse_receipt_types(raw: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one receipt type is required")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_RUNTIME_DB)
    parser.add_argument(
        "--receipt-types",
        type=_parse_receipt_types,
        default=DEFAULT_RECEIPT_TYPES,
        help="comma-separated receipt types to backfill",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="mutate idempotency_records; without this flag the command is read-only",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = backfill_missing_idempotency_records(
        args.db,
        apply=bool(args.apply),
        receipt_types=args.receipt_types,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"mode: {result['mode']}")
        print(f"db: {result['db_path']}")
        print(f"candidates: {result['candidate_count']}")
        print(f"inserted: {result['inserted_count']}")
        print("safety: no runtime_receipts updates; no derived side_effect_key values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
