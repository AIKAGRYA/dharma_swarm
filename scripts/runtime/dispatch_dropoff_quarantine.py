#!/usr/bin/env python3
"""Quarantine historical dispatch_dropoff rows in the runtime DB (receipted).

Track loop-closure-2026-06 residual: the cybernetics_codex audit counts
full-history ``delegation_runs`` rows with ``status='failed'`` and
``failure_code='dispatch_dropoff'``; thousands predate the spine-dispatch
fixes and block any standing all-history daemon-clean claim. This tool marks
pre-cutoff rows quarantined (``quarantined_at`` + ``quarantine_reason``
columns on the EXISTING table — no new store, quarantine != delete) and
writes a JSON quarantine receipt. The audit then reports
``dropoff_live=N, dropoff_quarantined_historical=M`` — the historical tally
is excluded from live counts but never hidden, and the raw rows survive.

Safety:
  - ``--before`` is REQUIRED: fresh dropoffs can never be silently swept.
    A cutoff in the future is refused outright.
  - Dry-run is the DEFAULT and mutates nothing (not even the schema);
    pass ``--execute`` to stamp rows and write the receipt.
  - Idempotent: stamped rows leave the live predicate, so a re-run with the
    same cutoff quarantines zero new rows.

Usage (daemon host):
    python3 scripts/runtime/dispatch_dropoff_quarantine.py \
        --before 2026-06-18T00:00:00Z            # dry-run report first
    python3 scripts/runtime/dispatch_dropoff_quarantine.py \
        --before 2026-06-18T00:00:00Z --execute  # stamp + write receipt
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dharma_swarm.loop_closure_quarantine import (  # noqa: E402
    parse_ts,
    quarantine_historical_dropoffs,
)

ABSENT_HINT = "runtime DB not present on this host — nothing to quarantine (see make orient)"
DEFAULT_REASON = (
    "historical dispatch_dropoff predating spine-dispatch fixes; quarantined "
    "for the all-history daemon-clean claim (loop-closure-2026-06 residual)"
)


def _default_db_path() -> Path:
    """Canonical runtime DB path — owned by runtime_state, never hardcoded."""
    try:
        from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

        return Path(DEFAULT_RUNTIME_DB)
    except Exception:  # pragma: no cover - defensive
        return Path.home() / ".dharma" / "state" / "runtime.db"


def _default_receipt_dir() -> Path:
    # Runtime receipts belong under ~/.dharma/, not in git (CLAUDE.md rule);
    # override with --receipt-dir for repo-witnessed runs.
    return Path.home() / ".dharma" / "loop_closure"


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (table,)
    ).fetchone()
    return row is not None


def run(args: argparse.Namespace) -> dict:
    db_path = Path(args.db)
    out: dict = {
        "tool": "dispatch_dropoff_quarantine",
        "db_path": str(db_path),
        "present": False,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if not db_path.exists():
        out["detail"] = ABSENT_HINT
        return out

    conn = sqlite3.connect(str(db_path))
    try:
        if not _table_exists(conn, "delegation_runs"):
            out["detail"] = "delegation_runs table missing — nothing to quarantine"
            return out
        out["present"] = True
        result = quarantine_historical_dropoffs(
            conn,
            before=args.before_dt,
            reason=args.reason,
            execute=args.execute,
        )
        out.update(result)
    finally:
        conn.close()

    if args.execute:
        receipt_dir = Path(args.receipt_dir)
        receipt_dir.mkdir(parents=True, exist_ok=True)
        stamp = out["generated_at"].replace(":", "").replace("-", "")
        receipt_path = receipt_dir / f"dispatch_dropoff_quarantine_{stamp}.json"
        receipt_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
        out["receipt_path"] = str(receipt_path)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        default=str(_default_db_path()),
        help="runtime DB path (default: canonical runtime_state.DEFAULT_RUNTIME_DB)",
    )
    parser.add_argument(
        "--before",
        required=True,
        help="REQUIRED ISO-8601 cutoff; only dispatch_dropoff rows strictly "
        "older than this are quarantined (fresh dropoffs are never touched)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be quarantined (the DEFAULT; kept explicit)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="actually stamp rows and write the quarantine receipt",
    )
    parser.add_argument(
        "--receipt-dir",
        default=str(_default_receipt_dir()),
        help="where --execute writes the JSON quarantine receipt "
        "(default: ~/.dharma/loop_closure/ — runtime receipts never enter git)",
    )
    parser.add_argument("--reason", default=DEFAULT_REASON, help="quarantine reason recorded on each row")
    args = parser.parse_args(argv)

    if args.dry_run and args.execute:
        parser.error("--dry-run and --execute are mutually exclusive")
    cutoff = parse_ts(args.before)
    if cutoff is None:
        parser.error(f"--before is not a parseable ISO-8601 timestamp: {args.before!r}")
    if cutoff >= datetime.now(timezone.utc):
        parser.error(
            "--before is in the future; that would quarantine fresh dropoffs. "
            "Pick a cutoff before the spine-dispatch fixes landed."
        )
    args.before_dt = cutoff

    out = run(args)
    print(json.dumps(out, indent=2, sort_keys=True))
    if not out.get("present"):
        # Graceful absence is a first-class outcome (spine_tail pattern).
        return 0
    if not args.execute:
        print(
            f"\nDRY RUN — nothing mutated. {out['candidates']} row(s) would be "
            f"quarantined (fresh_live_kept={out['dropoff_fresh_live_kept']}, "
            f"undated_kept={out['dropoff_undated_kept']}). Re-run with --execute.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
