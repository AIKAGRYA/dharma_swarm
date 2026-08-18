#!/usr/bin/env python3
"""Operator-gated archive/drop of the write-only `idea_links` table (audit WS-F / OP-5).

`idea_links` has zero read paths on main (recon 2026-07-25: only the now-deleted
pairwise INSERT, the DDL, and census row-counting). This script retires the
14.58M accumulated rows in two reversible phases, dry-run by default:

  phase archive : ALTER TABLE idea_links RENAME TO idea_links_archive_<stamp>
                  (metadata-only; the next ensure_memory_plane_schema call
                  recreates an empty idea_links, so census/DDL keep working)
  phase drop    : copy the archive table into a standalone backup sqlite file,
                  verify row-count parity + sha256, then DROP the archive table.
                  Run only in a later window, after idea_links count has stayed
                  flat >=3 days. VACUUM is a separate explicit flag (rewrites
                  the whole multi-GB db file).

Nothing runs against the live db without --apply. Every applied phase writes a
JSON receipt with before/after counts, backup sha256, and rollback notes.

The audit packet guardrail (ADVERSARIAL_REVIEW.md: no destructive DB op before
an off-host backup exists) is enforced as an attestation: `--phase drop --apply`
refuses to run without --offhost-copy naming where the off-host copy lives —
the local --backup-dir file is same-host/same-disk and does NOT satisfy it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".dharma" / "db" / "memory_plane.db"
DEFAULT_RECEIPT_DIR = Path.home() / ".dharma" / "witness" / "audit_impl_20260725"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _utc_time_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(db_path))
    # live db has concurrent writers; wait instead of raising "database is locked"
    db.execute("PRAGMA busy_timeout = 60000")
    return db


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _count(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _write_receipt(receipt_dir: Path, receipt: dict) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"archive_idea_links_{receipt['action']}_{_utc_time_stamp()}.json"
    with path.open("x") as handle:  # never clobber a prior run's receipt
        handle.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def _reserve_receipt(receipt_dir: Path, action: str) -> Path:
    """Reserve the receipt path BEFORE any applied mutation.

    An unwritable receipt dir, a full disk, or a same-second filename
    collision must fail the run while the database is still untouched —
    not after a committed rename/drop.
    """
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"archive_idea_links_{action}_{_utc_time_stamp()}.json"
    with path.open("x") as handle:  # exclusive create = reservation
        handle.write(json.dumps({"action": action, "status": "in_progress"}) + "\n")
    return path


def _finalize_receipt(path: Path, receipt: dict) -> Path:
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


_ARCHIVE_NAME_RE = re.compile(r"^idea_links_archive_\d{8}$")


def phase_archive(db_path: Path, *, apply: bool, receipt_dir: Path) -> int:
    archive_name = f"idea_links_archive_{_utc_stamp()}"
    with _connect(db_path) as db:
        if not _table_exists(db, "idea_links"):
            print("idea_links does not exist; nothing to archive")
            return 1
        if _table_exists(db, archive_name):
            print(f"{archive_name} already exists; refusing to overwrite")
            return 1
        before = _count(db, "idea_links")
        plan = f'ALTER TABLE idea_links RENAME TO "{archive_name}"'
        print(f"idea_links rows: {before}")
        print(f"plan: {plan}")
        if not apply:
            print("DRY RUN — nothing changed (pass --apply to execute)")
            return 0
        receipt_path = _reserve_receipt(receipt_dir, "archive")
        db.execute(plan)
        db.commit()
        after_exists = _table_exists(db, "idea_links")
        archived = _count(db, archive_name)
    receipt = {
        "agent": "archive_idea_links.py",
        "action": "archive",
        "db": str(db_path),
        "before": {"idea_links_rows": before},
        "after": {
            "archive_table": archive_name,
            "archive_rows": archived,
            "idea_links_exists": after_exists,
        },
        "timestamp": _utc_now_iso(),
        "rollback": f'ALTER TABLE "{archive_name}" RENAME TO idea_links (drop the empty recreated idea_links first if schema-ensure ran)',
    }
    path = _finalize_receipt(receipt_path, receipt)
    print(f"archived {archived} rows -> {archive_name}; receipt: {path}")
    return 0


def phase_drop(
    db_path: Path,
    *,
    apply: bool,
    backup_dir: Path,
    vacuum: bool,
    receipt_dir: Path,
    offhost_copy: str,
    archive_table: str = "",
) -> int:
    with _connect(db_path) as db:
        # LIKE underscores are single-char wildcards; validate every returned
        # name against the exact archive format so an unrelated table can
        # never be selected for backup+DROP.
        archives = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " AND name LIKE 'idea_links_archive_%' ORDER BY name"
            ).fetchall()
            if _ARCHIVE_NAME_RE.fullmatch(row[0])
        ]
        if not archives:
            print("no idea_links_archive_* table found; run phase archive first")
            return 1
        if archive_table:
            if archive_table not in archives:
                print(f"--archive-table {archive_table} not found; discovered: {archives}")
                return 1
            archive_name = archive_table
        elif len(archives) > 1:
            # Re-running phase archive after schema-ensure recreates an empty
            # idea_links produces a newer, possibly empty archive; silently
            # dropping archives[-1] would leave the real rows behind unnoticed.
            print("multiple archive tables found; pass --archive-table to choose one:")
            for name in archives:
                print(f"  {name}: {_count(db, name)} rows")
            return 1
        else:
            archive_name = archives[-1]
        rows = _count(db, archive_name)
        backup_path = backup_dir / f"{archive_name}.db"
        print(f"archive table: {archive_name} ({rows} rows)")
        print(f"plan: backup -> {backup_path}; verify parity; DROP TABLE {archive_name}")
        if vacuum:
            print("plan: VACUUM after drop")
        # refusal checks run before the dry-run return so a clean dry run
        # implies --apply will not refuse for the same state
        if backup_path.exists():
            print(f"{backup_path} already exists; refusing to overwrite")
            return 1
        if not offhost_copy:
            print(
                "no --offhost-copy attestation; refusing to DROP"
                " (packet guardrail: off-host backup must exist first)"
            )
            return 1
        if not apply:
            print("DRY RUN — nothing changed (pass --apply to execute)")
            return 0
        receipt_path = _reserve_receipt(receipt_dir, "drop")
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Preserve the declared schema in the backup: CREATE TABLE AS SELECT
        # keeps rows only (no PK / NOT NULL / declared types), so a rollback
        # from that copy would drop the original invariants. Recreate from
        # the source DDL, then copy rows; index DDLs ride in the receipt.
        table_ddl = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (archive_name,),
        ).fetchone()[0]
        index_ddls = [
            row[0]
            for row in db.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index'"
                " AND tbl_name = ? AND sql IS NOT NULL",
                (archive_name,),
            ).fetchall()
        ]
        backup_table_ddl = re.sub(
            r"^\s*CREATE\s+TABLE\s+(\"[^\"]+\"|\S+)",
            f'CREATE TABLE backup."{archive_name}"',
            table_ddl,
            count=1,
            flags=re.IGNORECASE,
        )
        db.execute("ATTACH DATABASE ? AS backup", (str(backup_path),))
        try:
            db.execute(backup_table_ddl)
            db.execute(f'INSERT INTO backup."{archive_name}" SELECT * FROM "{archive_name}"')
            db.commit()
            backed_up = int(
                db.execute(f'SELECT COUNT(*) FROM backup."{archive_name}"').fetchone()[0]
            )
        except sqlite3.Error as e:
            # A partial backup file must not block the retry that ATTACH's
            # blanket exists() refusal would otherwise hit: this invocation
            # created the file (exists() refused above if it predated us),
            # so detach and remove it, finalize a failure receipt, and keep
            # the archive table untouched.
            db.rollback()
            try:
                db.execute("DETACH DATABASE backup")
            except sqlite3.Error:
                pass
            backup_path.unlink(missing_ok=True)
            _finalize_receipt(
                receipt_path,
                {
                    "agent": "archive_idea_links.py",
                    "action": "drop",
                    "status": "failed_before_drop",
                    "error": f"{type(e).__name__}: {e}",
                    "db": str(db_path),
                    "archive_table": archive_name,
                    "partial_backup_removed": True,
                    "timestamp": _utc_now_iso(),
                },
            )
            print(f"backup construction FAILED ({e}); partial backup removed; archive table NOT dropped")
            return 1
        db.execute("DETACH DATABASE backup")
        if backed_up != rows:
            # A parity-failed backup is unusable evidence: remove it so the
            # identical retry is not refused, and finalize the receipt.
            backup_path.unlink(missing_ok=True)
            _finalize_receipt(
                receipt_path,
                {
                    "agent": "archive_idea_links.py",
                    "action": "drop",
                    "status": "failed_before_drop",
                    "error": f"backup parity mismatch ({backed_up} != {rows})",
                    "db": str(db_path),
                    "archive_table": archive_name,
                    "partial_backup_removed": True,
                    "timestamp": _utc_now_iso(),
                },
            )
            print(f"backup parity FAILED ({backed_up} != {rows}); backup removed; archive table NOT dropped")
            return 1
        # Hash the verified backup BEFORE the destructive commit so the only
        # post-drop step left is writing the already-assembled receipt.
        backup_sha = _sha256(backup_path)
        db.execute(f'DROP TABLE "{archive_name}"')
        db.commit()
        vacuum_error: str | None = None
        if vacuum:
            # A VACUUM failure must not bypass the receipt: the DROP is
            # already committed, so record the failure and continue to the
            # backup hash + receipt — otherwise the destructive op is left
            # without its audit record and a retry refuses on the existing
            # backup file.
            try:
                db.execute("VACUUM")
            except sqlite3.Error as e:
                vacuum_error = f"{type(e).__name__}: {e}"
                print(f"VACUUM failed (drop already committed; receipt still written): {vacuum_error}")
    receipt = {
        "agent": "archive_idea_links.py",
        "action": "drop",
        "db": str(db_path),
        "before": {"archive_table": archive_name, "archive_rows": rows},
        "after": {
            "backup_path": str(backup_path),
            "backup_rows": backed_up,
            "dropped": True,
            "vacuumed": vacuum and vacuum_error is None,
            "vacuum_error": vacuum_error,
        },
        "offhost_copy_attestation": offhost_copy,
        "sha256s": {"backup": backup_sha},
        "schema": {"table_ddl": table_ddl, "index_ddls": index_ddls},
        "timestamp": _utc_now_iso(),
        "rollback": (
            f'ATTACH "{backup_path}" AS backup; recreate via schema.table_ddl; '
            f'INSERT INTO "{archive_name}" SELECT * FROM backup."{archive_name}"; '
            "re-apply schema.index_ddls"
        ),
    }
    try:
        path = _finalize_receipt(receipt_path, receipt)
    except OSError as e:
        # The drop is committed and the backup is verified; the receipt is the
        # only thing missing. Print its full content so the operator can write
        # it to the reserved path by hand instead of losing the audit record.
        print(json.dumps(receipt, indent=2, sort_keys=True))
        print(
            f"RECEIPT FINALIZATION FAILED after committed drop ({e}); "
            f"write the JSON above to {receipt_path} manually"
        )
        return 1
    print(f"dropped {archive_name}; backup sha256={backup_sha}; receipt: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--phase", choices=("archive", "drop"), default="archive")
    parser.add_argument(
        "--apply", action="store_true", help="execute the plan (default: dry run)"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / ".dharma" / "backups",
        help="where phase drop writes the standalone backup db",
    )
    parser.add_argument(
        "--vacuum", action="store_true", help="VACUUM after drop (rewrites whole db)"
    )
    parser.add_argument(
        "--offhost-copy",
        default="",
        help=(
            "attestation of where an off-host copy of the db/backup lives"
            " (e.g. rsync destination); required for phase drop"
        ),
    )
    parser.add_argument(
        "--archive-table",
        default="",
        help=(
            "exact idea_links_archive_YYYYMMDD table for phase drop;"
            " required when more than one archive table exists"
        ),
    )
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"db not found: {args.db}")
        return 1
    if args.phase == "archive":
        return phase_archive(args.db, apply=args.apply, receipt_dir=args.receipt_dir)
    return phase_drop(
        args.db,
        apply=args.apply,
        backup_dir=args.backup_dir,
        vacuum=args.vacuum,
        receipt_dir=args.receipt_dir,
        offhost_copy=args.offhost_copy,
        archive_table=args.archive_table,
    )


if __name__ == "__main__":
    sys.exit(main())
