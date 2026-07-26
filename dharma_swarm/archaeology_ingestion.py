"""Archaeology Ingestion — continuous indexer of DHARMA SWARM's institutional memory.

This module closes Gap 4 from WHAT_IT_WANTS_TO_BECOME.md:
    "Every time the swarm boots, it starts with whatever is in its
    configuration files and whatever the conductor loads. It cannot ask:
    'What has this system tried before? What worked? What failed? Why?'
    This is the amnesia problem."

What it does:
    Continuously ingests three streams of institutional memory into MemoryPalace
    (LanceDB), making them queryable by any agent during execution:

    Stream 1: Evolution Archive
        Every archive entry (diff, fitness, lineage, parent_id, component)
        becomes a searchable document. Agents can ask: "What has been
        tried for agent_runner.py? What was the highest-fitness mutation?"

    Stream 2: Session Transcripts
        Agent task outputs, WitnessAuditor cycles, and task completion
        records become searchable. Agents can ask: "What research has
        this swarm already done? What topics have been covered?"

    Stream 3: Research Outputs
        Files in ~/.dharma/shared/ (landscape research, competitor analyses,
        synthesis reports) are ingested. Agents avoid duplicating work.

    Stream 4: Stigmergy Marks (high-salience)
        All marks with salience >= 0.85 are ingested as permanent memory.
        The Gnani lodestone marks (salience 0.92-0.97) are always present.

Compressed Lessons (anti-amnesia):
    Every ingestion cycle produces a compressed "lessons learned" document
    that summarizes: what the system has tried, what worked, what failed,
    and what the current best-performing configurations are.
    This document is saved to ~/.dharma/meta/lessons_learned.md and loaded
    into the conductor's context at every boot.

Query interface:
    The `query_archaeology` async function provides agents with a simple
    interface: give it a natural language question, get back the most
    relevant institutional memory.

Usage (daemon)::

    daemon = ArchaeologyIngestionDaemon()
    await daemon.run_once()      # one full ingestion pass
    await daemon.run_forever()   # loop every 30 minutes

Usage (query from agent tool)::

    results = await query_archaeology(
        "What has been tried to fix provider timeout errors?",
        state_dir=Path("~/.dharma"),
    )
    # Returns list of MemoryHit with content, source, relevance_score

Reference:
    DGM open-ended archive: https://sakana.ai/dgm/
    "New agents can branch off from ANY prior agent in the archive."
    This requires the archive to be indexed and accessible, not just stored.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.memory_palace import PalaceQuery
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_INGESTION_INTERVAL = 1800  # 30 minutes
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


@dataclass
class MemoryHit:
    """A single archaeology query result."""
    content: str
    source: str
    layer: str
    relevance_score: float = 0.0
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [truncated {len(text) - max_chars} chars]"


async def _ingest_into_palace(
    palace: Any,
    content: str,
    source: str,
    layer: str,
    tags: list[str],
    metadata: dict[str, Any],
    ledger: IngestCycleLedger | None = None,
) -> str | None:
    """Ingest one document into MemoryPalace. Returns doc_id or None on failure/skip.

    With a ledger, unchanged content (same source uid + digest as last cycle)
    and over-budget inserts are skipped. ledger=None keeps legacy behavior.
    """
    if not content.strip():
        return None
    digest = ""
    if ledger is not None:
        digest = _sha256(content)
        if ledger.unchanged(source, digest):
            ledger.skipped_unchanged += 1
            return None
        if ledger.exhausted():
            ledger.skipped_budget += 1
            return None
    dedupe_info: dict[str, Any] = {}
    extra: dict[str, Any] = {"dedupe_info": dedupe_info} if ledger is not None else {}
    try:
        doc_id = await palace.ingest(
            content=content,
            source=source,
            layer=layer,
            tags=tags,
            metadata=metadata,
            dedupe_digest=digest or None,
            **extra,
        )
    except Exception as exc:
        logger.debug("Palace ingest failed for %s: %s", source, exc)
        return None
    if ledger is None:
        return doc_id
    vec_status = dedupe_info.get("vec_status")
    if vec_status == "unchanged":
        # Vec row already present (state file lost/rebuilding): restore the
        # cursor without consuming budget or reporting a new ingest.
        ledger.note(source, digest)
        ledger.skipped_unchanged += 1
        return None
    if vec_status in ("guard_error", "error"):
        # Nothing landed in the vector store; leave the cursor untouched so
        # the document is retried next cycle.
        ledger.skipped_error += 1
        return None
    if doc_id:
        ledger.record(source, digest)
    return doc_id


# ---------------------------------------------------------------------------
# Stream ingestors
# ---------------------------------------------------------------------------

async def ingest_evolution_archive(
    palace: Any,
    state_dir: Path,
    ledger: IngestCycleLedger | None = None,
) -> int:
    """Ingest all evolution archive entries into MemoryPalace.

    Each entry becomes a document describing: what file was modified,
    what the diff proposed, what the fitness score was, and what the outcome was.
    Agents querying "what has been tried on agent_runner.py?" will find these.

    Returns: number of entries ingested.
    """
    archive_path = state_dir / "evolution" / "archive.jsonl"
    if not archive_path.exists():
        return 0

    ingested = 0
    try:
        lines = archive_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_id = entry.get("id", "")
            component = entry.get("component", entry.get("source_file", "unknown"))
            status = entry.get("status", "unknown")
            timestamp = entry.get("timestamp", "")
            parent_id = entry.get("parent_id", "")
            diff_text = entry.get("diff", "")
            fitness = entry.get("fitness", {})
            test_results = entry.get("test_results", {})

            # Build a human-readable document for this archive entry
            fitness_summary = ""
            if isinstance(fitness, dict):
                weighted = fitness.get("weighted", 0)
                correctness = fitness.get("correctness", 0)
                dharmic = fitness.get("dharmic_alignment", 0)
                fitness_summary = (
                    f"Fitness: weighted={weighted:.3f}, "
                    f"correctness={correctness:.3f}, "
                    f"dharmic_alignment={dharmic:.3f}"
                )

            doc = (
                f"Evolution archive entry: {entry_id}\n"
                f"Component: {component} | Status: {status} | Timestamp: {timestamp}\n"
                f"Parent: {parent_id or 'root'}\n"
                f"{fitness_summary}\n"
                f"Test results: {json.dumps(test_results)[:300]}\n"
            )
            if diff_text.strip():
                doc += f"Diff summary (first 500 chars):\n{diff_text[:500]}\n"

            # Id-less entries: content-hash suffix so distinct entries don't
            # collapse to one key and digest-expire each other (matches the
            # stigmergy / task-completion fallbacks below).
            source_key = (
                f"evolution_archive:{entry_id}" if entry_id
                else f"evolution_archive:{_sha256(doc)[:16]}"
            )
            doc_id = await _ingest_into_palace(
                palace,
                content=doc,
                source=source_key,
                layer="development",
                tags=["evolution", "archive", component, status],
                metadata={
                    "entry_id": entry_id,
                    "component": component,
                    "status": status,
                    "timestamp": timestamp,
                    "parent_id": parent_id,
                    "stream": "evolution_archive",
                },
                ledger=ledger,
            )
            if doc_id:
                ingested += 1

    except Exception as exc:
        logger.warning("Evolution archive ingestion failed: %s", exc)

    logger.info("Evolution archive: %d entries ingested", ingested)
    return ingested


async def ingest_shared_research(
    palace: Any,
    state_dir: Path,
    ledger: IngestCycleLedger | None = None,
) -> int:
    """Ingest research outputs from ~/.dharma/shared/ into MemoryPalace.

    These are the files produced by agents: landscape research, competitor
    analyses, synthesis reports, grant drafts, etc.

    Agents querying "what research has been done on Sakana AI?" will find these.
    This prevents agents from duplicating work that has already been completed.

    Returns: number of files ingested.
    """
    shared_dir = state_dir / "shared"
    if not shared_dir.exists():
        return 0

    artifacts_dir = state_dir / "artifacts"

    ingested = 0
    for directory in [shared_dir, artifacts_dir]:
        if not directory.exists():
            continue
        for f in directory.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue

                # Path-unique key: shared/ + artifacts/ carry duplicate
                # filenames in different directories; a filename-only key
                # makes distinct documents expire each other's rows.
                try:
                    rel_key = f.relative_to(state_dir).as_posix()
                except ValueError:
                    rel_key = f.name
                source_key = f"research:{rel_key}"
                doc_id = await _ingest_into_palace(
                    palace,
                    content=_truncate(content, 3000),
                    source=source_key,
                    layer="development",
                    tags=["research", "output", f.stem],
                    metadata={
                        "file_path": str(f),
                        "file_name": f.name,
                        "stream": "shared_research",
                        "size_bytes": f.stat().st_size,
                    },
                    ledger=ledger,
                )
                if doc_id:
                    ingested += 1
                    if rel_key != f.name:
                        _expire_legacy_research_key(palace, f.name)
            except Exception as exc:
                logger.debug("Failed to ingest %s: %s", f, exc)

    logger.info("Shared research: %d files ingested", ingested)
    return ingested


def _expire_legacy_research_key(palace: Any, file_name: str) -> None:
    """One-time migration: pre-#1133 cycles keyed research rows by filename.

    Row expiry matches ``source`` exactly, so rows written under the old
    ``research:{name}`` key would stay active alongside the new path-keyed
    row forever. Expire them whenever a new-key row lands (a no-op indexed
    lookup once the legacy rows are gone).
    """
    store = getattr(palace, "_vector_store", None)
    if store is None or not hasattr(store, "expire_active_source"):
        return
    try:
        store.expire_active_source(f"research:{file_name}", "research_key_migrated")
    except Exception as exc:
        logger.debug("Legacy research-key expiry failed for %s: %s", file_name, exc)


async def ingest_stigmergy_marks(
    palace: Any,
    state_dir: Path,
    min_salience: float = 0.85,
    ledger: IngestCycleLedger | None = None,
) -> int:
    """Ingest high-salience stigmergy marks into MemoryPalace as permanent memory.

    Marks at salience >= 0.85 represent critical observations that all agents
    should have access to. The Gnani lodestone marks (0.92-0.97) are always included.

    Returns: number of marks ingested.
    """
    marks_path = state_dir / "stigmergy" / "marks.jsonl"
    if not marks_path.exists():
        return 0

    ingested = 0
    try:
        lines = marks_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        for line in lines:
            if not line.strip():
                continue
            try:
                mark = json.loads(line)
            except json.JSONDecodeError:
                continue

            salience = float(mark.get("salience", 0))
            if salience < min_salience:
                continue

            mark_id = mark.get("id", "")
            channel = mark.get("channel", "default")
            observation = mark.get("observation", "")
            agent = mark.get("agent", "unknown")
            file_path = mark.get("file_path", "")

            if not observation.strip():
                continue

            doc = (
                f"Stigmergy mark [{channel}] (salience={salience:.2f})\n"
                f"Agent: {agent} | File: {file_path} | ID: {mark_id}\n"
                f"Observation: {observation}\n"
            )

            # Id-less marks: content-hash suffix so distinct marks in one
            # channel don't collapse to a single key and expire each other.
            source_key = (
                f"stigmergy:{mark_id}" if mark_id
                else f"stigmergy:{channel}:{_sha256(doc)[:16]}"
            )
            doc_id = await _ingest_into_palace(
                palace,
                content=doc,
                source=source_key,
                layer="meta",
                tags=["stigmergy", channel, agent],
                metadata={
                    "mark_id": mark_id,
                    "channel": channel,
                    "salience": salience,
                    "stream": "stigmergy",
                },
                ledger=ledger,
            )
            if doc_id:
                ingested += 1

    except Exception as exc:
        logger.warning("Stigmergy ingestion failed: %s", exc)

    logger.info("Stigmergy marks: %d high-salience marks ingested", ingested)
    return ingested


async def ingest_task_completions(
    palace: Any,
    state_dir: Path,
    ledger: IngestCycleLedger | None = None,
) -> int:
    """Ingest completed task records into MemoryPalace.

    Agents can query: "What tasks has this swarm completed? What approaches
    succeeded? What failed and why?"

    Returns: number of task records ingested.
    """
    db_dir = state_dir / "db"
    task_log_path = state_dir / "tasks" / "completed.jsonl"
    alt_path = db_dir / "task_completions.jsonl"

    ingested = 0
    for path in [task_log_path, alt_path]:
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
            for line in lines[-500:]:  # Last 500 completions to avoid overwhelming
                if not line.strip():
                    continue
                try:
                    task = json.loads(line)
                except json.JSONDecodeError:
                    continue

                title = task.get("title", "unknown")
                result_summary = task.get("result_summary", task.get("output", ""))[:500]
                status = task.get("status", "unknown")
                agent = task.get("agent_id", "unknown")
                completed_at = task.get("completed_at", "")

                if not result_summary.strip():
                    continue

                doc = (
                    f"Task completion: {title}\n"
                    f"Status: {status} | Agent: {agent} | Completed: {completed_at}\n"
                    f"Result: {result_summary}\n"
                )

                task_id = task.get("id", "")
                # Title fallback gets a content-hash suffix: distinct tasks
                # sharing a title must not expire each other's rows.
                source_key = (
                    f"task_completion:{task_id}" if task_id
                    else f"task_completion:{title[:40]}:{_sha256(doc)[:16]}"
                )
                doc_id = await _ingest_into_palace(
                    palace,
                    content=doc,
                    source=source_key,
                    layer="session",
                    tags=["task", "completion", status, agent],
                    metadata={
                        "title": title,
                        "status": status,
                        "agent": agent,
                        "stream": "task_completions",
                    },
                    ledger=ledger,
                )
                if doc_id:
                    ingested += 1
        except Exception as exc:
            logger.debug("Task completion ingestion from %s failed: %s", path, exc)

    logger.info("Task completions: %d records ingested", ingested)
    return ingested


# ---------------------------------------------------------------------------
# Compressed lessons synthesis
# ---------------------------------------------------------------------------

async def synthesize_lessons_learned(
    palace: Any,
    state_dir: Path,
    max_hits: int = 20,
) -> str:
    """Query MemoryPalace for the most important institutional lessons.

    Produces a compressed "lessons learned" document that captures:
    - Best-performing evolution entries (what worked)
    - Common failure patterns (what to avoid)
    - Research already completed (no duplication)
    - Active strategic constraints (from Gnani marks)

    This document is saved to ~/.dharma/meta/lessons_learned.md and loaded
    at every boot. It is the anti-amnesia mechanism.

    Returns: The lessons learned markdown text.
    """
    sections: list[str] = []
    sections.append(f"# DHARMA SWARM Lessons Learned\n*Generated: {_utc_iso()}*\n")

    # Query 1: What evolution strategies worked?
    try:
        result = await palace.recall(PalaceQuery(text="evolution applied fitness improvement success", max_results=5))
        if result.results:
            sections.append("## Evolution: What Worked\n")
            for hit in result.results[:5]:
                content = getattr(hit, 'content', '') or str(hit)
                sections.append(f"- {content[:200]}\n")
    except Exception as exc:
        logger.debug("Lessons query 1 failed: %s", exc)

    # Query 2: What failed or was rolled back?
    try:
        result = await palace.recall(PalaceQuery(text="evolution rolled_back failed rejected error", max_results=5))
        if result.results:
            sections.append("\n## Evolution: What Failed\n")
            for hit in result.results[:5]:
                content = getattr(hit, 'content', '') or str(hit)
                sections.append(f"- {content[:200]}\n")
    except Exception as exc:
        logger.debug("Lessons query 2 failed: %s", exc)

    # Query 3: Research already completed
    try:
        result = await palace.recall(PalaceQuery(text="research completed analysis landscape competitive", max_results=5))
        if result.results:
            sections.append("\n## Research: Already Completed\n")
            for hit in result.results[:5]:
                content = getattr(hit, 'content', '') or str(hit)
                source = getattr(hit, 'source', '')
                sections.append(f"- [{source}] {content[:150]}\n")
    except Exception as exc:
        logger.debug("Lessons query 3 failed: %s", exc)

    # Query 4: Gnani / strategic constraints
    try:
        result = await palace.recall(PalaceQuery(text="gnani witness telos dharmic architecture constraint", max_results=5))
        if result.results:
            sections.append("\n## Strategic Constraints (Gnani Layer)\n")
            for hit in result.results[:5]:
                content = getattr(hit, 'content', '') or str(hit)
                sections.append(f"- {content[:200]}\n")
    except Exception as exc:
        logger.debug("Lessons query 4 failed: %s", exc)

    # Query 5: Provider issues
    try:
        result = await palace.recall(PalaceQuery(text="provider error timeout groq billing access denied", max_results=3))
        if result.results:
            sections.append("\n## Known Provider Issues\n")
            for hit in result.results[:3]:
                content = getattr(hit, 'content', '') or str(hit)
                sections.append(f"- {content[:150]}\n")
    except Exception as exc:
        logger.debug("Lessons query 5 failed: %s", exc)

    lessons_text = "\n".join(sections)

    # Save to disk
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    lessons_path = meta_dir / "lessons_learned.md"
    try:
        lessons_path.write_text(lessons_text, encoding="utf-8")
        logger.info("Lessons learned saved: %s (%d chars)", lessons_path, len(lessons_text))
    except Exception as exc:
        logger.warning("Failed to save lessons learned: %s", exc)

    return lessons_text


# ---------------------------------------------------------------------------
# Query interface for agents
# ---------------------------------------------------------------------------

async def query_archaeology(
    question: str,
    state_dir: Path | None = None,
    top_k: int = 5,
) -> list[MemoryHit]:
    """Query the institutional archaeology memory.

    This is the agent-facing interface. Agents call this when they want
    to know what the system has done before, what worked, what failed,
    or what research has been completed.

    Args:
        question: Natural language question, e.g.:
            "What has been tried to fix provider timeouts?"
            "What research has already been done on Sakana AI?"
            "What are the highest-fitness evolution archive entries?"
        state_dir: DHARMA state directory. Defaults to ~/.dharma.
        top_k: Maximum results to return.

    Returns:
        List of MemoryHit ordered by relevance.
    """
    state_dir = state_dir or dharma_state_dir()

    try:
        from dharma_swarm.memory_palace import MemoryPalace, PalaceQuery

        palace = MemoryPalace(state_dir=state_dir)
        result = await palace.recall(PalaceQuery(text=question, max_results=top_k))

        hits: list[MemoryHit] = []
        for r in result.results:
            content = getattr(r, 'content', '') or str(r)
            source = getattr(r, 'source', 'unknown')
            layer = getattr(r, 'layer', 'unknown')
            score = getattr(r, 'score', 0.0)
            metadata = getattr(r, 'metadata', {})
            hits.append(MemoryHit(
                content=content,
                source=source,
                layer=layer,
                relevance_score=score,
                metadata=metadata,
            ))

        # Also check lessons_learned.md for quick answers
        lessons_path = state_dir / "meta" / "lessons_learned.md"
        if lessons_path.exists() and len(hits) < top_k:
            lessons_text = lessons_path.read_text(encoding="utf-8", errors="ignore")
            # Simple relevance check: does the question's key terms appear?
            question_terms = question.lower().split()
            relevant_lines = [
                line for line in lessons_text.splitlines()
                if any(term in line.lower() for term in question_terms if len(term) > 3)
            ]
            if relevant_lines:
                hits.insert(0, MemoryHit(
                    content="\n".join(relevant_lines[:10]),
                    source="lessons_learned.md",
                    layer="meta",
                    relevance_score=0.8,
                    metadata={"stream": "compressed_lessons"},
                ))

        return hits[:top_k]

    except Exception as exc:
        logger.warning("Archaeology query failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Main daemon class
# ---------------------------------------------------------------------------

class ArchaeologyIngestionDaemon:
    """Continuous ingestion daemon for DHARMA SWARM's institutional memory.

    Runs every 30 minutes (configurable). On each cycle:
    1. Ingests evolution archive entries
    2. Ingests shared research outputs
    3. Ingests high-salience stigmergy marks
    4. Ingests task completion records
    5. Synthesizes compressed lessons learned document

    At boot, the conductor loads lessons_learned.md as a context prefix,
    ensuring the swarm starts each session with its accumulated wisdom.

    Args:
        state_dir: DHARMA state directory. Defaults to ~/.dharma.
        interval_seconds: Time between ingestion cycles (default: 30 min).
    """

    def __init__(
        self,
        state_dir: Path | None = None,
        interval_seconds: int = _DEFAULT_INGESTION_INTERVAL,
    ) -> None:
        self._state_dir = state_dir or dharma_state_dir()
        self._interval = interval_seconds

    async def run_once(self) -> dict[str, int]:
        """Run one full ingestion cycle. Returns counts per stream."""
        try:
            from dharma_swarm.memory_palace import MemoryPalace
            palace = MemoryPalace(state_dir=self._state_dir)
        except Exception as exc:
            logger.error("ArchaeologyIngestionDaemon: MemoryPalace unavailable: %s", exc)
            return {}

        state_path = self._state_dir / "meta" / _INGEST_STATE_FILENAME
        cursor, saved_generation = _read_ingest_state(state_path)

        vector_store = getattr(palace, "_vector_store", None)
        generation: int | None = None
        if vector_store is not None:
            # One-time dedupe-index build OFF the event loop: the lazy
            # in-upsert build on a large existing DB takes minutes while
            # holding the write lock, and run_once executes under
            # orchestrate_live's asyncio.wait_for — a synchronous build
            # would stall every other loop far past the timeout.
            if hasattr(vector_store, "ensure_dedupe_index_built"):
                try:
                    await asyncio.to_thread(vector_store.ensure_dedupe_index_built)
                except Exception as exc:
                    logger.warning(
                        "Dedupe index pre-build failed (per-upsert guard stays fail-closed): %s",
                        exc,
                    )
            if hasattr(vector_store, "db_generation"):
                try:
                    generation = await asyncio.to_thread(vector_store.db_generation)
                except Exception as exc:
                    logger.debug("vectors.db generation probe failed: %s", exc)

        if (
            generation is not None
            and saved_generation is not None
            and generation != saved_generation
        ):
            # vectors.db was recreated or replaced since the cursor was
            # written: state-only skips would leave the new DB missing every
            # "unchanged" document indefinitely. Discard the cursor; the
            # vec-store "unchanged" statuses rebuild it without re-inserting
            # rows that do exist.
            logger.warning(
                "vectors.db generation changed (%s -> %s); discarding archaeology cursor",
                saved_generation, generation,
            )
            cursor = {}

        total_budget = _cycle_insert_budget()
        ledger = IngestCycleLedger(
            state=cursor,
            budget=total_budget,
            state_path=state_path,
            db_generation=generation if generation is not None else saved_generation,
        )

        counts: dict[str, int] = {}
        streams = (
            ("evolution_archive", ingest_evolution_archive),
            ("shared_research", ingest_shared_research),
            ("stigmergy_marks", ingest_stigmergy_marks),
            ("task_completions", ingest_task_completions),
        )

        try:
            for index, (name, ingestor) in enumerate(streams):
                # Fair-share budget: a large backlog in an early stream must
                # not starve later streams indefinitely — each stream gets a
                # reserved slice of the remaining budget first.
                remaining = max(0, total_budget - ledger.inserted)
                share = max(1, remaining // (len(streams) - index))
                ledger.budget = min(total_budget, ledger.inserted + share)
                counts[name] = await ingestor(palace, self._state_dir, ledger=ledger)
            if ledger.skipped_budget and ledger.inserted < total_budget:
                # Mop-up pass: streams that left their reserved slice unused
                # must not strand budget while another stream still has
                # backlog. Runs only when something was budget-skipped, so
                # the steady state (nothing skipped) stays a single sweep;
                # re-visits of already-recorded docs are ledger no-ops.
                ledger.budget = total_budget
                inserted_before = ledger.inserted
                unchanged_before = ledger.skipped_unchanged
                budget_before = ledger.skipped_budget
                error_before = ledger.skipped_error
                for name, ingestor in streams:
                    if ledger.exhausted():
                        break
                    counts[name] += await ingestor(palace, self._state_dir, ledger=ledger)
                # Every doc was already tallied in the fair-share pass; the
                # mop-up only converts provisional budget-skips into inserts,
                # so restore the skip counters to unique-doc counts.
                mopped = ledger.inserted - inserted_before
                ledger.skipped_unchanged = unchanged_before
                ledger.skipped_budget = max(0, budget_before - mopped)
                ledger.skipped_error = error_before
        finally:
            # orchestrate_live cancels run_once at 120s (asyncio.wait_for);
            # the cursor must survive partial cycles or every cycle restarts
            # from scratch. The write is synchronous, so it completes even
            # during CancelledError unwinding.
            ledger.budget = total_budget
            ledger.flush()

        # Synthesize compressed lessons
        await synthesize_lessons_learned(palace, self._state_dir)

        total = sum(counts.values())
        logger.info(
            "Archaeology ingestion complete: %d documents total | %s | "
            "skipped_unchanged=%d skipped_budget=%d skipped_error=%d budget=%s",
            total, counts, ledger.skipped_unchanged, ledger.skipped_budget,
            ledger.skipped_error, ledger.budget,
        )
        counts["skipped_unchanged"] = ledger.skipped_unchanged
        counts["skipped_budget"] = ledger.skipped_budget
        counts["skipped_error"] = ledger.skipped_error
        return counts

    async def run_forever(self) -> None:
        """Run ingestion continuously on a fixed interval."""
        logger.info(
            "ArchaeologyIngestionDaemon starting (interval=%ds)", self._interval
        )
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.error("Archaeology ingestion cycle failed: %s", exc, exc_info=True)
            await asyncio.sleep(self._interval)


# ---------------------------------------------------------------------------
# Wiring into orchestrate_live.py — the ingestion loop task
# ---------------------------------------------------------------------------

async def start_archaeology_loop(
    state_dir: Path | None = None,
    interval_seconds: int = _DEFAULT_INGESTION_INTERVAL,
) -> asyncio.Task:
    """Start the archaeology ingestion daemon as a background asyncio task.

    Called from orchestrate_live.py during boot, alongside other background
    loops (evolution, witness, etc.).

    Returns the asyncio Task so it can be tracked and cancelled on shutdown.
    """
    daemon = ArchaeologyIngestionDaemon(state_dir=state_dir, interval_seconds=interval_seconds)

    # Run once immediately at boot (before the interval timer)
    try:
        await asyncio.wait_for(daemon.run_once(), timeout=120.0)
    except asyncio.TimeoutError:
        logger.warning("Boot-time archaeology ingestion timed out (120s) — continuing")
    except Exception as exc:
        logger.warning("Boot-time archaeology ingestion failed (non-fatal): %s", exc)

    # Then schedule the recurring loop
    task = asyncio.create_task(daemon.run_forever(), name="archaeology_ingestion")
    return task


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    import json

    logging.basicConfig(level=logging.INFO)
    daemon = ArchaeologyIngestionDaemon()
    counts = await daemon.run_once()
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
