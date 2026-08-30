"""RUDRA workcell: state root, mission lock, journal, private Git.

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md section 10.

Write zones (spec invariant 5): supervisor writes live only under
``$DHARMA_STATE_DIR/rudra``; the base checkout receives zero writes. The
mission-level ``fcntl.flock`` fd is held for the supervisor lifetime and is
never unlinked; age or TTL never authorizes takeover.

Decomposition (leaf modules, one-directional):
  process_owner — OS identity probes, group/descendant census, ProcessOwner
This module keeps the public API stable by re-exporting that leaf.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.rudra.contracts import sha256_json
from dharma_swarm.rudra.process_owner import (
    ProcessOwner as ProcessOwner,
    ProcessProbeError as ProcessProbeError,
    descendants_of as descendants_of,
    os_boot_id as os_boot_id,
    process_command as process_command,
    process_cwd as process_cwd,
    process_start_id as process_start_id,
    _pgid_members as _pgid_members,
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


# --- State root and mission lock --------------------------------------------


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


# --- Journal: sequenced, fsynced JSONL, intent/result effects, CAS seal -----

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


# --- Hermetic Git invocation (spec section 8 step 4) -----------------------


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


def init_private_git(
    gitdir: Path,
    worktree: Path,
    *,
    alternates: Sequence[str],
    ref_steps: Sequence[Sequence[str]],
    env: dict[str, str],
) -> None:
    """Fixed workcell construction (spec section 10): bare private gitdir,
    read-only alternates, caller-chosen ref steps, .git pointer, populated
    worktree. Never writes worktree metadata, refs, objects, or index state
    to the base repository."""
    require_git_ok(run_git(["init", "--bare", str(gitdir)], env=env), "init")
    alt = gitdir / "objects" / "info" / "alternates"
    alt.parent.mkdir(parents=True, exist_ok=True)
    alt.write_text("".join(f"{a}\n" for a in alternates))
    steps = [
        *ref_steps,
        ["config", "core.worktree", str(worktree)],
        ["config", "core.bare", "false"],
    ]
    for step in steps:
        require_git_ok(run_git(["--git-dir", str(gitdir), *step], env=env), step[0])
    # .git pointer: target lives under the supervisor state root, outside
    # the executor-writable policy boundary for git control surfaces.
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n")
    for populate in (["read-tree", "HEAD"], ["checkout-index", "-f", "-a"]):
        require_git_ok(
            run_git(
                ["--git-dir", str(gitdir), "--work-tree", str(worktree), *populate],
                env=env, timeout=300,
            ),
            populate[0],
        )


# --- Workcell: private supervisor-owned Git directory, base byte preservation


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

    def create(self) -> None:
        """Create the private gitdir and checkout at the exact base (spec
        section 10): private ref at base, read-only alternate into the base
        object store. The base repository receives no writes."""
        env = hermetic_git_env(self._env_home)
        self.private_git.mkdir(parents=True)
        self.worktree.mkdir(parents=True)
        self._env_home.mkdir(parents=True, exist_ok=True)
        init_private_git(
            self.private_git,
            self.worktree,
            alternates=[str(self.base_repo / ".git" / "objects")],
            ref_steps=[
                ["update-ref", "refs/rudra/work", self.base_sha],
                ["symbolic-ref", "HEAD", "refs/rudra/work"],
            ],
            env=env,
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
