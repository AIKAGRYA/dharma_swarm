"""Holon session persistence/replay (U6) — append-only cycle-record log so a holon
survives restart and resumes rather than repeating.

Pure file I/O, append-only, JSONL. Reuses the canonical agent home and the witness /
conversation_log / compass-signal append pattern (``_path`` helper +
``mkdir(parents=True, exist_ok=True)`` + line-delimited JSON). Does NOT create a new
top-level tree: events live alongside the holon's other per-agent state in
``~/.dharma/agents/<name>/holon_events.jsonl``.

A "cycle record" is whatever the loop wants to persist for one cycle (an arbitrary JSON
dict). This layer is storage-only: it does not interpret governance, never blocks, never
calls a model. Restart-replay = read prior events back in order; ``resume_point`` returns
the last cycle so a restarted loop continues from cycle N+1.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path.home() / ".dharma" / "agents"


def _events_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "holon_events.jsonl"


def save_cycle_record(
    name: str,
    record: dict[str, Any],
    agents_root: Path | None = None,
) -> dict[str, Any]:
    """Append one cycle record to ``~/.dharma/agents/<name>/holon_events.jsonl``.

    The stored event wraps the caller's ``record`` with a monotonically increasing
    ``cycle`` index (derived from the count of prior events) and an ``at`` UTC timestamp,
    so a restarted loop can read the last ``cycle`` and continue from the next one. The
    original record payload is preserved under the ``record`` key (and the event is
    returned). Append-only: never rewrites or truncates the file.
    """
    if not isinstance(record, dict):
        raise TypeError(f"record must be a dict, got {type(record).__name__}")

    path = _events_path(name, agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    cycle = len(load_session(name, agents_root))
    event = {
        "cycle": cycle,
        "holon": name,
        "at": datetime.now(timezone.utc).isoformat(),
        "record": record,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def load_session(name: str, agents_root: Path | None = None) -> list[dict[str, Any]]:
    """Return the holon's prior cycle events in append order (empty list if none).

    Missing file → ``[]``. Malformed/blank lines are skipped with a warning so a single
    corrupt append can never make a restart unreplayable (replay must degrade, not crash).
    """
    path = _events_path(name, agents_root)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning(
                "[holon %s] skipping malformed event at line %d: %s", name, lineno, exc
            )
    return events


def resume_point(name: str, agents_root: Path | None = None) -> dict[str, Any] | None:
    """Return the last cycle event (so a restarted loop continues at cycle+1), or None.

    None means no prior session → a restarted loop starts fresh at cycle 0. The returned
    event carries ``cycle`` (last completed index) and ``record`` (its payload); the loop
    resumes from ``cycle + 1``.
    """
    events = load_session(name, agents_root)
    if not events:
        return None
    return events[-1]
