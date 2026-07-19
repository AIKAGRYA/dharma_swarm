"""Trace store -- persistent lineage tracking for swarm agent actions.

Named ``traces`` (not ``residual_stream``) to avoid confusion with the
mech-interp residual stream concept.  Ported from
~/DHARMIC_GODEL_CLAW/swarm/residual_stream.py into dharma_swarm conventions:
Pydantic BaseModel, async I/O via ``asyncio.to_thread``, no singletons.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from dharma_swarm.archive import FitnessScore
from dharma_swarm.models import _new_id, _utc_now


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, data: dict, indent: int = 2) -> None:
    """Write *data* as JSON to *path* atomically.

    Strategy: write to a temp file in the same directory, then
    ``os.replace()`` which is a POSIX atomic rename on the same
    filesystem.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent, default=str)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class TraceEntry(BaseModel):
    """A single trace event in the swarm's operation log."""

    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utc_now)
    agent: str
    action: str  # e.g. "agent_spawned", "task_completed", "pulse", "circuit_break"
    state: str = "active"
    parent_id: Optional[str] = None
    fitness: Optional[FitnessScore] = None
    files_changed: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = ""  # CorrelationContext trace_id for cross-store correlation


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_DEFAULT_TRACE_PATH = Path.home() / ".dharma" / "traces"


class TraceStore:
    """File-backed trace store with history, archive, and pattern directories.

    All public methods are async.  File I/O is delegated to
    ``asyncio.to_thread`` so the event loop never blocks.
    """

    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path: Path = base_path or _DEFAULT_TRACE_PATH
        self.history_path: Path = self.base_path / "history"
        self.archive_path: Path = self.base_path / "archive"
        self.patterns_path: Path = self.base_path / "patterns"

    # -- lifecycle -----------------------------------------------------------

    async def init(self) -> None:
        """Create directory structure on disk."""
        for d in (self.history_path, self.archive_path, self.patterns_path):
            await asyncio.to_thread(d.mkdir, parents=True, exist_ok=True)

    # -- write ---------------------------------------------------------------

    async def log_entry(self, entry: TraceEntry) -> str:
        """Persist *entry* to ``history/{entry.id}.json`` and return the id."""
        # Auto-populate trace_id from CorrelationContext if not set
        if not entry.trace_id:
            try:
                from dharma_swarm.correlation_context import get_correlation
                corr = get_correlation()
                if corr.trace_id:
                    entry = entry.model_copy(update={"trace_id": corr.trace_id})
            except Exception:
                pass
        dest = self.history_path / f"{entry.id}.json"
        data = json.loads(entry.model_dump_json())
        await asyncio.to_thread(atomic_write_json, dest, data)
        return entry.id

    # -- read ----------------------------------------------------------------

    async def get_entry(self, entry_id: str) -> TraceEntry | None:
        """Load a single entry by id, or ``None`` if not found."""
        path = self.history_path / f"{entry_id}.json"
        return await asyncio.to_thread(self._read_entry, path)

    async def get_recent(self, limit: int = 20) -> list[TraceEntry]:
        """Return the most recent entries sorted by timestamp descending."""
        entries = await asyncio.to_thread(self._read_all_history)
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    async def get_lineage(self, entry_id: str) -> list[TraceEntry]:
        """Walk the ``parent_id`` chain from *entry_id* back to root.

        Returns a list ordered from the given entry back to the oldest
        ancestor (child-first).  Returns an empty list if *entry_id* is
        not found.
        """
        lineage: list[TraceEntry] = []
        seen: set[str] = set()
        current_id: str | None = entry_id

        while current_id and current_id not in seen:
            entry = await self.get_entry(current_id)
            if entry is None:
                break
            lineage.append(entry)
            seen.add(current_id)
            current_id = entry.parent_id

        return lineage

    # -- maintenance ---------------------------------------------------------

    async def archive_old(self, max_age_hours: int = 24) -> int:
        """Move entries older than *max_age_hours* to the archive directory.

        Returns the number of entries archived.
        """
        return await asyncio.to_thread(self._archive_old_sync, max_age_hours)

    # -- private sync helpers ------------------------------------------------

    @staticmethod
    def _read_entry(path: Path) -> TraceEntry | None:
        if not path.exists():
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return TraceEntry.model_validate(data)
        except (json.JSONDecodeError, ValueError, KeyError):
            return None

    def _read_all_history(self) -> list[TraceEntry]:
        if not self.history_path.exists():
            return []
        entries: list[TraceEntry] = []
        for fp in self.history_path.glob("*.json"):
            entry = self._read_entry(fp)
            if entry is not None:
                entries.append(entry)
        return entries

    def _archive_old_sync(self, max_age_hours: int) -> int:
        if not self.history_path.exists():
            return 0
        now = datetime.now(timezone.utc)
        count = 0
        for fp in list(self.history_path.glob("*.json")):
            entry = self._read_entry(fp)
            if entry is None:
                continue
            age_hours = (now - entry.timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                dest = self.archive_path / fp.name
                self.archive_path.mkdir(parents=True, exist_ok=True)
                os.replace(fp, dest)
                count += 1
        return count


# ---------------------------------------------------------------------------
# Front door
# ---------------------------------------------------------------------------


def canonical_trace_store() -> TraceStore:
    """THE documented entry point for operational trace writes.

    Resolves the single canonical location (``~/.dharma/traces``; override
    with ``DHARMA_TRACES_DIR`` for tests and sandboxes). New writers call
    this — or :func:`record_trace` — instead of hand-rolling
    ``TraceStore(base_path=...)``, which is how the per-module path drift
    (``overseeing_i.py:242``, ``ecc_eval_harness.py:442``,
    ``claude_hooks.py:162``) accumulated.

    Role map (do not merge these): this store holds operational lineage
    ``TraceEntry`` rows; ``observability.LocalTraceStore`` is the span/cost
    JSONL; ``chamber/traces.py`` is a deliberately DISJOINT evidence-corpus
    format under the RSI-lab boundary contract (its docstring, lines 9-12)
    and must not be unified into this one.
    """
    override = os.getenv("DHARMA_TRACES_DIR", "").strip()
    if override:
        return TraceStore(base_path=Path(override))
    return TraceStore()


async def record_trace(
    *,
    agent: str,
    action: str,
    state: str = "completed",
    parent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Write one operational trace through the front door; returns entry id."""
    store = canonical_trace_store()
    await store.init()
    return await store.log_entry(
        TraceEntry(
            agent=agent,
            action=action,
            state=state,
            parent_id=parent_id,
            metadata=dict(metadata or {}),
        )
    )


def auto_research_trace_entry(
    *,
    agent: str,
    task_id: str,
    workflow_name: str,
    step_name: str,
    output: Any,
    runtime_fields: list[str] | None = None,
) -> TraceEntry:
    """Build a trace entry for one AutoResearch workflow step."""
    metadata: dict[str, Any] = {
        "task_id": task_id,
        "workflow_name": workflow_name,
        "step_name": step_name,
        "runtime_fields": list(runtime_fields or []),
    }
    if isinstance(output, list):
        metadata["output_count"] = len(output)
        if output and hasattr(output[0], "query_id"):
            metadata["query_count"] = len(output)
        elif output and hasattr(output[0], "source_id"):
            metadata["source_count"] = len(output)
        elif output and hasattr(output[0], "claim_id"):
            metadata["claim_count"] = len(output)
    elif hasattr(output, "report_id"):
        metadata["report_id"] = getattr(output, "report_id", "")
        if hasattr(output, "source_ids"):
            metadata["source_count"] = len(getattr(output, "source_ids", []))
        if hasattr(output, "grade_card"):
            metadata["final_score"] = getattr(output.grade_card, "final_score", 0.0)
    return TraceEntry(
        agent=agent,
        action="auto_research_step",
        state="completed",
        metadata=metadata,
    )


def topology_trace_entry(
    *,
    agent: str,
    workflow_name: str,
    genome_id: str,
    step: TraceEntry | Any,
    output: Any,
) -> TraceEntry:
    """Build a trace entry for one topology-genome workflow step."""
    checkpoint = getattr(step, "checkpoint", {}) or {}
    metadata: dict[str, Any] = {
        "workflow_name": workflow_name,
        "step_name": getattr(step, "name", ""),
        "topology_genome_id": genome_id,
        "topology_node_id": checkpoint.get("topology_node_id", getattr(step, "step_id", "")),
        "topology_edge_ids": list(checkpoint.get("topology_edge_ids", [])),
        "runtime_fields": list(checkpoint.get("runtime_fields", [])),
    }
    if isinstance(output, list):
        metadata["output_count"] = len(output)
    elif isinstance(output, dict):
        metadata["output_keys"] = sorted(output.keys())
    return TraceEntry(
        agent=agent,
        action="topology_step",
        state="completed",
        metadata=metadata,
    )
