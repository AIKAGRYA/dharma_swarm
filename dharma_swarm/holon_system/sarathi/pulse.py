"""Read-only Sarathi pulse projection."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from dharma_swarm.holon_health import holon_status
from .roster import DEFAULT_ROSTER


def sarathi_pulse(roster: Iterable[str] = DEFAULT_ROSTER, *, agents_root: str | Path | None = None) -> dict[str, object]:
    """Return an honest status projection; does not start or mutate agents."""
    root = Path(agents_root).expanduser() if agents_root is not None else None
    rows = []
    for name in roster:
        try:
            rows.append(holon_status(str(name), agents_root=root))
        except Exception as exc:  # noqa: BLE001 - pulse is diagnostic, not a gate
            rows.append({"name": str(name), "registered": False, "error": str(exc)[:200]})
    return {
        "schema_version": "dharma.sarathi.pulse.v1",
        "wake_loop_active": False,
        "alive_claim": False,
        "roster": rows,
    }


__all__ = ["sarathi_pulse"]
