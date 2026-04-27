"""chetana.decay — stale_after scanner + quarantine.

This is the active-inference / Friston layer. Every atom carries a stale_after
date. When today > stale_after, the atom is decayed: it gets surfaced for
re-verification (if `--quarantine` not passed) or moved to quarantine/ (if it is).

The decay job is the single mechanism that turns the wiki from an accretive
archive into a living system. It runs daily (recommended via launchd/cron at
04:30 local) and reports the queue back to the operator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .provenance import FrontmatterSchema, parse_frontmatter
from .staging import (
    QUARANTINE_ROOT,
    TRUSTED_DEFAULT,
    WIKI_ROOT,
    list_trusted,
    quarantine_atom,
)

logger = logging.getLogger(__name__)


@dataclass
class DecayedAtom:
    path: Path
    title: str
    stale_after: str
    days_overdue: int
    confidence: float


@dataclass
class DecayReport:
    scanned: int = 0
    stale: list[DecayedAtom] = field(default_factory=list)
    quarantined: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def stale_count(self) -> int:
        return len(self.stale)


def scan_decay(
    *,
    today: date | None = None,
    roots: list[Path] | None = None,
    quarantine: bool = False,
    grace_days: int = 0,
) -> DecayReport:
    """Scan trusted atoms for stale_after expiry.

    By default, scans:
        ~/.dharma/knowledge/wiki/concepts/  (chetana-promoted atoms)

    Pass `roots=[...]` to scan additional directories (e.g., the cabinet
    or foundations) — provided they carry chetana frontmatter.

    `grace_days` lets you find atoms that will go stale soon
    (positive) or are already past stale (zero / negative).
    """
    today = today or date.today()
    roots = roots or [TRUSTED_DEFAULT]

    report = DecayReport()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            report.scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
                schema, _body = parse_frontmatter(text, lenient=True, source_path=str(path))
            except Exception as e:
                report.skipped.append((path, f"parse error: {e}"))
                continue

            if schema is None:
                report.skipped.append((path, "no chetana frontmatter"))
                continue

            try:
                stale_after = date.fromisoformat(schema.stale_after)
            except ValueError as e:
                report.skipped.append((path, f"bad stale_after: {e}"))
                continue

            days_overdue = (today - stale_after).days - grace_days
            if days_overdue >= 0:
                decayed = DecayedAtom(
                    path=path,
                    title=schema.title,
                    stale_after=schema.stale_after,
                    days_overdue=days_overdue,
                    confidence=schema.confidence,
                )
                report.stale.append(decayed)
                if quarantine:
                    try:
                        new_path = quarantine_atom(path)
                        report.quarantined.append(new_path)
                    except Exception as e:
                        report.skipped.append((path, f"quarantine failed: {e}"))

    return report


def decay_summary(report: DecayReport) -> str:
    """Render a one-screen markdown summary of the decay scan."""
    lines = [
        "# Decay scan",
        "",
        f"- Scanned: {report.scanned} files",
        f"- Stale: {report.stale_count}",
        f"- Quarantined: {len(report.quarantined)}",
        f"- Skipped: {len(report.skipped)}",
        "",
    ]
    if report.stale:
        lines.append("## Stale atoms (most overdue first)")
        for atom in sorted(report.stale, key=lambda a: -a.days_overdue):
            lines.append(
                f"- `{atom.path}` — {atom.title!r} (stale_after={atom.stale_after}, "
                f"overdue {atom.days_overdue}d, confidence={atom.confidence:.2f})"
            )
        lines.append("")
    if report.skipped:
        lines.append("## Skipped (top 20)")
        for path, why in report.skipped[:20]:
            lines.append(f"- `{path}` — {why}")
    return "\n".join(lines)
