#!/usr/bin/env python3
"""Tombstone the pre-Honest-Spine evolution archive epoch.

Audit findings (2026-06-10, verified): ~11,164 records; 98.96% empty diff;
0% parent lineage; 0 commit hashes; status="applied" written without any
application. These records are activity narration, not evolution evidence.

This migration marks every entry timestamped before the cutoff with
`untrusted_epoch: true`. Selection (`EvolutionArchive.get_best`) already
excludes tombstoned entries; nothing is deleted, so the historical record
stays inspectable and the operation is reversible (backup + flag flip).

Safety:
  - dry-run by default; --apply required to mutate
  - full backup written next to the archive before any rewrite
  - exclusive flock held for the whole transform; atomic rename at the end

Usage:
  python3 scripts/runtime/tombstone_archive_epoch.py            # dry run
  python3 scripts/runtime/tombstone_archive_epoch.py --apply
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ARCHIVE = Path.home() / ".dharma" / "evolution" / "archive.jsonl"
DEFAULT_CUTOFF = "2026-06-10T00:00:00"


def migrate(archive_path: Path, cutoff: str, apply: bool) -> dict[str, int]:
    if not archive_path.exists():
        print(f"archive not found: {archive_path}")
        return {"total": 0, "tombstoned": 0, "already": 0, "kept": 0, "unparseable": 0}

    stats = {"total": 0, "tombstoned": 0, "already": 0, "kept": 0, "unparseable": 0}
    out_lines: list[str] = []

    with open(archive_path, "r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                stats["total"] += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    stats["unparseable"] += 1
                    out_lines.append(line)
                    continue
                if rec.get("untrusted_epoch"):
                    stats["already"] += 1
                    out_lines.append(line)
                    continue
                ts = str(rec.get("timestamp", ""))
                if ts and ts < cutoff:
                    rec["untrusted_epoch"] = True
                    stats["tombstoned"] += 1
                    out_lines.append(json.dumps(rec, default=str))
                else:
                    stats["kept"] += 1
                    out_lines.append(line)

            if apply and stats["tombstoned"]:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = archive_path.with_suffix(f".pre_tombstone_{stamp}.jsonl")
                shutil.copy2(archive_path, backup)
                tmp = archive_path.with_suffix(".tombstone_tmp")
                tmp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
                os.replace(tmp, archive_path)
                print(f"backup: {backup}")
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF,
                        help="ISO timestamp; entries strictly before are tombstoned")
    parser.add_argument("--apply", action="store_true",
                        help="actually rewrite the archive (default: dry run)")
    args = parser.parse_args()

    stats = migrate(args.archive, args.cutoff, args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] {args.archive}")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    if not args.apply and stats["tombstoned"]:
        print("re-run with --apply to write (backup is taken automatically)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
