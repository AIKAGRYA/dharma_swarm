"""Headless persistence state machine for one canonical operator turn.

The transport owns acknowledgements and provider cancellation.  This recorder
owns the durable boundary around those operations: callers create it before
emitting an acknowledgement, then pass only operator-visible canonical events
through :meth:`record`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import os
from threading import RLock
from typing import Any, Callable, cast

from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
    UserPrompt,
)

from .session_store import SessionStore, cwd_matches

TERMINAL_SESSION_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class SessionUsage:
    """Usage accumulated across every report emitted for the turn."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_tokens: int = 0
    total_cost_usd: float | None = None


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
        status = str(meta.get("status", "") or "").strip().lower()
        if status in TERMINAL_SESSION_STATUSES:
            continue
        if not cwd_matches(str(meta.get("cwd", "") or ""), cwd):
            continue
        if not _owner_is_orphaned(
            meta,
            active_owner_id=owner_id,
            active_owner_pid=active_owner_pid,
            observed_at=observed_at,
            legacy_owner_grace=grace,
            pid_is_alive=pid_is_alive,
        ):
            continue

        transcript = store.load_transcript(session_id)
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


class SessionLifecycleRecorder:
    """Persist one canonical session turn and finalize it exactly once.

    ``parent_session_id`` in :meth:`begin` is canonical SessionStore lineage.
    Provider-native resume identifiers deliberately have no constructor
    parameter; they enter this boundary only through a real ``SessionStart``.
    """

    def __init__(
        self,
        *,
        store: SessionStore,
        session_id: str,
        provider_id: str,
        model_id: str,
    ) -> None:
        self._store = store
        self._session_id = session_id
        self._provider_id = provider_id
        self._model_id = model_id
        self._provider_session_id: str | None = None
        self._session_started = False
        self._assistant_turn_completed = False
        self._input_tokens = 0
        self._output_tokens = 0
        self._cache_read_tokens = 0
        self._cache_write_tokens = 0
        self._thinking_tokens = 0
        self._total_cost_usd = 0.0
        self._cost_reported = False
        self._terminal_event: SessionEnd | None = None
        self._status: str | None = None
        self._finalization_attempted = False
        self._finalized = False
        self._lock = RLock()

    @classmethod
    def begin(
        cls,
        store: SessionStore,
        *,
        provider_id: str,
        model_id: str,
        cwd: str,
        prompt: str,
        session_id: str | None = None,
        title: str | None = None,
        parent_session_id: str | None = None,
        forked_from: str | None = None,
        runtime_owner_id: str | None = None,
        runtime_owner_pid: int | None = None,
    ) -> SessionLifecycleRecorder:
        """Create durable state and record the prompt before returning.

        A bridge may safely emit its session acknowledgement only after this
        method returns.  ``parent_session_id`` must be a canonical session ID,
        never a provider-native resume or thread ID.
        """

        provider = provider_id.strip()
        model = model_id.strip()
        if not provider:
            raise ValueError("provider_id must not be empty")
        if not model:
            raise ValueError("model_id must not be empty")
        if not prompt.strip():
            raise ValueError("prompt must not be empty")

        canonical_session_id = store.create_session(
            session_id=session_id,
            provider_id=provider,
            model_id=model,
            cwd=cwd,
            title=title if title is not None else " ".join(prompt.split())[:96],
            parent_session_id=parent_session_id,
            forked_from=forked_from,
            runtime_owner_id=runtime_owner_id,
            runtime_owner_pid=runtime_owner_pid,
        )
        recorder = cls(
            store=store,
            session_id=canonical_session_id,
            provider_id=provider,
            model_id=model,
        )
        store.append_event(
            canonical_session_id,
            UserPrompt(session_id=canonical_session_id, content=prompt),
        )
        return recorder

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def provider_session_id(self) -> str | None:
        return self._provider_session_id

    @property
    def status(self) -> str | None:
        return self._status

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    @property
    def terminal_event(self) -> SessionEnd | None:
        return self._terminal_event

    @property
    def usage(self) -> SessionUsage:
        return SessionUsage(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cache_read_tokens=self._cache_read_tokens,
            cache_write_tokens=self._cache_write_tokens,
            thinking_tokens=self._thinking_tokens,
            total_cost_usd=self._total_cost_usd if self._cost_reported else None,
        )

    def bind_route(self, *, provider_id: str, model_id: str) -> bool:
        """Bind metadata to the provider/model route that actually ran."""

        provider = provider_id.strip()
        model = model_id.strip()
        if not provider:
            raise ValueError("provider_id must not be empty")
        if not model:
            raise ValueError("model_id must not be empty")

        with self._lock:
            if self._terminal_event is not None:
                return False
            if provider == self._provider_id and model == self._model_id:
                return False
            self._store.update_session_route(
                self._session_id,
                provider_id=provider,
                model_id=model,
            )
            self._provider_id = provider
            self._model_id = model
            return True

    def record(self, event: CanonicalEventType) -> CanonicalEventType | None:
        """Persist and return one accepted operator-visible canonical event.

        ``None`` means the event was a duplicate lifecycle boundary or arrived
        after finalization and must not be projected to the operator either.
        """

        with self._lock:
            if self._terminal_event is not None:
                return None
            if isinstance(event, UserPrompt):
                raise ValueError("the recorder owns the single canonical user prompt")

            canonical = cast(
                CanonicalEventType,
                replace(event, session_id=self._session_id),
            )
            if isinstance(canonical, SessionStart):
                if self._session_started:
                    return None
                provider = canonical.provider_id.strip() or self._provider_id
                model = canonical.model.strip() or self._model_id
                if provider != self._provider_id or model != self._model_id:
                    self._store.update_session_route(
                        self._session_id,
                        provider_id=provider,
                        model_id=model,
                    )
                    self._provider_id = provider
                    self._model_id = model
                canonical = replace(
                    canonical,
                    provider_id=provider,
                    model=model,
                )

            self._store.append_event(self._session_id, canonical)

            if isinstance(canonical, SessionStart):
                self._session_started = True
                provider_session_id = str(canonical.provider_session_id or "").strip()
                if provider_session_id:
                    self._store.set_provider_session_id(
                        self._session_id,
                        provider_session_id,
                    )
                    self._provider_session_id = provider_session_id
            elif isinstance(canonical, UsageReport):
                self._accumulate_usage(canonical)
            elif isinstance(canonical, TextComplete):
                if canonical.role == "assistant":
                    self._assistant_turn_completed = True
            elif isinstance(canonical, SessionEnd):
                self._terminal_event = canonical
                self._finalize_once(self._status_for(canonical))

            return canonical

    def fail(
        self,
        error: BaseException | str,
        *,
        error_code: str = "runner_exception",
    ) -> SessionEnd | None:
        """Synthesize the sole failed terminal event, if still running."""

        message = str(error).strip()
        if isinstance(error, BaseException):
            message = f"{type(error).__name__}: {message}" if message else type(error).__name__
        return self._synthesize_terminal(
            success=False,
            error_code=error_code,
            error_message=message or "session failed",
        )

    def cancel(self, reason: str = "cancelled by operator") -> SessionEnd | None:
        """Synthesize the sole cancelled terminal event, if still running."""

        return self._synthesize_terminal(
            success=False,
            error_code="cancelled",
            error_message=reason.strip() or "cancelled by operator",
        )

    def _synthesize_terminal(
        self,
        *,
        success: bool,
        error_code: str,
        error_message: str,
    ) -> SessionEnd | None:
        with self._lock:
            if self._terminal_event is not None:
                return None
            accepted = self.record(
                SessionEnd(
                    provider_id=self._provider_id,
                    session_id=self._session_id,
                    success=success,
                    error_code=error_code,
                    error_message=error_message,
                )
            )
            return accepted if isinstance(accepted, SessionEnd) else None

    def _accumulate_usage(self, event: UsageReport) -> None:
        self._input_tokens += max(0, int(event.input_tokens or 0))
        self._output_tokens += max(0, int(event.output_tokens or 0))
        self._cache_read_tokens += max(0, int(event.cache_read_tokens or 0))
        self._cache_write_tokens += max(0, int(event.cache_write_tokens or 0))
        self._thinking_tokens += max(0, int(event.thinking_tokens or 0))
        if event.total_cost_usd is not None:
            self._cost_reported = True
            self._total_cost_usd += max(0.0, float(event.total_cost_usd))

    @staticmethod
    def _status_for(event: SessionEnd) -> str:
        if str(event.error_code or "").strip().lower() == "cancelled":
            return "cancelled"
        return "completed" if event.success else "failed"

    def _finalize_once(self, status: str) -> None:
        if self._finalization_attempted:
            return
        self._finalization_attempted = True
        self._status = status
        self._store.finalize_session(
            self._session_id,
            status=status,
            total_cost_usd=(
                self._total_cost_usd if self._cost_reported else None
            ),
            total_turns=1 if self._assistant_turn_completed else 0,
            total_input_tokens=self._input_tokens,
            total_output_tokens=self._output_tokens,
            provider_session_id=self._provider_session_id,
        )
        self._finalized = True
