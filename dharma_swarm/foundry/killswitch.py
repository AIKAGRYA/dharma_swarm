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

from pathlib import Path

from dharma_swarm.holon_killswitch import is_kill_requested, read_kill

FOUNDRY_HOLON = "sublimation-foundry"
_STOP_FILE = Path.home() / ".dharma" / "foundry" / "STOP"


class FoundryStopped(RuntimeError):
    """Raised by :func:`check` when a durable stop signal is present."""


def _stop_file(state_root: Path | None = None) -> Path:
    if state_root is not None:
        return Path(state_root) / "STOP"
    return _STOP_FILE


def is_stopped(*, agents_root: Path | None = None, state_root: Path | None = None) -> bool:
    return is_kill_requested(FOUNDRY_HOLON, agents_root) or _stop_file(state_root).exists()


def stop_reason(*, agents_root: Path | None = None, state_root: Path | None = None) -> str:
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
