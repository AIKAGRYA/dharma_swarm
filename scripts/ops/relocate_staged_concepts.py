#!/usr/bin/env python3
"""OP-4: move staged/auto_promoted atoms out of the trusted wiki projection.

Companion migration to the PR-06 staging-boundary fix (audit §5.5 / WS-D.3):
atoms whose provenance.review_status is `staged` or `auto_promoted` were
historically written straight into ~/.dharma/knowledge/wiki/concepts/ — the
trusted projection. This script relocates them into the pending root
(~/.dharma/knowledge/wiki/pending/) where the fixed promote pipeline now
routes them.

Safety properties:
    - DRY-RUN BY DEFAULT: prints the plan as JSON, moves nothing. Pass
      --apply to execute.
    - Files are MOVED, never deleted; collisions in the pending root abort
      that file (fail closed) and are reported.
    - Legacy pages without chetana provenance are never touched.
    - On --apply, a JSON receipt (before/after paths + sha256s + rollback
      instructions) is written under the receipt dir.

Usage:
    python3 scripts/ops/relocate_staged_concepts.py                # dry-run
    python3 scripts/ops/relocate_staged_concepts.py --apply        # execute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

RELOCATABLE_STATUSES = {"staged", "auto_promoted"}


def _utc_now() -> str:
    # date -u per the ops receipt convention.
    return subprocess.run(
        ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True, check=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _review_status(path: Path) -> str | None:
    """Extract provenance.review_status from an atom's frontmatter, or None."""
    try:
        import yaml
    except ImportError:
        print("error: pyyaml required", file=sys.stderr)
        raise
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    prov = fm.get("provenance")
    if not isinstance(prov, dict):
        return None
    status = prov.get("review_status")
    return status if isinstance(status, str) else None


def plan_moves(concepts_root: Path, pending_root: Path) -> tuple[list[dict], list[dict]]:
    moves: list[dict] = []
    skipped: list[dict] = []
    if not concepts_root.is_dir():
        return moves, skipped
    for path in sorted(concepts_root.glob("*.md")):
        status = _review_status(path)
        if status not in RELOCATABLE_STATUSES:
            continue
        dest = pending_root / path.name
        if dest.exists():
            skipped.append(
                {
                    "path": str(path),
                    "review_status": status,
                    "reason": f"collision: {dest} already exists (fail closed, not moved)",
                }
            )
            continue
        moves.append(
            {
                "before": str(path),
                "after": str(dest),
                "review_status": status,
                "sha256": _sha256(path),
            }
        )
    return moves, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--concepts-root",
        type=Path,
        default=Path.home() / ".dharma" / "knowledge" / "wiki" / "concepts",
    )
    parser.add_argument(
        "--pending-root",
        type=Path,
        default=Path.home() / ".dharma" / "knowledge" / "wiki" / "pending",
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=Path.home() / ".dharma" / "witness" / "chetana",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="execute the moves (default: dry-run, print plan only)",
    )
    args = parser.parse_args(argv)

    concepts_root = args.concepts_root.expanduser()
    pending_root = args.pending_root.expanduser()
    moves, skipped = plan_moves(concepts_root, pending_root)

    receipt = {
        "agent": "relocate_staged_concepts",
        "action": "op4_relocate_staged_concepts",
        "timestamp": _utc_now(),
        "dry_run": not args.apply,
        "concepts_root": str(concepts_root),
        "pending_root": str(pending_root),
        "moves": moves,
        "skipped": skipped,
        "rollback": (
            "for each entry in moves: mv <after> <before>; verify sha256 matches"
        ),
    }

    if not args.apply:
        print(json.dumps(receipt, indent=2))
        print(
            f"\nDRY-RUN: {len(moves)} atom(s) would move, {len(skipped)} skipped. "
            "Re-run with --apply to execute.",
            file=sys.stderr,
        )
        return 0

    pending_root.mkdir(parents=True, exist_ok=True)
    applied: list[dict] = []
    for move in moves:
        src, dest = Path(move["before"]), Path(move["after"])
        if dest.exists():
            skipped.append({"path": str(src), "reason": "collision appeared at apply time"})
            continue
        # Revalidate the source against the plan at apply time: an approval
        # (or any other writer) may have replaced it since plan_moves ran, and
        # moving the current bytes on stale plan metadata would relocate a
        # newly approved atom into pending/ while the receipt describes the
        # previous staged file.
        if not src.exists():
            skipped.append({"path": str(src), "reason": "source vanished before apply"})
            continue
        current_status = _review_status(src)
        if current_status not in RELOCATABLE_STATUSES:
            skipped.append(
                {
                    "path": str(src),
                    "reason": (
                        "review_status changed to "
                        f"{current_status!r} after planning (not moved)"
                    ),
                }
            )
            continue
        current_sha = _sha256(src)
        if current_sha != move["sha256"]:
            skipped.append(
                {
                    "path": str(src),
                    "reason": (
                        "content changed after planning "
                        f"(planned sha256 {move['sha256'][:12]}…, "
                        f"current {current_sha[:12]}…; not moved)"
                    ),
                }
            )
            continue
        shutil.move(str(src), str(dest))
        applied.append({**move, "sha256_after": _sha256(dest)})
    receipt["moves"] = applied

    receipt_dir = args.receipt_dir.expanduser()
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"op4_relocate_{receipt['timestamp'].replace(':', '-')}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    print(f"\nAPPLIED: {len(applied)} moved, {len(skipped)} skipped. Receipt: {receipt_path}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
