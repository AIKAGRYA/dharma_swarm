"""Read-only health projection for standalone Holon."""

from __future__ import annotations

from pathlib import Path

from .killswitch import is_kill_requested
from .persistence import load_session


def holon_status(name: str, *, agents_root: Path) -> dict[str, object]:
    root = agents_root / name
    events = load_session(name, agents_root=agents_root)
    return {
        "holon": name,
        "living_dock_path": str(root),
        "identity_present": (root / "identity.json").exists(),
        "kill_requested": is_kill_requested(name, agents_root=agents_root),
        "cycle_count": len(events),
        "last_status": events[-1].get("record", {}).get("status") if events else "none",
    }
