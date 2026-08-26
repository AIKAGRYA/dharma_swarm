"""Canonical process-identity probes for the live organism.

Two failure modes this module exists to close, both found by review on the
liveness-oracle PR:

1. **Command-form drift.** Every surface that asked "is orchestrate-live
   running?" carried its own needle list. ``com.dharma.swarm.plist`` execs the
   console script (``dgc orchestrate-live``) while
   ``scripts/runtime/dharma_swarm_release_runner.sh`` execs the isolated release
   entrypoint. A scanner that knew only one
   spelling reported a healthy host dead — the opposite of the loud-failure
   property this lane exists for.

2. **PID reuse.** ``kill -0`` proves that *a* process holds the number, not
   that it is *the* organism. After a PID wrap a corpse's snapshot reads as
   live. ``daemon_pid_alive`` therefore treats existence as necessary but not
   sufficient: if the PID's command line can be read and positively belongs to
   something else, the owner is gone.

The disconfirmation is deliberately asymmetric. An unreadable command line
never downgrades a live PID (``ps`` may be unavailable, sandboxed, or slow),
and the "is this ours" marker set is broad, so an unlisted-but-genuine launch
spelling still reads as alive. Only positive evidence of a foreign process
turns ``True`` into ``False``.
"""

from __future__ import annotations

import os
import subprocess

# Every command form the organism is actually launched under. Sources, in
# order: com.dharma.swarm.plist (console script), release runner (isolated module
# form), Dockerfile.swarm (container entrypoint), direct script invocation,
# legacy shell launcher. tests/test_runtime_command_forms.py pins these
# against the real launch definitions so the list cannot drift again.
ORCHESTRATE_COMMAND_NEEDLES: tuple[str, ...] = (
    "dgc orchestrate-live",
    "dharma_swarm.runtime_release_entrypoint orchestrate-live",
    "dharma_swarm.dgc_cli orchestrate-live",
    "dharma_swarm.orchestrate_live",
    "orchestrate_live.py",
    "run_daemon.sh",
)

# Broad "this process belongs to the estate" markers used only to *disconfirm*
# a recycled PID. Kept wide on purpose: a false negative here would resurrect
# the false-dead bug the needles above fix.
RUNTIME_IDENTITY_MARKERS: tuple[str, ...] = (
    "dharma_swarm",
    "orchestrate",
    "dgc",
)


def matches_orchestrate_command(command: str) -> bool:
    """True if ``command`` is one of the organism's launch spellings."""
    return any(needle in command for needle in ORCHESTRATE_COMMAND_NEEDLES)


def orchestrate_pgrep_pattern() -> str:
    """The needle list as an ERE alternation, for ``pgrep -f`` callers.

    Only ``.`` needs escaping — ``-`` and ``_`` are literal outside brackets in
    POSIX ERE, and nothing here contains other metacharacters.
    """
    return "|".join(
        needle.replace(".", r"\.") for needle in ORCHESTRATE_COMMAND_NEEDLES
    )


def looks_like_runtime_command(command: str) -> bool:
    """True if ``command`` plausibly belongs to the dharma runtime at all."""
    return any(marker in command for marker in RUNTIME_IDENTITY_MARKERS)


def pid_alive(pid: int) -> bool:
    """Existence probe only: ``kill -0``. Never sufficient on its own."""
    try:
        if pid <= 1:
            return False
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def pid_command(pid: int, *, timeout: float = 5.0) -> str | None:
    """Return the command line for ``pid``, or None if it cannot be read."""
    if pid <= 1:
        return None
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=max(0.5, timeout),
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    command = (proc.stdout or "").strip()
    return command or None


def daemon_pid_alive(pid: int, *, timeout: float = 5.0) -> bool:
    """True only if ``pid`` exists AND is not provably a foreign process.

    A recorded PID that has been recycled onto an unrelated process is
    reported dead: the organism that wrote the artifact is gone, which is the
    only claim the caller is entitled to make.
    """
    if not pid_alive(pid):
        return False
    command = pid_command(pid, timeout=timeout)
    if command is None:
        return True
    return looks_like_runtime_command(command)
