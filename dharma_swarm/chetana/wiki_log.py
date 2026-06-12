"""Karpathy-style append-only wiki operation log."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import staging as staging_mod


def append_wiki_log(
    *,
    operation: str,
    title: str,
    atom_path: Path | None = None,
    atom_id: str | None = None,
    root: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Append a parseable operation entry to ``wiki/log.md``."""
    wiki_root = root or staging_mod.WIKI_ROOT
    wiki_root.mkdir(parents=True, exist_ok=True)
    log_path = wiki_root / "log.md"
    stamp = (now or datetime.now().astimezone()).strftime("%Y-%m-%d %H:%M")
    lines = [f"## [{stamp}] {operation} | {title}", ""]
    if atom_id:
        lines.append(f"- atom_id: {atom_id}")
    if atom_path:
        lines.append(f"- path: {atom_path}")
    lines.append("")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return log_path
