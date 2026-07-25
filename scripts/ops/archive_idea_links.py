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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path.home() / ".dharma" / "db" / "memory_plane.db"
DEFAULT_RECEIPT_DIR = Path.home() / ".dharma" / "witness" / "audit_impl_20260725"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    path = receipt_dir / f"archive_idea_links_{receipt['action']}_{_utc_stamp()}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def phase_archive(db_path: Path, *, apply: bool, receipt_dir: Path) -> int:
    archive_name = f"idea_links_archive_{_utc_stamp()}"
    with sqlite3.connect(str(db_path)) as db:
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
    path = _write_receipt(receipt_dir, receipt)
    print(f"archived {archived} rows -> {archive_name}; receipt: {path}")
    return 0


def phase_drop(
    db_path: Path, *, apply: bool, backup_dir: Path, vacuum: bool, receipt_dir: Path
) -> int:
    with sqlite3.connect(str(db_path)) as db:
        archives = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " AND name LIKE 'idea_links_archive_%' ORDER BY name"
            ).fetchall()
        ]
        if not archives:
            print("no idea_links_archive_* table found; run phase archive first")
            return 1
        archive_name = archives[-1]
        rows = _count(db, archive_name)
        backup_path = backup_dir / f"{archive_name}.db"
        print(f"archive table: {archive_name} ({rows} rows)")
        print(f"plan: backup -> {backup_path}; verify parity; DROP TABLE {archive_name}")
        if vacuum:
            print("plan: VACUUM after drop")
        if not apply:
            print("DRY RUN — nothing changed (pass --apply to execute)")
            return 0
        if backup_path.exists():
            print(f"{backup_path} already exists; refusing to overwrite")
            return 1
        backup_dir.mkdir(parents=True, exist_ok=True)
        db.execute("ATTACH DATABASE ? AS backup", (str(backup_path),))
        db.execute(f'CREATE TABLE backup."{archive_name}" AS SELECT * FROM "{archive_name}"')
        db.commit()
        backed_up = int(
            db.execute(f'SELECT COUNT(*) FROM backup."{archive_name}"').fetchone()[0]
        )
        db.execute("DETACH DATABASE backup")
        if backed_up != rows:
            print(f"backup parity FAILED ({backed_up} != {rows}); archive table NOT dropped")
            return 1
        db.execute(f'DROP TABLE "{archive_name}"')
        db.commit()
        if vacuum:
            db.execute("VACUUM")
    backup_sha = _sha256(backup_path)
    receipt = {
        "agent": "archive_idea_links.py",
        "action": "drop",
        "db": str(db_path),
        "before": {"archive_table": archive_name, "archive_rows": rows},
        "after": {
            "backup_path": str(backup_path),
            "backup_rows": backed_up,
            "dropped": True,
            "vacuumed": vacuum,
        },
        "sha256s": {"backup": backup_sha},
        "timestamp": _utc_now_iso(),
        "rollback": f'ATTACH "{backup_path}" AS backup; CREATE TABLE "{archive_name}" AS SELECT * FROM backup."{archive_name}"',
    }
    path = _write_receipt(receipt_dir, receipt)
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
    )


if __name__ == "__main__":
    sys.exit(main())
