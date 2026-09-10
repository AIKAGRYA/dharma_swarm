"""Canonical session persistence for the shared operator core.

# closure-layer-role: canonical-store — SessionStore owns the durable session
# transcript/audit/meta layout under ~/.dharma/sessions (state_dir.sessions in
# ACTIVE_SURFACE_MANIFEST.yaml); physical I/O lives in session_store_fs.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from dharma_swarm.continuity_harness import append_snapshot, verify_replay_integrity
from dharma_swarm.session_event_bridge import SessionEventBridge
from dharma_swarm.tui.engine.events import (
    CanonicalEvent,
    CanonicalEventType,
    ContextReceipt,
)

from . import session_store_fs as _fs
from .session_store_fs import cwd_matches

__all__ = ["SessionStore", "cwd_matches"]

HOME = Path.home()
DEFAULT_ROOT = HOME / ".dharma" / "sessions"
LEGACY_OWNER_GRACE_SECONDS = 300.0
logger = logging.getLogger(__name__)

_now_iso = _fs.now_iso
_new_session_id = _fs.new_session_id
_atomic_write_json = _fs.atomic_write_json


def _pid_is_alive(pid: int) -> bool:
    """Compatibility seam used by recovery tests and runtime injection."""

    from .session_recovery import _pid_is_alive as check_pid

    return check_pid(pid)


def _observe_git_branch(cwd: str) -> str:
    """Compatibility seam kept for tests that stub branch observation."""

    return _fs.observe_git_branch(cwd)


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
        _fs.append_jsonl_record(tp, encoded)
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
        return _fs.read_transcript_events(tp, include_types=include_types, limit=limit)

    def append_audit(self, session_id: str, entry: dict[str, Any]) -> None:
        ap = self.root / session_id / "audit.jsonl"
        payload = dict(entry)
        payload.setdefault("timestamp", datetime.now(timezone.utc).timestamp())
        payload.setdefault("created_at", _now_iso())
        payload.setdefault("session_id", session_id)
        _fs.append_jsonl_line(ap, payload)
        self._touch_session(session_id)

    def load_audit(
        self,
        session_id: str,
        *,
        include_domains: set[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        ap = self.root / session_id / "audit.jsonl"
        return _fs.read_audit_entries(ap, include_domains=include_domains, limit=limit)

    def prune_audit_domains(self, session_id: str, *, domains: set[str]) -> int:
        ap = self.root / session_id / "audit.jsonl"
        return _fs.prune_audit_domains(ap, domains=domains)

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
        from .session_recovery import recover_orphaned_sessions

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
        with _fs.session_recovery_file_lock(lock_path):
            yield

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
        return _fs.index_entry_from_meta(meta)

    def _discovered_index_entries(self) -> list[dict[str, Any]]:
        return _fs.discovered_index_entries(self.root)

    def _merged_index_sessions(self) -> list[dict[str, Any]]:
        return _fs.merged_index_sessions(self._read_index().get("sessions", []), self.root)

    def _upsert_index_entry(self, session_id: str, updates: dict[str, Any]) -> None:
        index = self._read_index()
        index["sessions"] = _fs.upsert_index_sessions(
            index.get("sessions", []),
            session_id=session_id,
            updates=updates,
            meta_loader=self.load_meta,
        )
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
        return _fs.latest_session_meta(
            self.list_sessions(),
            meta_loader=self.load_meta,
            cwd=cwd,
            provider_id=provider_id,
            min_turns=min_turns,
        )

    def verify_session_replay(self, session_id: str) -> tuple[bool, list[str]]:
        snapshot_ok, snapshot_issues = verify_replay_integrity(
            self.root / session_id / "snapshots.jsonl"
        )
        transcript_issues = self._transcript_integrity_issues(session_id)
        issues = [*snapshot_issues, *transcript_issues]
        replay_ok = snapshot_ok and not transcript_issues
        if replay_ok and not self._transcript_has_context_receipt(session_id):
            # Pre-receipt-era transcripts stay replayable but are typed as
            # unproven: no ContextReceipt exists to validate against, and no
            # validity is grandfathered or backfilled.
            issues.append("replay_unproven_pre_receipt_era")
        return replay_ok, issues

    def _transcript_has_context_receipt(self, session_id: str) -> bool:
        try:
            return any(
                getattr(event, "type", "") == "context_receipt"
                for event in self.load_transcript(session_id)
            )
        except Exception:
            return False

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
        return _fs.snapshot_state(meta, reason=reason)
