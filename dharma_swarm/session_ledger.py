"""Session-scoped task/progress ledgers for orchestration traces.

Writes compact JSONL events for:
- task_ledger.jsonl: assignment/routing lifecycle
- progress_ledger.jsonl: execution outcomes, pivots, timing
- episode_ledger.jsonl: versioned validated Episode Ledger events
  (one stable episode_opened, one attempt_started per runtime construction,
  and observation_recorded per task/progress event); this is the first
  producer of the THE_KEEL §6 event family in episode_ledger.py.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.episode_ledger import (
    EpisodeLedgerWriter,
    new_attempt_id,
)
from dharma_swarm.runtime_state import (
    RuntimeStateStore,
    build_session_event_from_ledger_record,
)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class SessionLedger:
    """Append-only JSONL ledgers grouped by session ID."""

    def __init__(
        self,
        base_dir: Path | None = None,
        session_id: str | None = None,
        runtime_db_path: Path | None = None,
    ) -> None:
        self.base_dir = Path(
            base_dir
            or os.getenv("DGC_LEDGER_DIR")
            or (Path.home() / ".dharma" / "ledgers")
        )
        self.session_id = session_id or os.getenv("DGC_SESSION_ID") or _session_stamp()
        self.session_dir = self.base_dir / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.task_path = self.session_dir / "task_ledger.jsonl"
        self.progress_path = self.session_dir / "progress_ledger.jsonl"
        self._runtime_state = RuntimeStateStore(runtime_db_path)

        # Episode identity is stable across restarts of the same named session.
        # Attempt identity is not: every SessionLedger construction represents
        # a distinct runtime attempt within that episode.
        digest = hashlib.sha256(self.session_id.encode("utf-8")).hexdigest()
        self.episode_id = f"ep_{digest[:16]}"
        self.attempt_id = new_attempt_id()
        self.episode_path = self.session_dir / "episode_ledger.jsonl"
        self.episode_ledger_failures = 0
        self._episode_writer: EpisodeLedgerWriter | None = None

        try:
            self._episode_writer = EpisodeLedgerWriter(self.episode_path)
        except Exception:
            self._episode_writer = None
            self.episode_ledger_failures += 1

        # Replay older unacked deliveries before recording this runtime's
        # attempt. File append precedes DB ack; logical-key dedupe makes a
        # crash in that gap exactly-once on the next drain.
        self._drain_episode_outbox()
        self._enqueue_episode_event(
            delivery_key=f"episode:{self.episode_id}:opened",
            event_type="episode_opened",
            attempt_id="",
            payload={"session_id": self.session_id},
        )
        self._enqueue_episode_event(
            delivery_key=f"attempt:{self.attempt_id}:started",
            event_type="attempt_started",
            attempt_id=self.attempt_id,
            payload={"session_id": self.session_id},
        )
        self._drain_episode_outbox()

    def task_event(self, event: str, **payload: Any) -> None:
        self._append(self.task_path, "task", event, payload)

    def progress_event(self, event: str, **payload: Any) -> None:
        self._append(self.progress_path, "progress", event, payload)

    def _append(
        self,
        path: Path,
        ledger_kind: str,
        event: str,
        payload: dict[str, Any],
    ) -> None:
        record = {
            "ts_utc": _utc_ts(),
            "session_id": self.session_id,
            "event": event,
            "ledger_kind": ledger_kind,
            **payload,
        }
        indexed = build_session_event_from_ledger_record(
            session_id=self.session_id,
            ledger_kind=ledger_kind,
            record=record,
        )
        record["event_id"] = indexed.event_id
        # Never break orchestration because ledger persistence failed.
        try:
            with open(path, "a") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            return
        delivery_key = f"session-event:{indexed.event_id}:observation"
        episode_payload = {
            "ledger_kind": ledger_kind,
            "event": event,
            "session_event_id": indexed.event_id,
        }
        try:
            self._runtime_state.record_session_event_with_episode_outbox_sync(
                indexed,
                delivery_key=delivery_key,
                episode_id=self.episode_id,
                attempt_id=self.attempt_id,
                event_type="observation_recorded",
                payload=episode_payload,
            )
        except Exception:
            return
        self._drain_episode_outbox()

    def _enqueue_episode_event(
        self,
        *,
        delivery_key: str,
        event_type: str,
        attempt_id: str,
        payload: dict[str, Any],
    ) -> bool:
        try:
            self._runtime_state.enqueue_episode_event_sync(
                delivery_key=delivery_key,
                episode_id=self.episode_id,
                attempt_id=attempt_id,
                event_type=event_type,
                payload=payload,
            )
            return True
        except Exception:
            self.episode_ledger_failures += 1
            return False

    def _drain_episode_outbox(self) -> int:
        """Append pending deliveries in durable enqueue order, then ack.

        Stop at the first failure so later evidence never overtakes an older
        pending lifecycle event.
        """

        if self._episode_writer is None:
            return 0
        try:
            pending = self._runtime_state.list_pending_episode_events_sync(
                episode_id=self.episode_id,
            )
        except Exception:
            self.episode_ledger_failures += 1
            return 0
        delivered = 0
        for item in pending:
            try:
                persisted = self._episode_writer.append_delivery(
                    delivery_key=item.delivery_key,
                    event_type=item.event_type,
                    episode_id=item.episode_id,
                    attempt_id=item.attempt_id,
                    payload=item.payload,
                    fixed_sequence=0
                    if item.event_type == "episode_opened"
                    else None,
                )
                self._runtime_state.ack_episode_event_sync(
                    item.delivery_key,
                    episode_event_id=persisted.event_id,
                )
            except Exception:
                self.episode_ledger_failures += 1
                break
            delivered += 1
        return delivered
