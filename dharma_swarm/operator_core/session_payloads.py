"""JSON-ready session payload builders for the shared operator core."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
from typing import Any

from dharma_swarm.tui.engine.events import EVENT_TYPES

from .adapters import event_envelope_from_legacy_event, session_from_meta
from .contracts import CanonicalEventEnvelope, CanonicalSession
from .permission_payloads import PERMISSION_PAYLOAD_VERSION, _permission_history_entries_for_session
from .session_store import SessionStore, cwd_matches

SESSION_PAYLOAD_VERSION = "v1"
SESSION_CATALOG_DOMAIN = "session_catalog"
SESSION_DETAIL_DOMAIN = "session_detail"


def transcript_integrity_issues(store: SessionStore, session_id: str) -> list[str]:
    """Validate transcript structure and terminal metadata consistency."""

    transcript_path = store.root / session_id / "transcript.jsonl"
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
            issues.append(f"event_{index}_session_mismatch:{event_session_id or 'missing'}")

    try:
        meta = store.load_meta(session_id)
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


def _string(value: Any) -> str:
    return str(value or "").strip()


def _session_payload(session: CanonicalSession) -> dict[str, Any]:
    return asdict(session)


def _event_payload(event: CanonicalEventEnvelope) -> dict[str, Any]:
    return asdict(event)


def _event_compaction_preview(events: list[Any]) -> dict[str, Any]:
    counts = Counter(getattr(event, "type", "unknown") for event in events)
    recent_event_types = [getattr(event, "type", "unknown") for event in events[-12:]]
    verbose_event_total = sum(counts.get(kind, 0) for kind in ("text_delta", "thinking_delta", "tool_args_delta"))
    compactable_ratio = (verbose_event_total / len(events)) if events else 0.0
    protected = [
        kind
        for kind in (
            "user_prompt",
            "session_start",
            "tool_call_complete",
            "tool_result",
            "usage",
            "session_end",
            "error",
        )
        if counts.get(kind, 0) > 0
    ]
    return {
        "event_count": len(events),
        "by_type": dict(counts),
        "compactable_ratio": round(compactable_ratio, 3),
        "protected_event_types": protected,
        "recent_event_types": recent_event_types,
    }


def build_session_catalog_payload(
    store: SessionStore,
    *,
    cwd: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Build a shell-neutral session catalog payload."""

    records: list[dict[str, Any]] = []
    total_count = 0
    page_limit = max(1, limit)
    for entry in reversed(store.list_sessions()):
        session_id = _string(entry.get("session_id"))
        if not session_id:
            continue
        try:
            meta = store.load_meta(session_id)
        except Exception:
            continue
        if cwd and not cwd_matches(str(meta.get("cwd", "")), cwd):
            continue
        total_count += 1
        if len(records) >= page_limit:
            continue
        replay_ok, replay_issues = store.verify_session_replay(session_id)
        records.append(
            {
                "session": _session_payload(session_from_meta(meta)),
                "replay_ok": replay_ok,
                "replay_issues": list(replay_issues),
                "total_turns": int(meta.get("total_turns", 0) or 0),
                "total_cost_usd": float(meta.get("total_cost_usd", 0.0) or 0.0),
            }
        )

    return {
        "version": SESSION_PAYLOAD_VERSION,
        "domain": SESSION_CATALOG_DOMAIN,
        "count": total_count,
        "returned_count": len(records),
        "limit": page_limit,
        "has_more": total_count > len(records),
        "sessions": records,
    }


def build_session_detail_payload(
    store: SessionStore,
    session_id: str,
    *,
    transcript_limit: int = 80,
) -> dict[str, Any]:
    """Build a shell-neutral session detail payload."""

    meta = store.load_meta(session_id)
    events = store.load_transcript(session_id, limit=transcript_limit)
    replay_ok, replay_issues = store.verify_session_replay(session_id)
    envelopes = [event_envelope_from_legacy_event(event) for event in events]
    session_permission_entries = _permission_history_entries_for_session(store, session_id)
    return {
        "version": SESSION_PAYLOAD_VERSION,
        "domain": SESSION_DETAIL_DOMAIN,
        "session": _session_payload(session_from_meta(meta)),
        "replay_ok": replay_ok,
        "replay_issues": list(replay_issues),
        "compaction_preview": _event_compaction_preview(events),
        "recent_events": [_event_payload(envelope) for envelope in envelopes],
        "approval_history": {
            "version": PERMISSION_PAYLOAD_VERSION,
            "domain": "permission_history",
            "count": len(session_permission_entries),
            "entries": session_permission_entries,
        },
    }
