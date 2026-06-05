#!/usr/bin/env python3
"""consume_review_marks.py — Bulk-promote staging atoms to trusted wiki.

Cron contract: this script runs on a 6-hour cadence to prevent staging
from unbounded growth. Without it, the ingest pipeline adds ~1k atoms/day
while nothing ever graduates to trusted.

Promotion criteria (--auto-promote mode):
  1. type == "atomic" (compound atoms need manual review)
  2. confidence >= 0.5 (frontmatter field)
  3. content-bound external review mark exists under knowledge/review_marks/
  4. File is valid markdown with YAML frontmatter
  5. Not quarantined (already in a separate dir)

Usage:
  # Dry run — show what would promote
  python3 scripts/consume_review_marks.py --dry-run

  # Auto-promote with default thresholds
  python3 scripts/consume_review_marks.py --auto-promote

  # Custom confidence threshold
  python3 scripts/consume_review_marks.py --auto-promote --min-confidence 0.7

  # Report staging health without promoting
  python3 scripts/consume_review_marks.py --report

Directories (relative to DHARMA_HOME, default ~/.dharma):
  knowledge/staging/         → source (atoms awaiting review)
  knowledge/wiki/concepts/   → target (trusted atoms)
  knowledge/quarantine/      → rejected atoms (not touched by this script)

Exit codes:
  0 — success (promoted N atoms or nothing to promote)
  1 — error (filesystem, parse failure, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DHARMA_HOME = Path(os.environ.get("DHARMA_HOME", Path.home() / ".dharma"))
STAGING_DIR = DHARMA_HOME / "knowledge" / "staging"
TRUSTED_DIR = DHARMA_HOME / "knowledge" / "wiki" / "concepts"
QUARANTINE_DIR = DHARMA_HOME / "knowledge" / "quarantine"
REVIEW_MARK_DIR = DHARMA_HOME / "knowledge" / "review_marks"
LOG_PATH = DHARMA_HOME / "logs" / "consume_review_marks.jsonl"

DEFAULT_MIN_CONFIDENCE = 0.5
ALLOWED_TYPES = {"atomic"}
REVIEW_MARK_SCHEMA = "dharma.knowledge_review_mark.v1"
TRUSTED_REVIEWERS = {
    "operator",
}


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class AtomMeta(NamedTuple):
    """Extracted metadata from atom frontmatter."""

    atom_type: str
    confidence: float
    title: str
    concepts: list[str]
    raw_frontmatter: str
    reviewed: bool = False


def parse_frontmatter(text: str) -> AtomMeta | None:
    """Parse YAML-ish frontmatter from a markdown atom.

    Lightweight parser — avoids PyYAML dependency for cron portability.
    Handles simple key: value lines.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None

    raw = match.group(1)
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip().strip("'\"")

    atom_type = fields.get("type", "unknown").lower()
    try:
        confidence = float(fields.get("confidence", "0.0"))
    except (ValueError, TypeError):
        confidence = 0.0

    title = fields.get("title", fields.get("name", "untitled"))
    concepts_raw = fields.get("concepts", "")
    concepts = [c.strip() for c in concepts_raw.split(",") if c.strip()]
    reviewed = fields.get("reviewed", "").lower() in {"1", "true", "yes", "approved"}
    review_status = fields.get("review_status", "").lower()
    reviewed = reviewed or review_status in {"approved", "reviewed"}

    return AtomMeta(
        atom_type=atom_type,
        confidence=confidence,
        title=title,
        concepts=concepts,
        raw_frontmatter=raw,
        reviewed=reviewed,
    )


def review_mark_id(src: Path) -> str:
    """Return the deterministic external review-mark id for a staging atom."""

    rel = src.relative_to(STAGING_DIR).as_posix()
    return hashlib.sha256(rel.encode("utf-8")).hexdigest()


def review_mark_path(src: Path) -> Path:
    """Return the expected external review-mark path for a staging atom."""

    return REVIEW_MARK_DIR / f"{review_mark_id(src)}.json"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_external_review_mark(src: Path) -> bool:
    """Return True only when a separate review-mark receipt approves the atom."""

    try:
        rel = src.relative_to(STAGING_DIR).as_posix()
        mark_path = review_mark_path(src)
    except ValueError:
        return False

    try:
        mark = json.loads(mark_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return False

    if str(mark.get("schema") or "").strip() != REVIEW_MARK_SCHEMA:
        return False
    decision = str(
        mark.get("decision") or mark.get("review_status") or mark.get("status") or ""
    ).strip().lower()
    if decision not in {"approved", "reviewed"}:
        return False
    if str(mark.get("path") or "").strip() != rel:
        return False
    reviewer = str(mark.get("reviewer") or mark.get("reviewed_by") or "").strip()
    if reviewer not in TRUSTED_REVIEWERS:
        return False
    if not str(mark.get("reviewed_at") or mark.get("timestamp") or "").strip():
        return False

    expected_hash = str(mark.get("atom_sha256") or "").strip()
    if not expected_hash or expected_hash != _file_sha256(src):
        return False
    return True


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------


def should_promote(
    meta: AtomMeta,
    min_confidence: float,
    *,
    has_independent_review: bool = False,
) -> tuple[bool, str]:
    """Decide if an atom should be promoted.

    Returns (should_promote, reason).
    """
    if meta.atom_type not in ALLOWED_TYPES:
        return False, f"type={meta.atom_type} not in {ALLOWED_TYPES}"
    if meta.confidence < min_confidence:
        return False, f"confidence={meta.confidence:.2f} < {min_confidence}"
    if not has_independent_review:
        return False, "missing external review mark"
    return True, "meets criteria"


def promote_atom(src: Path, dst_dir: Path, dry_run: bool = False) -> bool:
    """Move an atom from staging to trusted.

    Preserves directory structure relative to staging root.
    """
    rel = src.relative_to(STAGING_DIR)
    dst = dst_dir / rel

    if dst.exists():
        # Dedup: if same filename exists in trusted, append a suffix
        stem = dst.stem
        suffix = dst.suffix
        counter = 1
        while dst.exists():
            dst = dst.parent / f"{stem}_{counter}{suffix}"
            counter += 1

    if dry_run:
        logger.info("  [DRY-RUN] would promote staging atom")
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return True


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def scan_staging(min_confidence: float) -> dict:
    """Scan staging and return statistics."""
    stats = {
        "total": 0,
        "promotable": 0,
        "low_confidence": 0,
        "wrong_type": 0,
        "missing_review": 0,
        "no_frontmatter": 0,
        "errors": 0,
    }

    if not STAGING_DIR.exists():
        return stats

    for path in STAGING_DIR.rglob("*.md"):
        if not path.is_file():
            continue
        stats["total"] += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            if meta is None:
                stats["no_frontmatter"] += 1
                continue
            ok, reason = should_promote(
                meta,
                min_confidence,
                has_independent_review=has_external_review_mark(path),
            )
            if ok:
                stats["promotable"] += 1
            elif "confidence" in reason:
                stats["low_confidence"] += 1
            elif "external review" in reason:
                stats["missing_review"] += 1
            elif "type" in reason:
                stats["wrong_type"] += 1
            else:
                stats["errors"] += 1
        except Exception:
            stats["errors"] += 1

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk-promote staging atoms to trusted wiki."
    )
    parser.add_argument(
        "--auto-promote",
        action="store_true",
        help="Promote all qualifying atoms (type=atomic, confidence>=threshold)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be promoted without moving files",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print staging health report and exit",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help=f"Minimum confidence to auto-promote (default: {DEFAULT_MIN_CONFIDENCE})",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=5000,
        help="Maximum atoms to promote in one batch (default: 5000)",
    )
    args = parser.parse_args()

    if not STAGING_DIR.exists():
        logger.info("Staging directory does not exist: %s", STAGING_DIR)
        return 0

    # Report mode
    if args.report:
        stats = scan_staging(args.min_confidence)
        print(json.dumps(stats, indent=2))
        logger.info(
            "Staging report: %d total, %d promotable, %d low-confidence, "
            "%d wrong-type, %d missing-review, %d no-frontmatter, %d errors",
            stats["total"],
            stats["promotable"],
            stats["low_confidence"],
            stats["wrong_type"],
            stats["missing_review"],
            stats["no_frontmatter"],
            stats["errors"],
        )
        return 0

    if not args.auto_promote and not args.dry_run:
        parser.print_help()
        return 0

    if not args.dry_run:
        TRUSTED_DIR.mkdir(parents=True, exist_ok=True)

    # Process staging
    promoted = 0
    skipped = 0
    errors = 0

    for path in sorted(STAGING_DIR.rglob("*.md")):
        if not path.is_file():
            continue
        if promoted >= args.max_batch:
            logger.info("Batch limit reached (%d). Remaining atoms deferred.", args.max_batch)
            break

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            if meta is None:
                skipped += 1
                continue

            ok, reason = should_promote(
                meta,
                args.min_confidence,
                has_independent_review=has_external_review_mark(path),
            )
            if not ok:
                skipped += 1
                continue

            if promote_atom(path, TRUSTED_DIR, dry_run=args.dry_run):
                promoted += 1
        except Exception as exc:
            logger.warning("Error processing %s: %s", path, exc)
            errors += 1

    # Log result
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "promoted": promoted,
        "skipped": skipped,
        "errors": errors,
        "dry_run": args.dry_run,
        "min_confidence": args.min_confidence,
    }
    logger.info(
        "Done: promoted=%d skipped=%d errors=%d dry_run=%s",
        promoted, skipped, errors, args.dry_run,
    )

    # Persist to log
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
    except Exception as exc:
        logger.debug("Log write failed: %s", exc)

    return 1 if errors > 0 and promoted == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
