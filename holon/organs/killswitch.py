"""Durable kill switch for standalone Holon."""

from __future__ import annotations

import json
import re
from pathlib import Path

from holon.receipts import utc_now

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


def _agent_dir(name: str, agents_root: Path) -> Path:
    if not _NAME_RE.fullmatch(name or ""):
        raise ValueError("invalid holon name")
    return agents_root / name


def _kill_path(name: str, agents_root: Path) -> Path:
    return _agent_dir(name, agents_root) / "kill.json"


def request_kill(name: str, *, reason: str = "operator stop", agents_root: Path) -> dict[str, str]:
    path = _kill_path(name, agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"holon": name, "reason": reason, "requested_at": utc_now()}
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def clear_kill(name: str, *, agents_root: Path) -> bool:
    path = _kill_path(name, agents_root)
    if not path.exists():
        return False
    path.unlink()
    return True


def is_kill_requested(name: str, *, agents_root: Path) -> bool:
    return _kill_path(name, agents_root).exists()
