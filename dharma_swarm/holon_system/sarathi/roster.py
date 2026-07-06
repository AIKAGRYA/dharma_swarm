"""Sarathi sub-holon roster helpers."""

from __future__ import annotations

from pathlib import Path

DEFAULT_ROSTER = ("hermes-m5", "codex_composer", "fugu_ultra", "fable_composer")


def load_roster(path: str | Path | None = None) -> tuple[str, ...]:
    """Load a simple newline/YAML-list roster without creating runtime state."""
    if path is None:
        return DEFAULT_ROSTER
    roster_path = Path(path).expanduser()
    if not roster_path.exists():
        return DEFAULT_ROSTER
    names: list[str] = []
    for raw in roster_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line in {"sub_holons:", "agents:"}:
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if line:
            names.append(line)
    return tuple(names) or DEFAULT_ROSTER


__all__ = ["DEFAULT_ROSTER", "load_roster"]
