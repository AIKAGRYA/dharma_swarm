"""Canonical session persistence for the shared operator core."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import logging
import os
import secrets
import subprocess
import threading
from pathlib import Path
from typing import Any

from dharma_swarm.continuity_harness import append_snapshot, verify_replay_integrity
from dharma_swarm.session_event_bridge import SessionEventBridge
from dharma_swarm.tui.engine.events import (
    CanonicalEvent,
    CanonicalEventType,
    ContextReceipt,
    EVENT_TYPES,
)

HOME = Path.home()
DEFAULT_ROOT = HOME / ".dharma" / "sessions"
LEGACY_OWNER_GRACE_SECONDS = 300.0
logger = logging.getLogger(__name__)

_SESSION_RECOVERY_LOCKS: dict[Path, threading.RLock] = {}
_SESSION_RECOVERY_LOCKS_GUARD = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session_id() -> str:
    now = datetime.now(timezone.utc)
    return f"dgc-{now:%Y%m%d}-{now:%H%M%S}-{secrets.token_hex(2)}"


def _session_recovery_thread_lock(path: Path) -> threading.RLock:
    """Return the shared in-process half of a session recovery lock."""

    key = path.resolve()
    with _SESSION_RECOVERY_LOCKS_GUARD:
        return _SESSION_RECOVERY_LOCKS.setdefault(key, threading.RLock())


def _pid_is_alive(pid: int) -> bool:
    """Compatibility seam used by recovery tests and runtime injection."""

    from .session_lifecycle import _pid_is_alive as check_pid

    return check_pid(pid)


def _normalize_cwd(cwd: str) -> str:
    try:
        return str(Path(cwd).expanduser().resolve())
    except Exception:
        return str(Path(cwd).expanduser())


def cwd_matches(meta_cwd: str, expected_cwd: str) -> bool:
    if meta_cwd == expected_cwd:
        return True
    return _normalize_cwd(meta_cwd) == _normalize_cwd(expected_cwd)


def _observe_git_branch(cwd: str) -> str:
    """Sample the branch at session creation without making Git authoritative."""

    normalized_cwd = _normalize_cwd(cwd)
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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
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


class SessionStore:
    """Stores canonical event transcripts and session metadata."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._bridges: dict[str, SessionEventBridge] = {}
        self._last_snapshot_failure: tuple[str, str, str] | None = None
        if not self._index_path.exists():
            _atomic_write_json(
                self._index_path,
                {"schema_version": 1, "sessions": []},
            )

    def create_session(
        self,
        *,
        provider_id: str,
        model_id: str,
        cwd: str,
        title: str | None = None,
        provider_session_id: str | None = None,
        parent_session_id: str | None = None,
        forked_from: str | None = None,
        session_id: str | None = None,
        runtime_owner_id: str | None = None,
        runtime_owner_pid: int | None = None,
    ) -> str:
        sid = session_id or _new_session_id()
        sp = self.root / sid
        sp.mkdir(parents=True, exist_ok=True)

        meta = {
            "schema_version": 1,
            "session_id": sid,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "provider_id": provider_id,
            "model_id": model_id,
            "provider_session_id": provider_session_id,
            "title": title or "",
            "cwd": cwd,
            "git_branch": _observe_git_branch(cwd),
            "tags": [],
            "total_cost_usd": 0.0,
            "total_turns": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "capabilities_used": [],
            "status": "running",
            "parent_session_id": parent_session_id,
            "forked_from": forked_from,
            "runtime_owner_id": str(runtime_owner_id or "").strip() or None,
            "runtime_owner_pid": (
                int(runtime_owner_pid)
                if runtime_owner_pid is not None and int(runtime_owner_pid) > 0
                else None
            ),
        }
        self._write_meta(sid, meta)
        (sp / "transcript.jsonl").touch(exist_ok=True)
        (sp / "audit.jsonl").touch(exist_ok=True)
        (sp / "runtime.jsonl").touch(exist_ok=True)
        (sp / "snapshots.jsonl").touch(exist_ok=True)

        index = self._read_index()
        sessions = [
            entry
            for entry in self._merged_index_sessions()
            if entry.get("session_id") != sid
        ]
        sessions.append(
            {
                "session_id": sid,
                "title": meta["title"],
                "provider_id": provider_id,
                "model_id": model_id,
                "created_at": meta["created_at"],
                "updated_at": meta["updated_at"],
                "status": "running",
                "total_cost_usd": 0.0,
                "total_turns": 0,
            }
        )
        index["sessions"] = sessions
        try:
            self._write_index(index)
        except OSError as exc:
            logger.warning("session index write failed for %s (%s)", sid, type(exc).__name__)
        try:
            self._bridge_for(sid).session_start(
                sid,
                {
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "cwd": cwd,
                    "title": meta["title"],
                    "provider_session_id": provider_session_id or "",
                },
            )
            self._append_session_snapshot(sid, reason="session_created", meta=meta)
        except Exception:
            pass
        return sid

    def append_event(self, session_id: str, event: CanonicalEvent, *, strip_raw: bool = True) -> None:
        payload = asdict(event)
        if strip_raw:
            payload["raw"] = None
        tp = self.root / session_id / "transcript.jsonl"
        encoded = (json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8")
        with open(tp, "a+b") as handle:
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
        try:
            self._bridge_for(session_id).record_canonical_event(event)
        except Exception:
            pass
        self._touch_session(session_id)

    def load_transcript(
        self,
        session_id: str,
        *,
        include_types: set[str] | None = None,
        limit: int | None = None,
    ) -> list[CanonicalEventType]:
        tp = self.root / session_id / "transcript.jsonl"
        if not tp.exists():
            return []

        events: list[CanonicalEventType] = []
        for raw_line in tp.read_text(encoding="utf-8").splitlines():
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

    def append_audit(self, session_id: str, entry: dict[str, Any]) -> None:
        ap = self.root / session_id / "audit.jsonl"
        payload = dict(entry)
        payload.setdefault("timestamp", datetime.now(timezone.utc).timestamp())
        payload.setdefault("created_at", _now_iso())
        payload.setdefault("session_id", session_id)
        with open(ap, "a") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        self._touch_session(session_id)

    def load_audit(
        self,
        session_id: str,
        *,
        include_domains: set[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        ap = self.root / session_id / "audit.jsonl"
        if not ap.exists():
            return []

        entries: list[dict[str, Any]] = []
        for raw_line in ap.read_text(encoding="utf-8").splitlines():
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

    def prune_audit_domains(self, session_id: str, *, domains: set[str]) -> int:
        ap = self.root / session_id / "audit.jsonl"
        if not ap.exists():
            return 0

        kept_lines: list[str] = []
        removed = 0
        for raw_line in ap.read_text(encoding="utf-8").splitlines():
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

        with open(ap, "w", encoding="utf-8") as handle:
            for kept_line in kept_lines:
                handle.write(kept_line.rstrip("\n") + "\n")
        return removed

    def finalize_session(
        self,
        session_id: str,
        *,
        status: str,
        total_cost_usd: float | None = None,
        total_turns: int | None = None,
        total_input_tokens: int | None = None,
        total_output_tokens: int | None = None,
        provider_session_id: str | None = None,
    ) -> None:
        meta = self.load_meta(session_id)
        meta.pop("pending_context_receipt", None)
        meta["updated_at"] = _now_iso()
        meta["status"] = status
        if total_cost_usd is not None:
            meta["total_cost_usd"] = float(total_cost_usd)
        if total_turns is not None:
            meta["total_turns"] = int(total_turns)
        if total_input_tokens is not None:
            meta["total_input_tokens"] = int(total_input_tokens)
        if total_output_tokens is not None:
            meta["total_output_tokens"] = int(total_output_tokens)
        if provider_session_id:
            meta["provider_session_id"] = provider_session_id
        self._write_meta(session_id, meta)
        self._upsert_index_entry(
            session_id,
            {
                "updated_at": meta["updated_at"],
                "status": status,
                "total_cost_usd": meta.get("total_cost_usd", 0.0),
                "total_turns": meta.get("total_turns", 0),
            },
        )
        try:
            self._bridge_for(session_id).session_end(
                session_id,
                outcome=status,
                summary=f"status={status}; turns={meta.get('total_turns', 0)}; cost={meta.get('total_cost_usd', 0.0)}",
            )
            self._append_session_snapshot(session_id, reason="session_finalized", meta=meta)
        except Exception:
            pass

    def recover_orphaned_sessions(
        self,
        *,
        cwd: str,
        active_owner_id: str,
        active_owner_pid: int,
        legacy_owner_grace_seconds: float = LEGACY_OWNER_GRACE_SECONDS,
        now: datetime | None = None,
    ) -> list[str]:
        """Finalize durable turns abandoned by an earlier terminal bridge."""

        # Imported lazily to keep the store/lifecycle dependency acyclic while
        # preserving this long-standing public SessionStore entry point.
        from .session_lifecycle import recover_orphaned_sessions

        return recover_orphaned_sessions(
            self,
            cwd=cwd,
            active_owner_id=active_owner_id,
            active_owner_pid=active_owner_pid,
            legacy_owner_grace_seconds=legacy_owner_grace_seconds,
            now=now,
            pid_is_alive=_pid_is_alive,
        )

    @contextmanager
    def session_recovery_lock(self, session_id: str) -> Iterator[None]:
        """Serialize one orphan-recovery decision across stores and processes.

        The retained sidecar keeps a stable inode for the host-local advisory
        lock. ``flock`` alone does not serialize independent store instances in
        every same-process runtime, so a shared thread lock protects that case.
        """

        lock_path = self.root / session_id / ".recovery.lock"
        with _session_recovery_thread_lock(lock_path):
            with lock_path.open("a+b") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def load_meta(self, session_id: str) -> dict[str, Any]:
        return json.loads((self.root / session_id / "meta.json").read_text())

    def set_provider_session_id(self, session_id: str, provider_session_id: str) -> None:
        meta = self.load_meta(session_id)
        meta["provider_session_id"] = provider_session_id
        meta["updated_at"] = _now_iso()
        self._write_meta(session_id, meta)
        self._upsert_index_entry(session_id, {"updated_at": meta["updated_at"]})
        try:
            self._append_session_snapshot(session_id, reason="provider_session_bound", meta=meta)
        except Exception:
            pass

    def update_session_route(self, session_id: str, *, provider_id: str, model_id: str) -> None:
        """Rebind provisional session metadata to the route that actually ran."""

        meta = self.load_meta(session_id)
        meta["provider_id"] = provider_id
        meta["model_id"] = model_id
        meta["updated_at"] = _now_iso()
        self._write_meta(session_id, meta)
        self._upsert_index_entry(
            session_id,
            {
                "provider_id": provider_id,
                "model_id": model_id,
                "updated_at": meta["updated_at"],
            },
        )
        try:
            self._append_session_snapshot(session_id, reason="route_rebound", meta=meta)
        except Exception as exc:
            # Metadata and the index are already durable at this boundary. A
            # missing continuity snapshot must be visible without turning a
            # successful provider fallback into an in-memory/durable split.
            self._last_snapshot_failure = (
                session_id,
                "route_rebound",
                type(exc).__name__,
            )
            logger.warning(
                "session route rebound snapshot failed for %s (%s)",
                session_id,
                type(exc).__name__,
            )

    def stage_context_receipt(
        self,
        session_id: str,
        receipt: ContextReceipt,
    ) -> None:
        """Durably stage a context boundary before provider work begins."""

        if receipt.lane_outcome != "pending":
            raise ValueError("only a pending context receipt may be staged")
        payload = asdict(receipt)
        payload["raw"] = None
        meta = self.load_meta(session_id)
        meta["pending_context_receipt"] = payload
        meta["updated_at"] = _now_iso()
        self._write_meta(session_id, meta)
        self._upsert_index_entry(session_id, {"updated_at": meta["updated_at"]})

    def load_staged_context_receipt(
        self,
        session_id: str,
    ) -> ContextReceipt | None:
        payload = self.load_meta(session_id).get("pending_context_receipt")
        if not isinstance(payload, dict):
            return None
        try:
            receipt = ContextReceipt(**payload)
        except (TypeError, ValueError):
            return None
        if (
            receipt.lane_outcome != "pending"
            or not receipt.provider_id.strip()
            or not receipt.model_id.strip()
            or receipt.boundary_timestamp <= 0
        ):
            return None
        return receipt

    def clear_staged_context_receipt(self, session_id: str) -> bool:
        meta = self.load_meta(session_id)
        if "pending_context_receipt" not in meta:
            return False
        del meta["pending_context_receipt"]
        meta["updated_at"] = _now_iso()
        self._write_meta(session_id, meta)
        self._upsert_index_entry(session_id, {"updated_at": meta["updated_at"]})
        return True

    def _touch_session(self, session_id: str) -> None:
        meta = self.load_meta(session_id)
        meta["updated_at"] = _now_iso()
        self._write_meta(session_id, meta)
        self._upsert_index_entry(session_id, {"updated_at": meta["updated_at"]})

    def _write_meta(self, session_id: str, meta: dict[str, Any]) -> None:
        _atomic_write_json(self.root / session_id / "meta.json", meta)

    def _read_index(self) -> dict[str, Any]:
        try:
            return json.loads(self._index_path.read_text())
        except Exception:
            return {"schema_version": 1, "sessions": []}

    def _write_index(self, index: dict[str, Any]) -> None:
        _atomic_write_json(self._index_path, index)

    @staticmethod
    def _index_entry_from_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
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

    def _discovered_index_entries(self) -> list[dict[str, Any]]:
        discovered: list[dict[str, Any]] = []
        try:
            session_paths = sorted(self.root.iterdir(), key=lambda path: path.name)
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
            entry = self._index_entry_from_meta(meta)
            if entry is None or entry["session_id"] != session_path.name:
                continue
            discovered.append(entry)
        return discovered

    def _merged_index_sessions(self) -> list[dict[str, Any]]:
        raw_sessions = self._read_index().get("sessions", [])
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
        for discovered in self._discovered_index_entries():
            session_id = str(discovered["session_id"])
            position = positions.get(session_id)
            if position is None:
                positions[session_id] = len(sessions)
                sessions.append(discovered)
            else:
                sessions[position] = {**sessions[position], **discovered}
        return sessions

    def _upsert_index_entry(self, session_id: str, updates: dict[str, Any]) -> None:
        index = self._read_index()
        raw_sessions = index.get("sessions", [])
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
                meta_entry = self._index_entry_from_meta(self.load_meta(session_id))
            except (OSError, ValueError, TypeError):
                meta_entry = None
            if meta_entry is not None:
                meta_entry.update(updates)
                sessions.append(meta_entry)
        index["sessions"] = sessions
        try:
            self._write_index(index)
        except OSError as exc:
            logger.warning(
                "session index update failed for %s (%s)",
                session_id,
                type(exc).__name__,
            )

    def list_sessions(self) -> list[dict[str, Any]]:
        return self._merged_index_sessions()

    def latest_session(
        self,
        *,
        cwd: str | None = None,
        provider_id: str | None = None,
        min_turns: int | None = None,
    ) -> dict[str, Any] | None:
        latest_meta: dict[str, Any] | None = None
        latest_key = ""
        for entry in self.list_sessions():
            sid = str(entry.get("session_id", "")).strip()
            if not sid:
                continue
            try:
                meta = self.load_meta(sid)
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

    def verify_session_replay(self, session_id: str) -> tuple[bool, list[str]]:
        snapshot_ok, snapshot_issues = verify_replay_integrity(
            self.root / session_id / "snapshots.jsonl"
        )
        transcript_issues = self._transcript_integrity_issues(session_id)
        issues = [*snapshot_issues, *transcript_issues]
        return snapshot_ok and not transcript_issues, issues

    def _transcript_integrity_issues(self, session_id: str) -> list[str]:
        """Validate replay semantics, not only snapshot checksums."""

        from .session_payloads import transcript_integrity_issues

        return transcript_integrity_issues(self, session_id)

    def _bridge_for(self, session_id: str) -> SessionEventBridge:
        bridge = self._bridges.get(session_id)
        if bridge is not None:
            return bridge
        bridge = SessionEventBridge(runtime_log_path=self.root / session_id / "runtime.jsonl")
        self._bridges[session_id] = bridge
        return bridge

    def _append_session_snapshot(self, session_id: str, *, reason: str, meta: dict[str, Any] | None = None) -> None:
        state = self._snapshot_state(meta or self.load_meta(session_id), reason=reason)
        append_snapshot(self.root / session_id / "snapshots.jsonl", state)

    @staticmethod
    def _snapshot_state(meta: dict[str, Any], *, reason: str) -> dict[str, Any]:
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
