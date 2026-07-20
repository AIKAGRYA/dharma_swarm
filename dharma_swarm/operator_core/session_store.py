"""Canonical session persistence for the shared operator core."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
import secrets
from pathlib import Path
from typing import Any

from dharma_swarm.continuity_harness import append_snapshot, verify_replay_integrity
from dharma_swarm.session_event_bridge import SessionEventBridge
from dharma_swarm.tui.engine.events import (
    CanonicalEvent,
    CanonicalEventType,
    EVENT_TYPES,
    SessionEnd,
)

HOME = Path.home()
DEFAULT_ROOT = HOME / ".dharma" / "sessions"
TERMINAL_SESSION_STATUSES = frozenset({"completed", "failed", "cancelled"})
LEGACY_OWNER_GRACE_SECONDS = 300.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session_id() -> str:
    now = datetime.now(timezone.utc)
    return f"dgc-{now:%Y%m%d}-{now:%H%M%S}-{secrets.token_hex(2)}"


def _parse_iso_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _normalize_cwd(cwd: str) -> str:
    try:
        return str(Path(cwd).expanduser().resolve())
    except Exception:
        return str(Path(cwd).expanduser())


def cwd_matches(meta_cwd: str, expected_cwd: str) -> bool:
    if meta_cwd == expected_cwd:
        return True
    return _normalize_cwd(meta_cwd) == _normalize_cwd(expected_cwd)


class SessionStore:
    """Stores canonical event transcripts and session metadata."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "index.json"
        self._bridges: dict[str, SessionEventBridge] = {}
        if not self._index_path.exists():
            self._index_path.write_text(json.dumps({"schema_version": 1, "sessions": []}))

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
            "git_branch": "",
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
        (sp / "meta.json").write_text(json.dumps(meta, indent=2))
        (sp / "transcript.jsonl").touch(exist_ok=True)
        (sp / "audit.jsonl").touch(exist_ok=True)
        (sp / "runtime.jsonl").touch(exist_ok=True)
        (sp / "snapshots.jsonl").touch(exist_ok=True)

        index = self._read_index()
        sessions = index.get("sessions", [])
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
        self._write_index(index)
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
        with open(tp, "a") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
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
        """Finalize durable turns abandoned by an earlier terminal bridge.

        New terminal turns carry a bridge instance ID and PID.  A turn owned by
        another live PID is left alone, which permits independent Helm
        processes in the same workspace.  Ownerless rows predate this lease
        metadata and are recovered only after a grace window.

        Recovery appends an unsuccessful terminal event before updating
        metadata.  If a process died between those writes, a later recovery
        reuses the real terminal event rather than appending a duplicate.
        """

        owner_id = active_owner_id.strip()
        if not owner_id:
            raise ValueError("active_owner_id must not be empty")
        if active_owner_pid <= 0:
            raise ValueError("active_owner_pid must be positive")

        recovered: list[str] = []
        observed_at = now or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        grace = timedelta(seconds=max(0.0, float(legacy_owner_grace_seconds)))

        for entry in list(self.list_sessions()):
            session_id = str(entry.get("session_id", "") or "").strip()
            if not session_id:
                continue
            try:
                meta = self.load_meta(session_id)
            except Exception:
                continue
            status = str(meta.get("status", "") or "").strip().lower()
            if status in TERMINAL_SESSION_STATUSES:
                continue
            if not cwd_matches(str(meta.get("cwd", "") or ""), cwd):
                continue
            if not self._owner_is_orphaned(
                meta,
                active_owner_id=owner_id,
                active_owner_pid=active_owner_pid,
                observed_at=observed_at,
                legacy_owner_grace=grace,
            ):
                continue

            transcript = self.load_transcript(session_id)
            terminal_events = [event for event in transcript if event.type == "session_end"]
            if terminal_events:
                terminal = terminal_events[-1]
                error_code = str(getattr(terminal, "error_code", "") or "").strip().lower()
                terminal_status = (
                    "cancelled"
                    if error_code == "cancelled"
                    else "completed"
                    if bool(getattr(terminal, "success", False))
                    else "failed"
                )
            else:
                terminal = SessionEnd(
                    provider_id=str(meta.get("provider_id", "") or ""),
                    session_id=session_id,
                    success=False,
                    error_code="bridge_interrupted",
                    error_message=(
                        "previous terminal bridge process ended before session finalization"
                    ),
                )
                self.append_event(session_id, terminal)
                terminal_status = "failed"

            self.finalize_session(
                session_id,
                status=terminal_status,
                total_cost_usd=float(meta.get("total_cost_usd", 0.0) or 0.0),
                total_turns=int(meta.get("total_turns", 0) or 0),
                total_input_tokens=int(meta.get("total_input_tokens", 0) or 0),
                total_output_tokens=int(meta.get("total_output_tokens", 0) or 0),
                provider_session_id=(
                    str(meta.get("provider_session_id", "") or "").strip() or None
                ),
            )
            recovered.append(session_id)

        return recovered

    @staticmethod
    def _owner_is_orphaned(
        meta: dict[str, Any],
        *,
        active_owner_id: str,
        active_owner_pid: int,
        observed_at: datetime,
        legacy_owner_grace: timedelta,
    ) -> bool:
        owner_id = str(meta.get("runtime_owner_id", "") or "").strip()
        try:
            owner_pid = int(meta.get("runtime_owner_pid", 0) or 0)
        except (TypeError, ValueError):
            owner_pid = 0

        if owner_id == active_owner_id and owner_pid == active_owner_pid:
            return False
        if owner_pid > 0 and owner_pid != active_owner_pid and _pid_is_alive(owner_pid):
            return False
        if owner_id or owner_pid > 0:
            return True

        updated_at = _parse_iso_datetime(meta.get("updated_at"))
        if updated_at is None:
            return True
        return observed_at - updated_at >= legacy_owner_grace

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
        except Exception:
            pass

    def _touch_session(self, session_id: str) -> None:
        meta = self.load_meta(session_id)
        meta["updated_at"] = _now_iso()
        self._write_meta(session_id, meta)
        self._upsert_index_entry(session_id, {"updated_at": meta["updated_at"]})

    def _write_meta(self, session_id: str, meta: dict[str, Any]) -> None:
        (self.root / session_id / "meta.json").write_text(json.dumps(meta, indent=2))

    def _read_index(self) -> dict[str, Any]:
        try:
            return json.loads(self._index_path.read_text())
        except Exception:
            return {"schema_version": 1, "sessions": []}

    def _write_index(self, index: dict[str, Any]) -> None:
        self._index_path.write_text(json.dumps(index, indent=2))

    def _upsert_index_entry(self, session_id: str, updates: dict[str, Any]) -> None:
        index = self._read_index()
        sessions = index.get("sessions", [])
        for entry in sessions:
            if entry.get("session_id") == session_id:
                entry.update(updates)
                break
        index["sessions"] = sessions
        self._write_index(index)

    def list_sessions(self) -> list[dict[str, Any]]:
        index = self._read_index()
        sessions = index.get("sessions", [])
        return sessions if isinstance(sessions, list) else []

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

        transcript_path = self.root / session_id / "transcript.jsonl"
        if not transcript_path.exists():
            return ["transcript_missing"]

        decoded: list[dict[str, Any]] = []
        issues: list[str] = []
        for line_number, raw_line in enumerate(
            transcript_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                issues.append(f"transcript_line_{line_number}_invalid_json")
                continue
            if not isinstance(payload, dict):
                issues.append(f"transcript_line_{line_number}_not_object")
                continue
            event_type = str(payload.get("type", "") or "").strip()
            event_cls = EVENT_TYPES.get(event_type)
            if event_cls is None:
                issues.append(
                    f"transcript_line_{line_number}_unknown_event:{event_type or 'missing'}"
                )
                continue
            try:
                event_cls(**payload)
            except Exception:
                issues.append(f"transcript_line_{line_number}_invalid_event:{event_type}")
                continue
            decoded.append(payload)

        if not decoded:
            issues.append("transcript_empty")
            return issues

        event_types = [str(payload.get("type", "")) for payload in decoded]
        start_count = event_types.count("session_start")
        if start_count != 1:
            issues.append(f"session_start_count:{start_count}")
        if "user_prompt" not in event_types:
            issues.append("user_prompt_missing")

        terminals = [
            payload for payload in decoded if str(payload.get("type", "")) == "session_end"
        ]
        if len(terminals) != 1:
            issues.append(f"session_end_count:{len(terminals)}")

        for index, payload in enumerate(decoded, start=1):
            event_session_id = str(payload.get("session_id", "") or "").strip()
            if event_session_id != session_id:
                issues.append(
                    f"event_{index}_session_mismatch:{event_session_id or 'missing'}"
                )

        try:
            meta = self.load_meta(session_id)
        except Exception:
            issues.append("session_meta_unreadable")
            return issues

        if len(terminals) == 1:
            terminal = terminals[0]
            error_code = str(terminal.get("error_code", "") or "").strip().lower()
            expected_status = (
                "cancelled"
                if error_code == "cancelled"
                else "completed"
                if terminal.get("success") is True
                else "failed"
            )
            actual_status = str(meta.get("status", "") or "").strip().lower()
            if actual_status != expected_status:
                issues.append(
                    f"metadata_status_mismatch:{actual_status or 'missing'}!={expected_status}"
                )

        return issues

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
