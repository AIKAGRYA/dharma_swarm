"""Filesystem primitives for the canonical operator-core session store.

Module-level I/O helpers extracted from ``session_store`` so the store class
owns session semantics while this module owns the physical durable layout
under ``~/.dharma/sessions`` (owned by ``SessionStore``; see the
``state_dir.sessions`` entry in ``ACTIVE_SURFACE_MANIFEST.yaml``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
from typing import Any

from dharma_swarm.tui.engine.events import EVENT_TYPES, CanonicalEventType

_SESSION_RECOVERY_LOCKS: dict[Path, threading.RLock] = {}
_SESSION_RECOVERY_LOCKS_GUARD = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session_id() -> str:
    now = datetime.now(timezone.utc)
    return f"dgc-{now:%Y%m%d}-{now:%H%M%S}-{secrets.token_hex(2)}"


def _session_recovery_thread_lock(path: Path) -> threading.RLock:
    """Return the shared in-process half of a session recovery lock."""

    key = path.resolve()
    with _SESSION_RECOVERY_LOCKS_GUARD:
        return _SESSION_RECOVERY_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def session_recovery_file_lock(lock_path: Path) -> Iterator[None]:
    """Serialize one orphan-recovery decision across stores and processes.

    The retained sidecar keeps a stable inode for the host-local advisory
    lock. ``flock`` alone does not serialize independent store instances in
    every same-process runtime, so a shared thread lock protects that case.
    """

    with _session_recovery_thread_lock(lock_path):
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def normalize_cwd(cwd: str) -> str:
    try:
        return str(Path(cwd).expanduser().resolve())
    except Exception:
        return str(Path(cwd).expanduser())


def cwd_matches(meta_cwd: str, expected_cwd: str) -> bool:
    if meta_cwd == expected_cwd:
        return True
    return normalize_cwd(meta_cwd) == normalize_cwd(expected_cwd)


def observe_git_branch(cwd: str) -> str:
    """Sample the branch at session creation without making Git authoritative."""

    normalized_cwd = normalize_cwd(cwd)
    try:
        result = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "-C",
                normalized_cwd,
                "branch",
                "--show-current",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Replace one JSON owner file without exposing a truncated target."""

    temp_path = path.with_name(
        f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    )
    encoded = json.dumps(payload, indent=2)
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = -1
        if directory_fd >= 0:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
            finally:
                os.close(directory_fd)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def append_jsonl_record(path: Path, encoded: bytes) -> None:
    """Durably append one newline-terminated record, healing a torn tail."""

    with open(path, "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() > 0:
            handle.seek(-1, os.SEEK_END)
            if handle.read(1) != b"\n":
                handle.seek(0, os.SEEK_END)
                handle.write(b"\n")
        handle.seek(0, os.SEEK_END)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def append_jsonl_line(path: Path, payload: dict[str, Any]) -> None:
    with open(path, "a") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_transcript_events(
    path: Path,
    *,
    include_types: set[str] | None = None,
    limit: int | None = None,
) -> list[CanonicalEventType]:
    if not path.exists():
        return []

    events: list[CanonicalEventType] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        event_type = str(payload.get("type", "") or "").strip()
        if not event_type or (include_types is not None and event_type not in include_types):
            continue
        event_cls = EVENT_TYPES.get(event_type)
        if event_cls is None:
            continue
        try:
            events.append(event_cls(**payload))
        except Exception:
            continue

    if limit is not None and limit >= 0:
        return events[-limit:]
    return events


def read_audit_entries(
    path: Path,
    *,
    include_domains: set[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        domain = str(payload.get("domain", "") or "").strip()
        if include_domains is not None and domain not in include_domains:
            continue
        entries.append(payload)

    if limit is not None and limit >= 0:
        return entries[-limit:]
    return entries


def prune_audit_domains(path: Path, *, domains: set[str]) -> int:
    if not path.exists():
        return 0

    kept_lines: list[str] = []
    removed = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            kept_lines.append(raw_line)
            continue
        if not isinstance(payload, dict):
            kept_lines.append(raw_line)
            continue
        domain = str(payload.get("domain", "") or "").strip()
        if domain in domains:
            removed += 1
            continue
        kept_lines.append(raw_line)

    with open(path, "w", encoding="utf-8") as handle:
        for kept_line in kept_lines:
            handle.write(kept_line.rstrip("\n") + "\n")
    return removed


def index_entry_from_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    session_id = str(meta.get("session_id", "") or "").strip()
    if not session_id:
        return None
    return {
        "session_id": session_id,
        "title": str(meta.get("title", "") or ""),
        "provider_id": str(meta.get("provider_id", "") or ""),
        "model_id": str(meta.get("model_id", "") or ""),
        "created_at": str(meta.get("created_at", "") or ""),
        "updated_at": str(meta.get("updated_at", "") or ""),
        "status": str(meta.get("status", "") or ""),
        "total_cost_usd": float(meta.get("total_cost_usd", 0.0) or 0.0),
        "total_turns": int(meta.get("total_turns", 0) or 0),
    }


def discovered_index_entries(root: Path) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    try:
        session_paths = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError:
        return discovered
    for session_path in session_paths:
        if not session_path.is_dir() or session_path.name.startswith("."):
            continue
        meta_path = session_path / "meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(meta, dict):
            continue
        entry = index_entry_from_meta(meta)
        if entry is None or entry["session_id"] != session_path.name:
            continue
        discovered.append(entry)
    return discovered


def merged_index_sessions(raw_sessions: Any, root: Path) -> list[dict[str, Any]]:
    """Union the index file's rows with on-disk discovery, index order first."""

    sessions: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    if isinstance(raw_sessions, list):
        for raw_entry in raw_sessions:
            if not isinstance(raw_entry, dict):
                continue
            session_id = str(raw_entry.get("session_id", "") or "").strip()
            if not session_id or session_id in positions:
                continue
            positions[session_id] = len(sessions)
            sessions.append(dict(raw_entry))
    for discovered in discovered_index_entries(root):
        session_id = str(discovered["session_id"])
        position = positions.get(session_id)
        if position is None:
            positions[session_id] = len(sessions)
            sessions.append(discovered)
        else:
            sessions[position] = {**sessions[position], **discovered}
    return sessions


def upsert_index_sessions(
    raw_sessions: Any,
    *,
    session_id: str,
    updates: dict[str, Any],
    meta_loader: Any,
) -> list[dict[str, Any]]:
    sessions = [
        dict(entry)
        for entry in raw_sessions
        if isinstance(entry, dict)
        and str(entry.get("session_id", "") or "").strip()
    ] if isinstance(raw_sessions, list) else []
    found = False
    for entry in sessions:
        if entry.get("session_id") == session_id:
            entry.update(updates)
            found = True
            break
    if not found:
        try:
            meta_entry = index_entry_from_meta(meta_loader(session_id))
        except (OSError, ValueError, TypeError):
            meta_entry = None
        if meta_entry is not None:
            meta_entry.update(updates)
            sessions.append(meta_entry)
    return sessions


def latest_session_meta(
    entries: list[dict[str, Any]],
    *,
    meta_loader: Any,
    cwd: str | None = None,
    provider_id: str | None = None,
    min_turns: int | None = None,
) -> dict[str, Any] | None:
    latest_meta: dict[str, Any] | None = None
    latest_key = ""
    for entry in entries:
        sid = str(entry.get("session_id", "")).strip()
        if not sid:
            continue
        try:
            meta = meta_loader(sid)
        except Exception:
            continue
        if cwd and not cwd_matches(str(meta.get("cwd", "")), cwd):
            continue
        if provider_id and str(meta.get("provider_id", "")) != provider_id:
            continue
        if min_turns is not None:
            turns = int(meta.get("total_turns", 0) or 0)
            if turns < int(min_turns):
                continue
        updated = str(meta.get("updated_at", ""))
        created = str(meta.get("created_at", ""))
        key = updated or created
        if key and key > latest_key:
            latest_key = key
            latest_meta = meta
    return latest_meta


def snapshot_state(meta: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "snapshot_reason": reason,
        "session_id": str(meta.get("session_id", "")),
        "provider_id": str(meta.get("provider_id", "")),
        "model_id": str(meta.get("model_id", "")),
        "provider_session_id": str(meta.get("provider_session_id", "")),
        "cwd": str(meta.get("cwd", "")),
        "status": str(meta.get("status", "")),
        "total_turns": int(meta.get("total_turns", 0) or 0),
        "total_input_tokens": int(meta.get("total_input_tokens", 0) or 0),
        "total_output_tokens": int(meta.get("total_output_tokens", 0) or 0),
        "total_cost_usd": float(meta.get("total_cost_usd", 0.0) or 0.0),
        "updated_at": str(meta.get("updated_at", "")),
    }
