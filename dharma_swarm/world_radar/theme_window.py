"""Rolling-window theme persistence over world_radar movements.

world_radar/analysis.py already clusters raw signals into "movements" (a
title-key grouping, not semantic) each cycle, from scratch, with no memory of
prior cycles. This module adds the one thing that was missing (per the
Signal Synthesis Desk DRAFT track, Phase 2): a persistent record of which
movement_ids have been seen before, how many cycles they've recurred across,
and when they were first/last observed -- so a theme that keeps reappearing
is recognizable as recurring rather than being re-discovered from scratch
every run, and so a downstream consumer (e.g. the deep sweep) can cheaply
answer "which of today's movements are actually NEW" instead of re-processing
everything every cycle.

Actually rolling, not monotonically accumulating: entries not seen again
within MAX_WINDOW_AGE_DAYS are pruned on the next update, so the state file
stays bounded by the recent-activity set rather than growing forever
(Copilot review finding, theme_window.py:16).

Read-only with respect to memory/canon: this module only maintains its own
small rolling-window state file under meta/world_radar/theme_window.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Generous default: at daily cadence this is ~90 cycles of recurrence memory,
# comfortably longer than any realistic verification backlog, while still
# bounding the state file's growth over months/years of continuous operation.
MAX_WINDOW_AGE_DAYS = 90


@dataclass(frozen=True)
class ThemeWindowEntry:
    movement_id: str
    title: str
    first_seen_at: str
    last_seen_at: str
    occurrence_count: int
    best_weighted_score: float

    def to_json(self) -> dict[str, object]:
        return {
            "movement_id": self.movement_id,
            "title": self.title,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "occurrence_count": self.occurrence_count,
            "best_weighted_score": self.best_weighted_score,
        }


def _is_stale(entry: ThemeWindowEntry, now: datetime, max_age_days: int) -> bool:
    """An entry not seen again within max_age_days is stale and gets pruned.

    An unparseable/missing last_seen_at (garbled state) is treated as stale
    too -- fail closed toward pruning rather than accumulating unboundedly.
    """
    try:
        last_seen = datetime.fromisoformat(entry.last_seen_at)
    except (TypeError, ValueError):
        return True
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (now - last_seen) > timedelta(days=max_age_days)


def _weighted_score(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def load_theme_window(path: Path) -> dict[str, ThemeWindowEntry]:
    """Defensive load. Missing or garbled state -> empty window, never a crash."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}
    window: dict[str, ThemeWindowEntry] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        movement_id = str(row.get("movement_id") or "")
        if not movement_id:
            continue
        try:
            window[movement_id] = ThemeWindowEntry(
                movement_id=movement_id,
                title=str(row.get("title") or ""),
                first_seen_at=str(row.get("first_seen_at") or ""),
                last_seen_at=str(row.get("last_seen_at") or ""),
                occurrence_count=int(row.get("occurrence_count") or 1),
                best_weighted_score=float(row.get("best_weighted_score") or 0.0),
            )
        except (TypeError, ValueError):
            continue
    return window


def save_theme_window(path: Path, window: dict[str, ThemeWindowEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"entries": [entry.to_json() for entry in window.values()]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def update_theme_window(
    window: dict[str, ThemeWindowEntry],
    movements: list[dict[str, Any]],
    *,
    max_age_days: int = MAX_WINDOW_AGE_DAYS,
) -> tuple[dict[str, ThemeWindowEntry], tuple[str, ...]]:
    """Fold this cycle's movements into the rolling window, then prune.

    Returns (updated_window, newly_seen_movement_ids) -- the latter is the
    cheap "what's actually new this cycle" signal a capped downstream
    consumer (e.g. deep_sweep's verification budget) can use instead of
    re-processing every movement every time.

    Prunes any entry not seen again within max_age_days -- this is what makes
    it an actual rolling window instead of an unbounded accumulator.
    """
    updated = dict(window)
    newly_seen: list[str] = []
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    for movement in movements:
        movement_id = str(movement.get("movement_id") or "")
        if not movement_id:
            continue
        title = str(movement.get("title") or "")
        score = _weighted_score(movement.get("weighted_score"))
        existing = updated.get(movement_id)
        if existing is None:
            updated[movement_id] = ThemeWindowEntry(
                movement_id=movement_id,
                title=title,
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
                best_weighted_score=score,
            )
            newly_seen.append(movement_id)
        else:
            updated[movement_id] = replace(
                existing,
                last_seen_at=now,
                occurrence_count=existing.occurrence_count + 1,
                best_weighted_score=max(existing.best_weighted_score, score),
                # Title can drift slightly cycle to cycle (title-key
                # clustering, not a stable key); keep the latest.
                title=title or existing.title,
            )
    pruned = {
        movement_id: entry
        for movement_id, entry in updated.items()
        if not _is_stale(entry, now_dt, max_age_days)
    }
    return pruned, tuple(newly_seen)


def run_theme_window_update(state_dir: Path) -> dict[str, object]:
    """Read the current world_signal_board, fold it into the persisted
    theme window, write the window back, and return a small summary.

    Defensive: a missing/garbled board yields an empty-movements update
    (window unchanged, no crash) rather than raising.
    """
    # .resolve() canonicalizes '..' segments/symlinks, matching the other
    # write-producing entrypoints in this PR (deep_sweep, zeitgeist_promotion)
    # (Copilot review finding, theme_window.py:147).
    meta = state_dir.expanduser().resolve() / "meta"
    board_path = meta / "world_signal_board.json"
    window_path = meta / "world_radar" / "theme_window.json"

    movements: list[dict[str, Any]] = []
    if board_path.exists():
        try:
            board = json.loads(board_path.read_text(encoding="utf-8"))
            if isinstance(board, dict) and isinstance(board.get("movements"), list):
                movements = [m for m in board["movements"] if isinstance(m, dict)]
        except (OSError, json.JSONDecodeError):
            movements = []

    window = load_theme_window(window_path)
    updated, newly_seen = update_theme_window(window, movements)
    save_theme_window(window_path, updated)

    return {
        "window_path": str(window_path),
        "total_tracked_themes": len(updated),
        "movements_this_cycle": len(movements),
        "newly_seen_count": len(newly_seen),
        "newly_seen_movement_ids": list(newly_seen),
    }


__all__ = [
    "MAX_WINDOW_AGE_DAYS",
    "ThemeWindowEntry",
    "load_theme_window",
    "save_theme_window",
    "update_theme_window",
    "run_theme_window_update",
]
