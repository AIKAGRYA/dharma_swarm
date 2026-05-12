#!/usr/bin/env python3
"""Consume stigmergy review-channel marks → human/agent-readable action queue.

Closes the recognition→action edge that spine §3 names as load-bearing:
"If witness writes but actors do not read, the repo becomes audited but
not self-correcting." Heartbeat phase 4b emits review-channel marks;
this script reads them, dedupes by content slug, scores them by
salience × recency × repeat-count, and regenerates a snapshot at
``~/.dharma/control/review_queue.md``.

Idempotent. Read-only on stigmergy. Writes only the queue file and
optional witness JSONL. Does not delete or mutate marks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_MARKS_PATH = Path.home() / ".dharma/stigmergy/marks.jsonl"
DEFAULT_QUEUE_PATH = Path.home() / ".dharma/control/review_queue.md"
DEFAULT_WITNESS_PATH = Path.home() / ".dharma/witness/review_consumer.jsonl"
DEFAULT_ESCALATION_LOG = Path.home() / ".dharma/control/review_escalations.jsonl"
DEFAULT_LOOKBACK_HOURS = 72
DEFAULT_MAX_ENTRIES = 25
DEFAULT_PROMOTE_SALIENCE = 0.85
DEFAULT_ESCALATION_DEDUP_HOURS = 24


@dataclass
class ReviewItem:
    slug: str
    content: str
    agent: str
    first_seen: datetime
    last_seen: datetime
    occurrences: int = 1
    max_salience: float = 0.0
    sources: list[str] = field(default_factory=list)

    @property
    def age_hours(self) -> float:
        return (datetime.now(timezone.utc) - self.first_seen).total_seconds() / 3600.0

    @property
    def score(self) -> float:
        # salience × log(occurrences+1) × age decay (half-life 24h, capped at 0.25)
        import math
        decay = max(0.25, 0.5 ** (self.age_hours / 24.0))
        return self.max_salience * math.log(self.occurrences + 1, 2) * decay


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _content_slug(content: str) -> str:
    """Stable identifier for dedup. Strips run-id-like suffixes."""
    text = (content or "").strip().lower()
    # Drop anything that looks like a per-run timestamp / hash trailer.
    text = re.sub(r"\b\d{8}t\d{6}z\b", "", text)
    text = re.sub(r"source:\s*[^\s]+", "source:", text)
    text = re.sub(r"\bsalience=[\d.]+\b", "", text)
    text = re.sub(r"\bkeywords=\[[^\]]*\]", "", text)
    cleaned = _SLUG_RE.sub("-", text).strip("-")
    if not cleaned:
        cleaned = hashlib.sha1((content or "").encode()).hexdigest()[:12]
    return cleaned[:80]


def _iter_marks(marks_path: Path) -> Iterable[dict]:
    if not marks_path.exists():
        return
    with marks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def collect_review_items(
    marks_path: Path,
    *,
    lookback_hours: int,
    channel: str = "review",
    now: datetime | None = None,
) -> list[ReviewItem]:
    """Walk marks.jsonl, group review-channel marks by content slug."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=lookback_hours)
    by_slug: dict[str, ReviewItem] = {}
    for mark in _iter_marks(marks_path):
        if mark.get("channel") != channel:
            continue
        ts = _parse_ts(mark.get("ts") or mark.get("timestamp"))
        if ts is None:
            continue
        # marks.jsonl may carry naive datetimes; coerce to UTC.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        content = str(mark.get("content") or mark.get("observation") or "").strip()
        if not content:
            continue
        slug = _content_slug(content)
        salience = float(mark.get("salience") or 0.0)
        agent = str(mark.get("agent") or "unknown")
        source = str(mark.get("source_run") or mark.get("file_path") or "")
        existing = by_slug.get(slug)
        if existing is None:
            by_slug[slug] = ReviewItem(
                slug=slug,
                content=content,
                agent=agent,
                first_seen=ts,
                last_seen=ts,
                occurrences=1,
                max_salience=salience,
                sources=[source] if source else [],
            )
            continue
        existing.occurrences += 1
        existing.max_salience = max(existing.max_salience, salience)
        existing.last_seen = max(existing.last_seen, ts)
        existing.first_seen = min(existing.first_seen, ts)
        if source and source not in existing.sources:
            existing.sources.append(source)
    return list(by_slug.values())


def render_queue(
    items: list[ReviewItem],
    *,
    max_entries: int,
    promote_salience: float,
    lookback_hours: int,
    now: datetime,
) -> tuple[str, list[ReviewItem]]:
    """Render the markdown queue + return the promotion-eligible items."""
    items_sorted = sorted(items, key=lambda it: it.score, reverse=True)
    promoted = [
        it
        for it in items_sorted
        if it.max_salience >= promote_salience and it.occurrences >= 2
    ]
    lines = [
        "# Stigmergy Review Queue",
        "",
        f"_Generated: {now.isoformat(timespec='seconds')}_",
        f"_Source: ~/.dharma/stigmergy/marks.jsonl (channel=review, lookback={lookback_hours}h)_",
        f"_Total unique items: {len(items_sorted)}; promotion-eligible: {len(promoted)}_",
        "",
        "Each item is a snapshot of a recognition→action signal that the system",
        "raised but has not yet metabolised. Tick `[x]` to acknowledge; the queue",
        "regenerates each heartbeat pulse from the latest stigmergy marks.",
        "",
        "## Promotion-eligible (salience ≥ "
        f"{promote_salience:.2f}, occurrences ≥ 2)",
        "",
    ]
    if promoted:
        for item in promoted[:max_entries]:
            lines.append(_render_item(item))
    else:
        lines.append("_(none — recognition layer is producing only low-salience "
                     "or singleton marks; check murder-flight credit budget.)_")
    lines.extend([
        "",
        "## All review marks (top by score)",
        "",
    ])
    if items_sorted:
        for item in items_sorted[:max_entries]:
            lines.append(_render_item(item))
    else:
        lines.append("_(no review-channel marks in the lookback window.)_")
    lines.append("")
    return "\n".join(lines), promoted


def _render_item(item: ReviewItem) -> str:
    sources = (
        f" — sources: {', '.join(item.sources[:3])}" if item.sources else ""
    )
    return (
        f"- [ ] **{item.slug}** "
        f"(agent={item.agent}, sal={item.max_salience:.2f}, "
        f"x{item.occurrences}, age={item.age_hours:.1f}h, "
        f"score={item.score:.2f})\n"
        f"      {item.content[:240]}{sources}"
    )


def append_witness(
    witness_path: Path,
    *,
    queue_path: Path,
    item_count: int,
    promoted_count: int,
    escalated_count: int,
    lookback_hours: int,
    now: datetime,
) -> None:
    witness_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": now.isoformat(),
        "source": "consume_review_marks",
        "queue_path": str(queue_path),
        "item_count": item_count,
        "promoted_count": promoted_count,
        "escalated_count": escalated_count,
        "lookback_hours": lookback_hours,
    }
    with witness_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _load_recent_escalations(
    log_path: Path, *, dedup_hours: int, now: datetime
) -> set[str]:
    """Slugs escalated within the dedup window — skip re-escalation."""
    if not log_path.exists():
        return set()
    cutoff = now - timedelta(hours=dedup_hours)
    out: set[str] = set()
    with log_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_ts(row.get("timestamp_utc"))
            slug = row.get("slug")
            if ts is None or not slug:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff and row.get("status") == "escalated":
                out.add(slug)
    return out


def _record_escalation(
    log_path: Path,
    *,
    slug: str,
    item: ReviewItem,
    status: str,
    detail: str,
    now: datetime,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": now.isoformat(),
        "slug": slug,
        "status": status,
        "detail": detail,
        "agent": item.agent,
        "salience": item.max_salience,
        "occurrences": item.occurrences,
        "score": round(item.score, 4),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def escalate_to_taskboard(
    items: list[ReviewItem],
    *,
    escalation_log: Path,
    dedup_hours: int,
    max_per_run: int,
    dry_run: bool,
    now: datetime,
) -> tuple[int, list[str]]:
    """For each promotion-eligible item not already escalated within
    `dedup_hours`, shell out to `dgc task create`. Returns (count, slugs)."""
    if not items:
        return 0, []
    binary = shutil.which("dgc")
    if not binary and not dry_run:
        # No dgc binary — record skipped escalations so the heartbeat can see why.
        for item in items[:max_per_run]:
            _record_escalation(
                escalation_log,
                slug=item.slug,
                item=item,
                status="skipped",
                detail="dgc binary not on PATH",
                now=now,
            )
        return 0, []
    recent = _load_recent_escalations(
        escalation_log, dedup_hours=dedup_hours, now=now
    )
    escalated: list[str] = []
    for item in items[:max_per_run]:
        if item.slug in recent:
            _record_escalation(
                escalation_log,
                slug=item.slug,
                item=item,
                status="deduped",
                detail=f"already escalated within {dedup_hours}h",
                now=now,
            )
            continue
        title = f"review:{item.slug}"[:120]
        description = (
            f"Auto-escalated from stigmergy review channel. "
            f"agent={item.agent} sal={item.max_salience:.2f} "
            f"x{item.occurrences} score={item.score:.2f}\n\n"
            f"{item.content[:800]}"
        )
        if dry_run:
            _record_escalation(
                escalation_log,
                slug=item.slug,
                item=item,
                status="dry_run",
                detail=title,
                now=now,
            )
            escalated.append(item.slug)
            continue
        try:
            result = subprocess.run(
                [binary or "dgc", "task", "create", title, description],
                capture_output=True,
                text=True,
                timeout=20,
            )
            ok = result.returncode == 0
            detail = (result.stdout or "").strip()[:240] if ok else (
                (result.stderr or "").strip()[:240] or f"exit={result.returncode}"
            )
            _record_escalation(
                escalation_log,
                slug=item.slug,
                item=item,
                status="escalated" if ok else "failed",
                detail=detail,
                now=now,
            )
            if ok:
                escalated.append(item.slug)
        except (subprocess.TimeoutExpired, OSError) as exc:
            _record_escalation(
                escalation_log,
                slug=item.slug,
                item=item,
                status="failed",
                detail=f"{type(exc).__name__}: {exc}",
                now=now,
            )
    return len(escalated), escalated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marks-path", type=Path, default=DEFAULT_MARKS_PATH)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--witness-path", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--lookback-hours", type=int, default=DEFAULT_LOOKBACK_HOURS)
    parser.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    parser.add_argument(
        "--promote-salience",
        type=float,
        default=DEFAULT_PROMOTE_SALIENCE,
        help="Items with max_salience ≥ this AND occurrences ≥ 2 are listed "
        "in the promotion-eligible section (candidates for TaskBoard escalation).",
    )
    parser.add_argument("--channel", default="review")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--escalate",
        action="store_true",
        help="For promotion-eligible items, shell out to `dgc task create` "
        "(idempotent within --escalation-dedup-hours).",
    )
    parser.add_argument(
        "--escalation-log",
        type=Path,
        default=DEFAULT_ESCALATION_LOG,
    )
    parser.add_argument(
        "--escalation-dedup-hours",
        type=int,
        default=DEFAULT_ESCALATION_DEDUP_HOURS,
    )
    parser.add_argument(
        "--escalation-max-per-run",
        type=int,
        default=3,
        help="Hard cap on tasks emitted per run, regardless of queue size.",
    )
    parser.add_argument(
        "--escalation-dry-run",
        action="store_true",
        help="Log what would be escalated without invoking dgc.",
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    items = collect_review_items(
        args.marks_path,
        lookback_hours=args.lookback_hours,
        channel=args.channel,
        now=now,
    )
    queue_md, promoted = render_queue(
        items,
        max_entries=args.max_entries,
        promote_salience=args.promote_salience,
        lookback_hours=args.lookback_hours,
        now=now,
    )
    args.queue_path.parent.mkdir(parents=True, exist_ok=True)
    args.queue_path.write_text(queue_md, encoding="utf-8")

    escalated_count = 0
    escalated_slugs: list[str] = []
    if args.escalate:
        escalated_count, escalated_slugs = escalate_to_taskboard(
            promoted,
            escalation_log=args.escalation_log,
            dedup_hours=args.escalation_dedup_hours,
            max_per_run=args.escalation_max_per_run,
            dry_run=args.escalation_dry_run,
            now=now,
        )

    append_witness(
        args.witness_path,
        queue_path=args.queue_path,
        item_count=len(items),
        promoted_count=len(promoted),
        escalated_count=escalated_count,
        lookback_hours=args.lookback_hours,
        now=now,
    )
    if not args.quiet:
        suffix = ""
        if args.escalate:
            mode = " [dry-run]" if args.escalation_dry_run else ""
            suffix = f" — escalated {escalated_count}{mode}: {','.join(escalated_slugs) or '(none)'}"
        print(
            f"[consume_review_marks] {len(items)} unique review items "
            f"({len(promoted)} promotion-eligible) written to {args.queue_path}"
            f"{suffix}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
