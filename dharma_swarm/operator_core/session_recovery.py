"""Orphaned-session recovery for the shared operator core.

Extracted from ``session_lifecycle`` so the recorder module stays focused on
one turn's durable boundary while this module owns cross-process recovery.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Callable

from dharma_swarm.tui.engine.events import ContextReceipt, SessionEnd

from .session_lifecycle import TERMINAL_SESSION_STATUSES
from .session_store import SessionStore, cwd_matches


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


def _owner_is_orphaned(
    meta: dict[str, Any],
    *,
    active_owner_id: str,
    active_owner_pid: int,
    observed_at: datetime,
    legacy_owner_grace: timedelta,
    pid_is_alive: Callable[[int], bool],
) -> bool:
    owner_id = str(meta.get("runtime_owner_id", "") or "").strip()
    try:
        owner_pid = int(meta.get("runtime_owner_pid", 0) or 0)
    except (TypeError, ValueError):
        owner_pid = 0

    if owner_id == active_owner_id and owner_pid == active_owner_pid:
        return False
    if owner_pid > 0 and owner_pid != active_owner_pid and pid_is_alive(owner_pid):
        return False
    if owner_id or owner_pid > 0:
        return True

    updated_at = _parse_iso_datetime(meta.get("updated_at"))
    if updated_at is None:
        return True
    return observed_at - updated_at >= legacy_owner_grace


def _session_needs_orphan_recovery(
    meta: dict[str, Any],
    *,
    cwd: str,
    active_owner_id: str,
    active_owner_pid: int,
    observed_at: datetime,
    legacy_owner_grace: timedelta,
    pid_is_alive: Callable[[int], bool],
) -> bool:
    status = str(meta.get("status", "") or "").strip().lower()
    return (
        status not in TERMINAL_SESSION_STATUSES
        and cwd_matches(str(meta.get("cwd", "") or ""), cwd)
        and _owner_is_orphaned(
            meta,
            active_owner_id=active_owner_id,
            active_owner_pid=active_owner_pid,
            observed_at=observed_at,
            legacy_owner_grace=legacy_owner_grace,
            pid_is_alive=pid_is_alive,
        )
    )


def recover_orphaned_sessions(
    store: SessionStore,
    *,
    cwd: str,
    active_owner_id: str,
    active_owner_pid: int,
    legacy_owner_grace_seconds: float,
    now: datetime | None = None,
    pid_is_alive: Callable[[int], bool] = _pid_is_alive,
) -> list[str]:
    """Finalize durable turns abandoned by an earlier terminal bridge.

    Turns owned by another live PID remain untouched. Ownerless legacy rows
    are recovered only after the caller-provided grace window. A real terminal
    event is reused when present so recovery stays idempotent.
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

    for entry in list(store.list_sessions()):
        session_id = str(entry.get("session_id", "") or "").strip()
        if not session_id:
            continue
        try:
            meta = store.load_meta(session_id)
        except Exception:
            continue
        if not _session_needs_orphan_recovery(
            meta,
            cwd=cwd,
            active_owner_id=owner_id,
            active_owner_pid=active_owner_pid,
            observed_at=observed_at,
            legacy_owner_grace=grace,
            pid_is_alive=pid_is_alive,
        ):
            continue

        with store.session_recovery_lock(session_id):
            # Candidate discovery above is intentionally optimistic. Another
            # bridge may have recovered this session while this contender was
            # waiting for the host-local lock, so decide again under the lock.
            try:
                meta = store.load_meta(session_id)
            except Exception:
                continue
            if not _session_needs_orphan_recovery(
                meta,
                cwd=cwd,
                active_owner_id=owner_id,
                active_owner_pid=active_owner_pid,
                observed_at=observed_at,
                legacy_owner_grace=grace,
                pid_is_alive=pid_is_alive,
            ):
                continue

            transcript = store.load_transcript(session_id)
            terminal_events = [
                event for event in transcript if event.type == "session_end"
            ]
            context_receipts = [
                event for event in transcript if isinstance(event, ContextReceipt)
            ]
            staged_context = store.load_staged_context_receipt(session_id)
            if staged_context is not None:
                if not context_receipts and not terminal_events:
                    store.update_session_route(
                        session_id,
                        provider_id=staged_context.provider_id,
                        model_id=staged_context.model_id,
                    )
                    interrupted_context = replace(
                        staged_context,
                        outcome_timestamp=observed_at.timestamp(),
                        lane_outcome="interrupted",
                    )
                    store.append_event(session_id, interrupted_context)
                    context_receipts.append(interrupted_context)
                store.clear_staged_context_receipt(session_id)
                meta = store.load_meta(session_id)
            if terminal_events:
                terminal = terminal_events[-1]
                error_code = str(
                    getattr(terminal, "error_code", "") or ""
                ).strip().lower()
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
                store.append_event(session_id, terminal)
                terminal_status = "failed"

            store.finalize_session(
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
