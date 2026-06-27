"""Append-only Holon cycle persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from holon.receipts import utc_now


def cycle_ledger_path(name: str, *, agents_root: Path) -> Path:
    return agents_root / name / "wake_ledger.jsonl"


def load_session(name: str, *, agents_root: Path) -> list[dict[str, Any]]:
    path = cycle_ledger_path(name, agents_root=agents_root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            events.append(loaded)
    return events


def resume_point(name: str, *, agents_root: Path) -> dict[str, int]:
    events = load_session(name, agents_root=agents_root)
    if not events:
        return {"cycle": -1, "next_cycle": 0}
    cycle = int(events[-1].get("cycle", -1))
    return {"cycle": cycle, "next_cycle": cycle + 1}


def save_cycle_record(name: str, record: dict[str, Any], *, agents_root: Path) -> dict[str, Any]:
    path = cycle_ledger_path(name, agents_root=agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    next_cycle = resume_point(name, agents_root=agents_root)["next_cycle"]
    event = {
        "schema_version": "holon.wake_cycle_record.v1",
        "holon": name,
        "cycle": next_cycle,
        "at": utc_now(),
        "record": record,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event
