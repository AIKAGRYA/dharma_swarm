"""RUDRA workcell: state root, mission lock, journal, private Git, processes.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 10.

Write zones (spec invariant 5): all supervisor control/evidence writes live
under ``$DHARMA_STATE_DIR/rudra``; executor mutations live only in the
mutation workcell; the base checkout receives zero writes. The mission-level
``fcntl.flock`` fd is held for the supervisor lifetime and is never unlinked;
age or TTL never authorizes takeover.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.rudra.contracts import (
    DerivedStatus,
    ProcessHandle,
    sha256_json,
)


class WorkcellError(RuntimeError):
    pass


class LockHeldError(WorkcellError):
    pass


class JournalCorrupt(WorkcellError):
    pass


class JournalConflict(WorkcellError):
    pass


class SealedJournalViolation(WorkcellError):
    pass


# ---------------------------------------------------------------------------
# OS identity helpers
# ---------------------------------------------------------------------------


def os_boot_id() -> str:
    """macOS boot identity; deliberately not spine.identity.process_boot_id."""
    out = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "kern.boottime"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    match = re.search(r"sec\s*=\s*(\d+)", out)
    if not match:
        raise WorkcellError(f"cannot parse kern.boottime: {out!r}")
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


# ---------------------------------------------------------------------------
# State root and mission lock
# ---------------------------------------------------------------------------


def rudra_state_root(state_dir: Path | None = None) -> Path:
    """Symlink-safe state root outside every repository and workcell."""
    base = state_dir or dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME")
    if Path(base).is_symlink():
        raise WorkcellError(f"state dir {base} is a symlink")
    root = Path(base) / "rudra"
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise WorkcellError(f"state root {root} is a symlink")
    return root.resolve()


class MissionLock:
    """One never-unlinked mission-level kernel lock.

    Acquired with LOCK_EX | LOCK_NB before the current-attempt pointer is
    read or created; the fd is held for the supervisor lifetime so a second
    supervisor can never coexist, regardless of chosen attempt IDs.
    """

    def __init__(self, mission_dir: Path) -> None:
        self.path = mission_dir / "supervisor.lock"
        self.run_uuid = uuid.uuid4().hex
        self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self._fd)
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise LockHeldError(f"mission lock held: {self.path}") from exc
            raise
        identity = {
            "run_uuid": self.run_uuid,
            "pid": os.getpid(),
            "pgid": os.getpgid(0),
            "os_boot_id": os_boot_id(),
            "process_start_id": process_start_id(os.getpid()),
            "executable": os.sys.executable,
            "cwd": os.getcwd(),
        }
        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        payload = (json.dumps(identity) + "\n").encode()
        os.write(self._fd, payload)
        os.fsync(self._fd)

    def close(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass

    def __enter__(self) -> "MissionLock":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Journal: sequenced, fsynced JSONL with intent/result effects and CAS seal
# ---------------------------------------------------------------------------

_TERMINAL_EVENT = "TERMINAL"


class Journal:
    """Crash-recovery evidence, not a task database (spec section 10)."""

    def __init__(self, path: Path, mission_key: str, attempt_key: str) -> None:
        self.path = path
        self.mission_key = mission_key
        self.attempt_key = attempt_key
        self._rows: list[dict[str, Any]] | None = None

    def _append_row(self, row: dict[str, Any]) -> None:
        line = (json.dumps(row, sort_keys=True, default=str) + "\n").encode()
        with open(self.path, "ab") as fh:
            view = memoryview(line)
            while view:  # complete-write loop
                written = fh.write(view)
                view = view[written:]
            fh.flush()
            os.fsync(fh.fileno())

    def rows(self) -> list[dict[str, Any]]:
        if self._rows is None:
            self._rows = self._load()
        return self._rows

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        with open(self.path, "rb") as fh:
            lines = fh.read().split(b"\n")
        for index, raw in enumerate(lines):
            if raw == b"" and index == len(lines) - 1:
                break  # trailing newline
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise JournalCorrupt(f"corrupt journal row {index + 1}") from exc
            if row.get("seq") != index + 1:
                raise JournalCorrupt(
                    f"journal sequence gap/reorder at row {index + 1}"
                )
            if row.get("event_id") in seen_ids:
                raise JournalCorrupt(f"duplicate event_id at row {index + 1}")
            seen_ids.add(row.get("event_id"))
            rows.append(row)
        return rows

    def has_torn_tail(self) -> bool:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return False
        with open(self.path, "rb") as fh:
            data = fh.read()
        return not data.endswith(b"\n")

    def repair_torn_tail(self) -> bool:
        """Only a torn final line may be truncated, under the held lock."""
        if not self.has_torn_tail():
            return False
        data = self.path.read_bytes()
        cut = data.rfind(b"\n")
        tail = data[cut + 1:]
        artifact = self.path.with_suffix(".torn-tail")
        artifact.write_bytes(tail)
        with open(self.path, "r+b") as fh:
            fh.truncate(cut + 1)
            fh.flush()
            os.fsync(fh.fileno())
        self._rows = None
        self.append("JOURNAL_TAIL_REPAIRED", {"tail_sha256": hashlib.sha256(tail).hexdigest()})
        return True

    def terminal(self) -> dict[str, Any] | None:
        terms = [r for r in self.rows() if r.get("event") == _TERMINAL_EVENT]
        return terms[-1] if terms else None

    def post_seal_violation(self) -> bool:
        rows = self.rows()
        for index, row in enumerate(rows):
            if row.get("event") == _TERMINAL_EVENT and index != len(rows) - 1:
                return True
        return False

    def append(
        self,
        event: str,
        payload: dict[str, Any] | None = None,
        effect_key: str | None = None,
    ) -> dict[str, Any]:
        sealed = self.terminal()
        if sealed is not None and event != _TERMINAL_EVENT:
            raise SealedJournalViolation(
                f"journal sealed by {sealed['payload'].get('terminal')}; "
                f"refusing {event}"
            )
        rows = self.rows()
        row = {
            "seq": len(rows) + 1,
            "event_id": uuid.uuid4().hex,
            "event": event,
            "at": time.time(),
            "mission_key": self.mission_key,
            "attempt_key": self.attempt_key,
            "effect_key": effect_key,
            "payload": payload or {},
        }
        self._append_row(row)
        rows.append(row)
        return row

    def effect_intent(self, effect_key: str, parameters: Any) -> dict[str, Any]:
        return self.append(
            "EFFECT_INTENT",
            {"parameters_digest": sha256_json(parameters)},
            effect_key=effect_key,
        )

    def effect_result(self, effect_key: str, observation: Any) -> dict[str, Any]:
        """Idempotent on identical observation; conflict on divergence."""
        digest = sha256_json(observation)
        for row in self.rows():
            if row.get("effect_key") == effect_key and row.get("event") == "EFFECT_RESULT":
                prior = row["payload"].get("observation_digest")
                if prior == digest:
                    return row
                raise JournalConflict(f"conflicting result for effect {effect_key}")
        return self.append(
            "EFFECT_RESULT", {"observation_digest": digest}, effect_key=effect_key
        )

    def compare_and_seal_terminal(
        self, terminal: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Append succeeds only when no terminal exists; identical retries
        return the sealed row; conflicts are invariant violations."""
        existing = self.terminal()
        record = {"terminal": terminal, **payload}
        if existing is not None:
            prior = existing["payload"]
            if prior == record:
                return existing
            raise JournalConflict(
                f"conflicting terminal: sealed={prior.get('terminal')} new={terminal}"
            )
        return self.append(_TERMINAL_EVENT, record)


# ---------------------------------------------------------------------------
# Hermetic Git invocation
# ---------------------------------------------------------------------------


def hermetic_git_env(home: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def run_git(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str],
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        "/usr/bin/git",
        "-c", "core.hooksPath=/dev/null",
        "-c", "commit.gpgSign=false",
        *args,
    ]
    proc = subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
    )
    return proc


def require_git_ok(proc: subprocess.CompletedProcess[str], what: str) -> str:
    if proc.returncode != 0:
        raise WorkcellError(f"git {what} failed: {proc.stderr.strip()}")
    return proc.stdout


# ---------------------------------------------------------------------------
# Workcell: private supervisor-owned Git directory, base byte preservation
# ---------------------------------------------------------------------------


class Workcell:
    """One disposable mutation checkout with a private Git directory.

    The base checkout's Git directory, HEAD, index, and working-tree bytes
    are never written; the private gitdir references the base object store
    through a read-only alternate.
    """

    def __init__(
        self,
        attempt_dir: Path,
        base_repo: Path,
        base_sha: str,
        state_root: Path,
    ) -> None:
        self.attempt_dir = attempt_dir
        self.base_repo = base_repo
        self.base_sha = base_sha
        self.state_root = state_root
        self.private_git = attempt_dir / "private.git"
        self.worktree = attempt_dir / "mutation" / "repo"
        self._env_home = attempt_dir / "git-home"

    # -- construction ------------------------------------------------------

    def create(self) -> None:
        """Create the private gitdir and checkout at the exact base.

        Fixed construction (spec section 10): private init, read-only
        alternate into the base object store, private ref at base, .git
        pointer file in the worktree. The base repository receives no
        worktree metadata, refs, objects, or index changes.
        """
        env = hermetic_git_env(self._env_home)
        self.private_git.mkdir(parents=True)
        self.worktree.mkdir(parents=True)
        self._env_home.mkdir(parents=True, exist_ok=True)
        require_git_ok(
            run_git(["init", "--bare", str(self.private_git)], env=env), "init"
        )
        base_objects = self.base_repo / ".git" / "objects"
        alternates = self.private_git / "objects" / "info" / "alternates"
        alternates.parent.mkdir(parents=True, exist_ok=True)
        alternates.write_text(str(base_objects) + "\n")
        require_git_ok(
            run_git(
                ["--git-dir", str(self.private_git), "update-ref",
                 "refs/rudra/work", self.base_sha],
                env=env,
            ),
            "update-ref",
        )
        require_git_ok(
            run_git(
                ["--git-dir", str(self.private_git), "symbolic-ref",
                 "HEAD", "refs/rudra/work"],
                env=env,
            ),
            "symbolic-ref",
        )
        # .git pointer: target lives under the supervisor state root, outside
        # the executor-writable policy boundary for git control surfaces.
        (self.worktree / ".git").write_text(f"gitdir: {self.private_git}\n")
        require_git_ok(
            run_git(
                ["--git-dir", str(self.private_git), "config",
                 "core.worktree", str(self.worktree)],
                env=env,
            ),
            "config",
        )
        require_git_ok(
            run_git(
                ["--git-dir", str(self.private_git), "config", "core.bare", "false"],
                env=env,
            ),
            "config",
        )
        # Populate the private index and the worktree from the exact base.
        require_git_ok(
            run_git(
                ["--git-dir", str(self.private_git),
                 "--work-tree", str(self.worktree), "read-tree", "HEAD"],
                env=env, timeout=300,
            ),
            "read-tree",
        )
        require_git_ok(
            run_git(
                ["--git-dir", str(self.private_git),
                 "--work-tree", str(self.worktree), "checkout-index", "-f", "-a"],
                env=env, timeout=300,
            ),
            "checkout-index",
        )

    def git(self, *args: str, timeout: float = 60.0) -> str:
        return require_git_ok(
            run_git(
                list(args), cwd=self.worktree, env=hermetic_git_env(self._env_home),
                timeout=timeout,
            ),
            " ".join(args[:1]),
        )

    def env(self) -> dict[str, str]:
        return hermetic_git_env(self._env_home)

    def porcelain_z(self) -> str:
        return self.git("status", "--porcelain=v2", "-z", "--untracked-files=all")

    def head_sha(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def quarantine(self, reason: str) -> Path:
        """Never force-remove an ambiguous workcell; park it for review."""
        target = self.attempt_dir.parent / f"quarantine-{self.attempt_dir.name}"
        marker = self.attempt_dir / "QUARANTINE.txt"
        marker.write_text(f"{time.time()}\n{reason}\n")
        if not target.exists():
            shutil.move(str(self.attempt_dir), str(target))
        return target


# ---------------------------------------------------------------------------
# ProcessOwner: sole spawn/signal/reap authority (spec sections 7, 10)
# ---------------------------------------------------------------------------


class ProcessOwner:
    """Owns every app-server, verifier, and tool process session."""

    def __init__(self, run_nonce: str | None = None) -> None:
        self.run_nonce = run_nonce or uuid.uuid4().hex
        self._procs: dict[int, subprocess.Popen[Any]] = {}

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

    # -- identity ----------------------------------------------------------

    def identity_status(self, handle: ProcessHandle) -> str:
        """alive | dead | ambiguous. Ambiguous never receives a signal."""
        start = process_start_id(handle.pid)
        if start is None:
            return "dead"
        if handle.os_boot_id != os_boot_id():
            return "dead"  # host rebooted; the pid namespace was reset
        expected = {
            "start": handle.process_start_id,
            "comm": os.path.basename(handle.executable),
        }
        actual_comm = process_command(handle.pid)
        if start != expected["start"]:
            return "dead"  # pid reused by another process
        actual_comm = process_command(handle.pid)
        if actual_comm is None:
            return "ambiguous"
        actual_real = (
            os.path.realpath(actual_comm)
            if actual_comm.startswith("/")
            else actual_comm
        )
        if os.path.basename(actual_real) != expected["comm"]:
            return "ambiguous"
        return "alive"

    # -- teardown ----------------------------------------------------------

    def terminate_tree(
        self, handle: ProcessHandle, grace_seconds: float = 2.0
    ) -> bool:
        """TERM group, bounded grace, KILL group plus any setsid escapees
        found by ppid lineage, reap, and prove zero descendants."""
        targets = set(_pgid_members(handle.pgid)) | descendants_of(handle.pid)
        targets.add(handle.pid)
        try:
            os.killpg(handle.pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        for pid in targets:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if not self._census(handle):
                break
            time.sleep(0.05)
        survivors = self._census(handle)
        if survivors:
            try:
                os.killpg(handle.pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            for pid in survivors:
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
        proc = self._procs.pop(handle.pid, None)
        if proc is not None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return False
            except (ProcessLookupError, ChildProcessError, OSError):
                pass
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
