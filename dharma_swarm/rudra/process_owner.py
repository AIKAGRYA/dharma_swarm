"""RUDRA process ownership: OS identity probes and the spawn/signal authority.

Leaf module of ``workcell``: owns the process-identity probes (boot id,
start time, command, cwd), the process-group/descendant census, and
``ProcessOwner``. It never imports the workcell module — the dependency
direction is ``workcell`` -> ``process_owner`` only.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md sections 7, 10.
"""

from __future__ import annotations

import os
import platform
import re
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.rudra.contracts import DerivedStatus, ProcessHandle


class ProcessProbeError(RuntimeError):
    pass


# --- OS identity helpers (spec section 10) ----------------------------------


def parse_proc_stat_btime(text: str) -> str:
    """Boot epoch from Linux /proc/stat content (the ``btime <epoch>`` line)."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "btime" and parts[1].isdigit():
            return parts[1]
    raise ProcessProbeError("no btime line in /proc/stat content")


_PROC_STAT_PATH = Path("/proc/stat")


def os_boot_id() -> str:
    """Machine boot epoch; deliberately not spine.identity.process_boot_id.

    The value feeds PID-reuse identity (spec section 10), so it must be the
    host boot epoch on every platform: ``btime`` from /proc/stat on Linux,
    ``kern.boottime`` via sysctl on Darwin."""
    if platform.system() == "Linux":
        return parse_proc_stat_btime(_PROC_STAT_PATH.read_text(encoding="utf-8"))
    out = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "kern.boottime"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    match = re.search(r"sec\s*=\s*(\d+)", out)
    if not match:
        raise ProcessProbeError(f"cannot parse kern.boottime: {out!r}")
    return match.group(1)


def process_start_id(pid: int) -> str | None:
    """OS-observed process start time, or None when the pid is gone."""
    out = subprocess.run(
        ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return out or None


def process_command(pid: int) -> str | None:
    out = subprocess.run(
        ["/bin/ps", "-o", "comm=", "-p", str(pid)],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return out or None


def process_cwd(pid: int) -> str | None:
    if platform.system() == "Linux":
        # lsof lives at /usr/bin on Linux and may be absent on slim runners;
        # the /proc symlink is the same honest OS observation.
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return None
    out = subprocess.run(
        ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        capture_output=True, text=True, timeout=15,
    ).stdout
    for line in out.splitlines():
        if line.startswith("n") and not line.startswith("ncwd"):
            return line[1:]
    return None


def _pgid_members(pgid: int) -> list[int]:
    out = subprocess.run(
        ["/bin/ps", "-axo", "pid=,pgid="],
        capture_output=True, text=True, timeout=15,
    ).stdout
    members = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and int(parts[1]) == pgid:
            members.append(int(parts[0]))
    return members


def descendants_of(root_pid: int) -> set[int]:
    """All descendants by ppid lineage, including setsid escapees."""
    out = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid="],
        capture_output=True, text=True, timeout=15,
    ).stdout
    children: dict[int, list[int]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            pid, ppid = int(parts[0]), int(parts[1])
            children.setdefault(ppid, []).append(pid)
    found: set[int] = set()
    queue = [root_pid]
    while queue:
        for child in children.get(queue.pop(), []):
            if child not in found:
                found.add(child)
                queue.append(child)
    found.discard(os.getpid())
    return found


# --- ProcessOwner: sole spawn/signal/reap authority (spec sections 7, 10) ---


class ProcessOwner:
    """Owns every app-server, verifier, and tool process session."""

    def __init__(self, run_nonce: str | None = None) -> None:
        self.run_nonce = run_nonce or uuid.uuid4().hex
        self._procs: dict[int, subprocess.Popen[Any]] = {}
        # Witness log for best-effort signal/reap failures during teardown.
        # A dead-pid race is expected; it is recorded, never swallowed.
        self.signal_failures: list[str] = []

    def spawn(
        self,
        argv: Sequence[str],
        *,
        env: dict[str, str],
        cwd: Path,
        stdout: Any = subprocess.PIPE,
        stderr: Any = subprocess.PIPE,
    ) -> tuple[subprocess.Popen[Any], ProcessHandle]:
        proc = subprocess.Popen(  # noqa: S603 - argv array, no shell
            list(argv),
            env=env,
            cwd=str(cwd),
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        start_id = process_start_id(proc.pid) or "unknown"
        handle = ProcessHandle(
            pid=proc.pid,
            pgid=os.getpgid(proc.pid),
            os_boot_id=os_boot_id(),
            process_start_id=start_id,
            executable=os.path.realpath(argv[0]),
            cwd=str(cwd),
            run_nonce=self.run_nonce,
        )
        self._procs[proc.pid] = proc
        return proc, handle

    def identity_status(self, handle: ProcessHandle) -> str:
        """alive | dead | ambiguous. Ambiguous never receives a signal.

        Restart matching (spec section 10) compares PID, OS start time, OS
        boot identity, executable, and cwd; any observation failure is
        ambiguous, never alive."""
        start = process_start_id(handle.pid)
        if start is None:
            return "dead"
        if handle.os_boot_id != os_boot_id():
            return "dead"  # host rebooted; the pid namespace was reset
        if start != handle.process_start_id:
            return "dead"  # pid reused by another process
        actual_comm = process_command(handle.pid)
        actual_cwd = process_cwd(handle.pid)
        if actual_comm is None or actual_cwd is None:
            return "ambiguous"
        actual_real = (
            os.path.realpath(actual_comm)
            if actual_comm.startswith("/")
            else actual_comm
        )
        if os.path.basename(actual_real) != os.path.basename(handle.executable):
            return "ambiguous"
        if os.path.realpath(actual_cwd) != os.path.realpath(handle.cwd):
            return "ambiguous"
        return "alive"

    def terminate_tree(
        self, handle: ProcessHandle, grace_seconds: float = 2.0
    ) -> bool:
        """TERM group, bounded grace, KILL group plus any setsid escapees
        found by ppid lineage, reap, and prove zero descendants.

        Signal and reap races against already-dead pids are expected during
        teardown; each one is recorded in ``signal_failures`` as evidence
        rather than swallowed silently."""
        targets = set(_pgid_members(handle.pgid)) | descendants_of(handle.pid)
        targets.add(handle.pid)
        try:
            os.killpg(handle.pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError) as exc:
            self.signal_failures.append(f"killpg TERM pgid={handle.pgid}: {exc!r}")
        for pid in targets:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError) as exc:
                self.signal_failures.append(f"kill TERM pid={pid}: {exc!r}")
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if not self._census(handle):
                break
            time.sleep(0.05)
        survivors = self._census(handle)
        if survivors:
            try:
                os.killpg(handle.pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError) as exc:
                self.signal_failures.append(
                    f"killpg KILL pgid={handle.pgid}: {exc!r}"
                )
            for pid in survivors:
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError) as exc:
                    self.signal_failures.append(f"kill KILL pid={pid}: {exc!r}")
        proc = self._procs.pop(handle.pid, None)
        if proc is not None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False
            except (ProcessLookupError, ChildProcessError, OSError) as exc:
                self.signal_failures.append(f"reap pid={handle.pid}: {exc!r}")
        time.sleep(0.05)
        return not self._census(handle)

    def _census(self, handle: ProcessHandle) -> set[int]:
        members = set(_pgid_members(handle.pgid))
        members |= descendants_of(handle.pid)
        members.discard(os.getpid())
        return members

    def prove_dead(self, handle: ProcessHandle) -> bool:
        """Zero descendants in the group and no identity-matching pid."""
        if self._census(handle):
            return False
        return self.identity_status(handle) == "dead"

    def status_for_recovery(self, handles: list[ProcessHandle]) -> DerivedStatus | None:
        """Any survivor or ambiguity blocks a new turn (spec section 13)."""
        for handle in handles:
            status = self.identity_status(handle)
            if status == "alive":
                self.terminate_tree(handle)
                if not self.prove_dead(handle):
                    return DerivedStatus.RECOVERY_REQUIRED
            elif status == "ambiguous":
                return DerivedStatus.RECOVERY_REQUIRED
        return None
