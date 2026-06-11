"""Kill-switch signaling for sovereign holons (U7).

Pure file-based stop signal. The autonomous wake loop (U5, not yet built) MUST check
``is_kill_requested`` at the top of each cycle and halt if set. This module animates
nothing — it just lets an operator (or a guardian process) raise a durable stop that the
loop honors on its next wake. Safety plumbing built BEFORE the loop, by design.

Canonical home: ``~/.dharma/agents/<name>/control/`` (see AGENT_HOME_RECONCILIATION.md).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

AGENTS_ROOT = Path.home() / ".dharma" / "agents"


def _kill_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "control" / "kill_requested.json"


def request_kill(name: str, reason: str = "", agents_root: Path | None = None) -> Path:
    """Raise a durable kill signal for a holon (atomic write). Idempotent."""
    path = _kill_path(name, agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "holon": name,
        "reason": reason,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)  # atomic rename
    return path


def is_kill_requested(name: str, agents_root: Path | None = None) -> bool:
    return _kill_path(name, agents_root).exists()


def read_kill(name: str, agents_root: Path | None = None) -> dict | None:
    path = _kill_path(name, agents_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"holon": name, "reason": "unparseable kill marker"}


def clear_kill(name: str, agents_root: Path | None = None) -> bool:
    """Clear a kill signal (e.g. operator resumes the holon). Returns True if one existed."""
    path = _kill_path(name, agents_root)
    if path.exists():
        path.unlink()
        return True
    return False
