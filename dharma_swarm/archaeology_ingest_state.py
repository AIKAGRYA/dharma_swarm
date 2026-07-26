"""Archaeology ingest resume cursor — dedupe state file + insert budget.

Extracted from archaeology_ingestion.py (which re-imports these names, so
existing callers and tests are unchanged) to keep that module inside the
Rule-10 line budget. Owns the ``~/.dharma/meta/archaeology_ingest_state.json``
uid→digest cursor: a derived view over vec_documents, rebuildable by deleting
the file (vec-store "unchanged" statuses restore it without re-inserting).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_CYCLE_INSERT_BUDGET = 500
_CYCLE_BUDGET_ENV = "DHARMA_ARCHAEOLOGY_CYCLE_BUDGET"
_INGEST_STATE_FILENAME = "archaeology_ingest_state.json"


def _cycle_insert_budget() -> int:
    """Per-cycle insert budget. Fail-closed: bad/nonpositive values → default."""
    raw = os.environ.get(_CYCLE_BUDGET_ENV, "")
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_CYCLE_INSERT_BUDGET
    return value if value > 0 else _DEFAULT_CYCLE_INSERT_BUDGET


@dataclass
class IngestCycleLedger:
    """Per-cycle dedupe state + insert budget for archaeology ingestion.

    ``state`` maps source uid → sha256(content) — the resumable state-file
    pattern from scripts/vector_store_backfill_memory_sources.py. Unchanged
    documents are skipped; the budget caps total inserts per cycle.

    With a ``state_path``, the ledger flushes the state file every
    ``flush_every`` mutations. run_once is cancelled at 120s by
    orchestrate_live's asyncio.wait_for — without incremental flushes a
    partial cycle would lose all progress and re-scan forever.
    """

    state: dict[str, str] = field(default_factory=dict)
    budget: int | None = None
    inserted: int = 0
    skipped_unchanged: int = 0
    skipped_budget: int = 0
    skipped_error: int = 0
    state_path: Path | None = None
    flush_every: int = 25
    min_flush_interval_s: float = 5.0
    db_generation: int | None = None
    _dirty: int = field(default=0, repr=False)
    _last_flush_monotonic: float = field(default=0.0, repr=False)

    def unchanged(self, source: str, digest: str) -> bool:
        return self.state.get(source) == digest

    def exhausted(self) -> bool:
        return self.budget is not None and self.inserted >= self.budget

    def record(self, source: str, digest: str) -> None:
        self.state[source] = digest
        self.inserted += 1
        self._flush_maybe()

    def note(self, source: str, digest: str) -> None:
        """State-only update — the store already holds this content.

        Rebuilds the resume cursor (e.g. after state-file loss) without
        consuming insert budget or counting as an ingest.
        """
        self.state[source] = digest
        self._flush_maybe()

    def _flush_maybe(self) -> None:
        self._dirty += 1
        if self.state_path is None or self._dirty < max(1, self.flush_every):
            return
        # Time-based checkpoint on top of the mutation count: every flush
        # rewrites the whole uid→digest map, so a burst of mutations must
        # not pay that O(cursor) write per flush_every entries.
        if time.monotonic() - self._last_flush_monotonic < self.min_flush_interval_s:
            return
        self.flush()

    def flush(self) -> None:
        # A clean ledger writes nothing — an unchanged cycle must not
        # rewrite the full cursor file just to store identical bytes.
        if self.state_path is None or self._dirty == 0:
            return
        try:
            _write_ingest_state(self.state_path, self.state, self.db_generation)
            self._dirty = 0
            self._last_flush_monotonic = time.monotonic()
        except OSError as exc:
            logger.warning(
                "Failed to persist archaeology ingest state %s: %s",
                self.state_path, exc,
            )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_ingest_state(path: Path) -> tuple[dict[str, str], int | None]:
    """Return ``(cursor, db_generation)``; accepts the legacy flat format."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Archaeology ingest state %s unreadable (%s); starting fresh",
            path, type(exc).__name__,
        )
        return {}, None
    if not isinstance(payload, dict):
        return {}, None
    cursor = payload.get("cursor")
    if isinstance(cursor, dict):
        generation = payload.get("db_generation")
        return (
            {str(key): str(value) for key, value in cursor.items()},
            generation if isinstance(generation, int) else None,
        )
    # Legacy flat uid→digest format (pre-generation-binding).
    return {str(key): str(value) for key, value in payload.items()}, None


def _write_ingest_state(
    path: Path, state: dict[str, str], db_generation: int | None = None
) -> None:
    # Atomic tmp+replace: this runs every cycle in a daemon; a crash
    # mid-write must not corrupt the cursor (which would force a full,
    # slow re-scan next cycle).
    path.parent.mkdir(parents=True, exist_ok=True)
    state_payload: dict[str, Any] = {"cursor": state}
    if db_generation is not None:
        state_payload["db_generation"] = db_generation
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(state_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
