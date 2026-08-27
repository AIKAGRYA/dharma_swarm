"""Foundry kill-switch wiring.

The standing loop MUST call :func:`check` at the top of every generation and
halt if a stop is raised. Two durable stop signals are honored:

- the holon kill-switch (``dharma_swarm.holon_killswitch`` — the repo-wide
  mechanism, ``~/.dharma/agents/<holon>/control/kill_requested.json``), and
- a simple operator ``~/.dharma/foundry/STOP`` file.

The GitHub Actions loop additionally honors the ``loop-control`` branch
``docs/ops/loop_control/KILLSWITCH`` via the shared ``loop-killswitch`` action;
that is enforced in the workflow, not here.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.holon_killswitch import is_kill_requested, read_kill

FOUNDRY_HOLON = "sublimation-foundry"
_STOP_FILE = Path.home() / ".dharma" / "foundry" / "STOP"
_KILL_FILE = "KILL.json"


class FoundryStopped(RuntimeError):
    """Raised by :func:`check` when a durable stop signal is present."""


def _stop_file(state_root: Path | None = None) -> Path:
    if state_root is not None:
        return Path(state_root) / "STOP"
    return _STOP_FILE


def terminal_kill_file(state_root: Path | None = None) -> Path:
    root = Path(state_root) if state_root is not None else _STOP_FILE.parent
    return root / _KILL_FILE


def read_terminal_kill(state_root: Path | None = None) -> dict[str, Any] | None:
    """Read the terminal marker; malformed evidence still means stop."""
    path = terminal_kill_file(state_root)
    try:
        marker_stat = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        return {
            "schema_version": "foundry_terminal_kill.corrupt",
            "category": "corrupt_kill_marker",
            "reason": f"terminal KILL marker cannot be inspected ({type(exc).__name__})",
        }
    if not stat.S_ISREG(marker_stat.st_mode):
        return {
            "schema_version": "foundry_terminal_kill.corrupt",
            "category": "corrupt_kill_marker",
            "reason": "terminal KILL marker is not a regular file",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        return {
            "schema_version": "foundry_terminal_kill.corrupt",
            "category": "corrupt_kill_marker",
            "reason": f"terminal KILL marker unreadable ({type(exc).__name__})",
        }
    if not isinstance(payload, dict):
        return {
            "schema_version": "foundry_terminal_kill.corrupt",
            "category": "corrupt_kill_marker",
            "reason": "terminal KILL marker is not an object",
        }
    return payload


def persist_terminal_kill(
    state_root: Path,
    *,
    category: str,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> Path:
    """Persist the first terminal verdict; later failures cannot replace it."""
    path = terminal_kill_file(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "foundry_terminal_kill.v1",
        "category": category,
        "reason": reason,
        "evidence": evidence or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Validate the complete marker before claiming the exclusive authoritative
    # path. Otherwise a serialization error can strand a truncated first-cause
    # file that no later writer is permitted to repair.
    try:
        serialized = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        # Evidence is subordinate to the stop verdict. Preserve the typed
        # first cause in a valid marker even when optional evidence cannot be
        # encoded, so malformed diagnostics can never keep the loop alive.
        payload["evidence"] = {}
        payload["evidence_serialization_error"] = type(exc).__name__
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        # Terminal means terminal: preserve the original causal marker.
        return path
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return path


def has_terminal_kill(state_root: Path | None = None) -> bool:
    try:
        terminal_kill_file(state_root).lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _quarantine_files(state_root: Path | None = None) -> tuple[Path, Path]:
    root = Path(state_root) if state_root is not None else _STOP_FILE.parent
    return root / "QUARANTINE.json", root / "QUARANTINE"


def is_stopped(*, agents_root: Path | None = None, state_root: Path | None = None) -> bool:
    return (
        has_terminal_kill(state_root)
        or any(path.exists() for path in _quarantine_files(state_root))
        or is_kill_requested(FOUNDRY_HOLON, agents_root)
        or _stop_file(state_root).exists()
    )


def stop_reason(*, agents_root: Path | None = None, state_root: Path | None = None) -> str:
    terminal = read_terminal_kill(state_root)
    if terminal:
        return (
            f"terminal KILL [{terminal.get('category', 'unknown')}]: "
            f"{terminal.get('reason') or '(no reason given)'}"
        )
    quarantine = next(
        (path for path in _quarantine_files(state_root) if path.exists()),
        None,
    )
    if quarantine is not None:
        return f"evidence quarantine requires operator review: {quarantine}"
    if _stop_file(state_root).exists():
        return f"operator STOP file present: {_stop_file(state_root)}"
    marker = read_kill(FOUNDRY_HOLON, agents_root)
    if marker:
        return f"holon kill requested: {marker.get('reason') or '(no reason given)'}"
    return ""


def check(*, agents_root: Path | None = None, state_root: Path | None = None) -> None:
    """Raise :class:`FoundryStopped` if any durable stop signal is present."""
    if is_stopped(agents_root=agents_root, state_root=state_root):
        raise FoundryStopped(stop_reason(agents_root=agents_root, state_root=state_root))
