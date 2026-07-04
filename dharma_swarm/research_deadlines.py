"""Operator-owned research deadlines — the post-COLM mechanism.

History: the COLM 2026 dates (2026-03-26 abstract / 2026-03-31 paper) were
hardcoded as constants in ``meta_daemon`` and ``master_prompt_engineer``.
When the deadline died, the stopped clock kept broadcasting a 0-day countdown
— and meta_daemon's "crunch" phase — into every agent context for three
months. The 2026-06-10 handoffs claimed this was fixed; the fix never landed
until 2026-07-03. Deadlines are operator DATA, never code constants.

The operator owns ``~/.dharma/research_deadlines.json``::

    {"deadlines": [
        {"venue": "NeurIPS 2027", "abstract": "2027-05-11", "paper": "2027-05-18"}
    ]}

(A bare list, or a single object, is also accepted.) Absent file, malformed
file, or no entry with a future date all mean **no active deadline** — callers
must then omit their countdown line entirely, never render 0 days or "crunch".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

from dharma_swarm.daemon_config import dharma_state_dir

DEADLINES_FILENAME = "research_deadlines.json"


def deadlines_path() -> Path:
    return dharma_state_dir() / DEADLINES_FILENAME


@dataclass(frozen=True)
class ResearchDeadline:
    """One venue deadline. Either date may be absent."""

    venue: str
    abstract: Optional[date] = None
    paper: Optional[date] = None

    def days_to_abstract(self, today: Optional[date] = None) -> Optional[int]:
        if self.abstract is None:
            return None
        return (self.abstract - (today or date.today())).days

    def days_to_paper(self, today: Optional[date] = None) -> Optional[int]:
        if self.paper is None:
            return None
        return (self.paper - (today or date.today())).days

    def latest_date(self) -> Optional[date]:
        candidates = [d for d in (self.abstract, self.paper) if d is not None]
        return max(candidates) if candidates else None


def _parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _parse_entries(payload: Any) -> list[ResearchDeadline]:
    if isinstance(payload, dict):
        raw = payload.get("deadlines", payload)
        entries = raw if isinstance(raw, list) else [raw]
    elif isinstance(payload, list):
        entries = payload
    else:
        return []
    out: list[ResearchDeadline] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        dl = ResearchDeadline(
            venue=str(e.get("venue", "research deadline")),
            abstract=_parse_date(e.get("abstract")),
            paper=_parse_date(e.get("paper")),
        )
        if dl.latest_date() is not None:
            out.append(dl)
    return out


def active_deadline(
    today: Optional[date] = None, path: Optional[Path] = None
) -> Optional[ResearchDeadline]:
    """The nearest deadline whose latest date is still in the future, or None.

    None means: render NO countdown. A past deadline is never returned — that
    is the stopped-clock bug this module exists to prevent.
    """
    today = today or date.today()
    p = path or deadlines_path()
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    live = [d for d in _parse_entries(payload) if d.latest_date() >= today]
    if not live:
        return None
    return min(live, key=lambda d: d.latest_date())


def deadline_line(
    today: Optional[date] = None, path: Optional[Path] = None
) -> str:
    """One human line for prompts/CLIs. Honest when nothing is on file."""
    dl = active_deadline(today=today, path=path)
    if dl is None:
        return f"no active research deadline on file ({deadlines_path()})"
    parts = []
    da = dl.days_to_abstract(today)
    dp = dl.days_to_paper(today)
    if da is not None and da >= 0:
        parts.append(f"abstract in {da}d")
    if dp is not None and dp >= 0:
        parts.append(f"paper in {dp}d")
    return f"{dl.venue} — {', '.join(parts) if parts else 'dates passed'}"


__all__ = [
    "DEADLINES_FILENAME",
    "ResearchDeadline",
    "active_deadline",
    "deadline_line",
    "deadlines_path",
]
