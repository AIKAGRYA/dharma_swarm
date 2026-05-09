"""Slop ledger: append-only JSONL log of every verification run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.slop.models import SlopLedgerEntry

LEDGER_DIR = Path.home() / ".dharma" / "slop_ledger"


def ledger_path(when: datetime | None = None, base: Path | None = None) -> Path:
    when = when or datetime.now(timezone.utc)
    base = base or LEDGER_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{when.strftime('%Y-%m-%d')}.jsonl"


def write_entries(
    entries: list[SlopLedgerEntry],
    *,
    base: Path | None = None,
) -> Path:
    if not entries:
        return ledger_path(base=base)
    when = datetime.fromisoformat(entries[0].timestamp.replace("Z", "+00:00"))
    target = ledger_path(when=when, base=base)
    with target.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry.to_jsonl_dict(), ensure_ascii=False) + "\n")
    return target


__all__ = ["LEDGER_DIR", "ledger_path", "write_entries"]
