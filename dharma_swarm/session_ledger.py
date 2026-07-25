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
    EpisodeEvent,
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


def _next_episode_sequence(path: Path, episode_id: str) -> int:
    """Return one greater than the highest valid sequence for *episode_id*.

    Physical line count is not an ordering authority: torn, corrupt, foreign,
    or non-contiguous records must not advance or reuse the next sequence.
    """

    if not path.exists():
        return 1

    highest = 0
    # Tolerant decode, matching EpisodeLedgerWriter._rehydrate: a torn UTF-8
    # tail is one skippable bad line, never a scan-aborting decode error.
    for line in path.read_bytes().decode("utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        try:
            event = EpisodeEvent.from_dict(record)
        except (TypeError, ValueError):
            continue
        if event.episode_id == episode_id:
            highest = max(highest, event.sequence)
    return max(1, highest + 1)


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
        self._episode_sequence = 1

        try:
            self._episode_writer = EpisodeLedgerWriter(self.episode_path)
            self._episode_sequence = _next_episode_sequence(
                self.episode_path, self.episode_id
            )
        except Exception:
            # Count the setup failure once. Later skipped emissions do not
            # repeatedly inflate this same root-cause failure.
            self._episode_writer = None
            self.episode_ledger_failures += 1
        else:
            # episode_opened is episode-scoped (empty attempt_id) and fixed at
            # sequence 0, so a restart re-emits identical content and dedupes.
            self._emit_episode_event(
                "episode_opened",
                sequence=0,
                payload={"session_id": self.session_id},
                attempt_id="",
            )
            self._emit_episode_event(
                "attempt_started",
                sequence=self._episode_sequence,
                payload={"session_id": self.session_id},
            )
            self._episode_sequence += 1

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
        try:
            self._runtime_state.record_session_event_sync(indexed)
        except Exception:
            return
        self._emit_episode_event(
            "observation_recorded",
            sequence=self._episode_sequence,
            payload={
                "ledger_kind": ledger_kind,
                "event": event,
                "session_event_id": indexed.event_id,
            },
        )
        self._episode_sequence += 1

    def _emit_episode_event(
        self,
        event_type: str,
        *,
        sequence: int,
        payload: dict[str, Any],
        attempt_id: str | None = None,
    ) -> bool:
        """Append one validated Episode Ledger event.

        Real append failures are counted. A writer that failed construction was
        already counted once and does not generate a second count per skipped
        event.
        """

        if self._episode_writer is None:
            return False
        try:
            return self._episode_writer.append(
                EpisodeEvent.new(
                    event_type=event_type,
                    episode_id=self.episode_id,
                    attempt_id=self.attempt_id if attempt_id is None else attempt_id,
                    sequence=sequence,
                    payload=payload,
                )
            )
        except Exception:
            self.episode_ledger_failures += 1
            return False
