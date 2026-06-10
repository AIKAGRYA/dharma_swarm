"""Self-Managing Agent Memory (Letta-inspired).

Each agent has explicit memory tools: remember(), recall(), forget().
Memory is structured in tiers:
- Working Memory (in-context, fast, limited)
- Short-term Memory (SQLite, session-scoped)
- Long-term Memory (SQLite, cross-session, persistent)
- Shared Memory (visible to all agents in the swarm)

The agent DECIDES what to remember and what to page in/out,
like an OS managing RAM vs disk.

Storage: SQLite at ~/.dharma/agent_memory/memories.db
Compatible with the existing AgentMemoryBank but adds:
- Persistent SQLite storage (no more JSON file corruption)
- Scoped memory (WORKING, SHORT_TERM, LONG_TERM, SHARED)
- TTL-based expiry for ephemeral memories
- Cross-agent shared memory with tags
- Keyword-based retrieval with recency/frequency scoring
- Token-budgeted context building
- Consolidation to prevent unbounded growth
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Canonical cognitive-memory typology. ``MemoryLane`` is the repo's single
# source of truth for the episodic/semantic/procedural distinction (declared in
# the MemoryKernel surface census). We import it here so the per-agent runtime
# store types its rows with the SAME vocabulary the kernel uses to classify
# memory surfaces -- no parallel enum. ``atoms`` has only stdlib deps, so this
# import is cheap and free of the provider-chain circular import that the unit
# test guards against.
from dharma_swarm.memory_kernel.atoms import MemoryLane

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class Scope(str, Enum):
    """Memory scope determines visibility and lifetime."""
    WORKING = "working"          # In-context, fast, limited
    SHORT_TERM = "short_term"    # Session-scoped, auto-expires
    LONG_TERM = "long_term"      # Cross-session, persistent
    SHARED = "shared"            # Visible to all agents


# Alias for recall queries that search all scopes
ALL_SCOPES = (Scope.WORKING, Scope.SHORT_TERM, Scope.LONG_TERM, Scope.SHARED)


# The cognitive lanes a per-agent runtime memory can carry. These are a subset
# of the canonical ``MemoryLane`` enum -- the three classical long-term memory
# types plus the always-hot ``WORKING`` lane that is the backward-compatible
# default for every row written before D4.
#   - EPISODIC   : "what happened" -- events, observations, session traces.
#                  Retrieval is recency-weighted (the latest episode wins).
#   - SEMANTIC   : "what is true" -- facts, learned principles, relations.
#                  Retrieval is importance/frequency-weighted (the most-reused
#                  fact wins), recency-insensitive.
#   - PROCEDURAL : "how to do X" -- skills, recipes, prescriptive patterns.
#                  Retrieval favours strong/whole matches (the right procedure
#                  for the task, not the most recent one).
#   - WORKING    : default lane for untyped rows; behaves as before D4.
COGNITIVE_LANES = (
    MemoryLane.WORKING,
    MemoryLane.EPISODIC,
    MemoryLane.SEMANTIC,
    MemoryLane.PROCEDURAL,
)

# Default lane for rows that do not declare one (and for pre-D4 rows after the
# additive migration). EPISODIC is the safe default: an undeclared memory is, by
# nature, "a thing that happened during a session".
_DEFAULT_LANE = MemoryLane.EPISODIC

# Key prefix marking a PROCEDURAL memory as a *named, identity-bound skill* (D5).
# A skill is not a new kind of storage -- it is a procedure addressed by a stable
# capability name so the agent's accrued know-how can be enumerated as a
# capability profile and reinforced by reuse. ``learn_skill`` / ``recall_skill``
# / ``accrued_skills`` are thin specialisations of the existing PROCEDURAL lane
# methods around this convention; nothing else changes. The reuse count
# (``access_count``) that PROCEDURAL retrieval already bumps IS the per-skill
# reward signal -- a skill that keeps getting recalled for relevant tasks rises.
_SKILL_KEY_PREFIX = "skill:"


def _skill_name(key: str) -> str | None:
    """Return the skill name if ``key`` is a skill key, else None."""
    if key.startswith(_SKILL_KEY_PREFIX):
        name = key[len(_SKILL_KEY_PREFIX):].strip()
        return name or None
    return None


def _coerce_lane(lane: "MemoryLane | str | None") -> MemoryLane:
    """Normalise any lane input to a ``MemoryLane`` restricted to the cognitive
    set. Unknown / out-of-set values fall back to the default lane rather than
    raising, so a stale or malformed row never breaks recall."""
    if lane is None:
        return _DEFAULT_LANE
    if isinstance(lane, MemoryLane):
        return lane if lane in COGNITIVE_LANES else _DEFAULT_LANE
    try:
        coerced = MemoryLane(str(lane).strip().lower())
    except ValueError:
        return _DEFAULT_LANE
    return coerced if coerced in COGNITIVE_LANES else _DEFAULT_LANE


@dataclass
class Memory:
    """A single memory entry."""
    id: int = 0
    agent_id: str = ""
    key: str = ""
    content: str = ""
    scope: Scope = Scope.WORKING
    created_at: float = 0.0      # Unix timestamp
    accessed_at: float = 0.0     # Unix timestamp
    access_count: int = 0
    ttl: int | None = None       # Seconds until expiry, None = permanent
    embedding_hash: str = ""     # For future dedup / semantic search
    tags: str = ""               # Comma-separated tags (for shared memories)
    lane: MemoryLane = _DEFAULT_LANE  # Cognitive type: episodic/semantic/procedural/working

    @property
    def is_expired(self) -> bool:
        """Check if this memory has expired based on TTL."""
        if self.ttl is None:
            return False
        return time.time() > (self.created_at + self.ttl)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "key": self.key,
            "content": self.content,
            "scope": self.scope.value,
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
            "access_count": self.access_count,
            "ttl": self.ttl,
            "embedding_hash": self.embedding_hash,
            "tags": self.tags,
            "lane": self.lane.value,
        }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'working',
    created_at REAL NOT NULL,
    accessed_at REAL NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    ttl INTEGER,
    embedding_hash TEXT DEFAULT '',
    lane TEXT NOT NULL DEFAULT 'episodic',
    UNIQUE(agent_id, key, scope, lane)
);

CREATE INDEX IF NOT EXISTS idx_memories_agent_scope
    ON memories(agent_id, scope);
CREATE INDEX IF NOT EXISTS idx_memories_accessed
    ON memories(accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_key
    ON memories(agent_id, key);
-- NOTE: the lane column + idx_memories_agent_lane are created by
-- _migrate_lane_column(), NOT here. On a legacy DB the CREATE TABLE above is a
-- no-op (table already exists without `lane`), so referencing `lane` in this
-- script would fail before the additive migration adds the column.

CREATE TABLE IF NOT EXISTS shared_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    tags TEXT DEFAULT '',
    UNIQUE(key)
);

CREATE INDEX IF NOT EXISTS idx_shared_key
    ON shared_memories(key);
CREATE INDEX IF NOT EXISTS idx_shared_tags
    ON shared_memories(tags);
"""


# ---------------------------------------------------------------------------
# AgentMemoryManager
# ---------------------------------------------------------------------------


class AgentMemoryManager:
    """Self-managing memory for a single agent.

    Provides remember/recall/forget/share operations with SQLite persistence.
    Thread-safe via a per-instance lock.

    Usage:
        mgr = AgentMemoryManager("agent_alpha")
        await mgr.remember("goal", "finish R_V paper", scope=Scope.WORKING)
        results = await mgr.recall("R_V", limit=5)
        context = await mgr.get_context(budget_tokens=2000)

    Identity-bound usage (recommended when an agent declares a
    ``memory_namespace`` via its registration / onboarding record):
        mgr = AgentMemoryManager.for_namespace("agent:opus_composer")
        # resolves to the ONE store for opus_composer across all sessions
    """

    # Limits per scope per agent
    MAX_WORKING = 50
    MAX_SHORT_TERM = 500
    MAX_LONG_TERM = 10_000
    MAX_SHARED = 50_000  # Global, not per agent

    def __init__(
        self,
        agent_id: str,
        db_path: str | Path | None = None,
    ) -> None:
        self._agent_id = agent_id
        if db_path is None:
            db_path = Path.home() / ".dharma" / "agent_memory" / "memories.db"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def db_path(self) -> Path:
        return self._db_path

    # -- Identity binding --------------------------------------------------

    @staticmethod
    def resolve_agent_id(namespace: str) -> str:
        """Resolve any identity form to the ONE canonical store key.

        An agent's continuity anchor declares a ``memory_namespace`` (see
        ``external_agent_registration.ExternalRoamingWorker.memory_namespace``
        and ``roaming_onboarding``), which is written in the prefixed form
        ``agent:<uid>`` for roaming workers, or as a bare path component
        (``operator``, ``witness``) for the constitutional roster. Nothing in
        the repo previously mapped those forms onto the sqlite ``agent_id``
        column, so the same agent could land in two different stores depending
        on whether the caller passed ``config.name`` or the declared namespace.

        This producer collapses every form to the bare ``uid``:

            ``agent:opus_composer``      -> ``opus_composer``
            ``agent:opus_composer:sub``  -> ``opus_composer``  (sub-scope folds in)
            ``opus_composer``            -> ``opus_composer``
            ``operator``                 -> ``operator``

        Resolution is idempotent: ``resolve(resolve(x)) == resolve(x)``.
        """

        if namespace is None:  # type: ignore[unreachable]
            raise ValueError("memory namespace must not be None")
        ns = str(namespace).strip()
        if not ns:
            raise ValueError("memory namespace must not be empty")
        if ns.startswith("agent:"):
            ns = ns[len("agent:"):]
        # Fold any sub-namespace (agent:<uid>:<sub>) onto the owning uid so the
        # agent resolves to ONE bound store regardless of sub-scope.
        uid = ns.split(":", 1)[0].strip()
        if not uid:
            raise ValueError(f"namespace {namespace!r} has no agent uid component")
        return uid

    @classmethod
    def for_namespace(
        cls,
        namespace: str,
        db_path: str | Path | None = None,
    ) -> "AgentMemoryManager":
        """Bind a manager to the ONE canonical store for an identity namespace.

        This is the binding the D2 contract requires: ``agent:opus_composer``
        (or ``opus_composer``, or any sub-scope of it) resolves to exactly one
        ``AgentMemoryManager`` store, so learnings written in one session are
        recalled in a later session through the same key. Use this instead of
        ``AgentMemoryManager(config.name)`` whenever a declared
        ``memory_namespace`` is available.
        """

        return cls(cls.resolve_agent_id(namespace), db_path=db_path)

    # -- Database setup ----------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create the SQLite connection (one per instance)."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path),
                timeout=10.0,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            conn = self._get_conn()
            conn.executescript(_SCHEMA_SQL)
            self._migrate_lane_column(conn)
            conn.commit()

    @staticmethod
    def _migrate_lane_column(conn: sqlite3.Connection) -> None:
        """Additively add the ``lane`` column to a pre-D4 ``memories`` table.

        ``executescript`` above creates the table with ``lane`` for *fresh*
        databases. Existing databases (e.g. the live shared store) predate the
        column, so we add it idempotently. This is purely additive: existing
        rows take the ``episodic`` default, every prior read/write keeps working,
        and the migration is a no-op once applied.

        We do not rebuild the table to widen the legacy
        ``UNIQUE(agent_id, key, scope)`` constraint into the new
        ``(agent_id, key, scope, lane)`` form: the legacy constraint is strictly
        tighter, so it never produces a wrong result, only a slightly narrower
        capacity (one lane per key+scope) on legacy stores. Fresh stores get the
        full per-lane capacity. Avoiding the rebuild keeps the migration
        reversible and zero-risk against the live shared db.
        """
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "lane" not in cols:
            conn.execute(
                "ALTER TABLE memories ADD COLUMN lane TEXT NOT NULL DEFAULT 'episodic'"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_agent_lane ON memories(agent_id, lane)"
        )

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # -- Core API ----------------------------------------------------------

    async def remember(
        self,
        key: str,
        content: str,
        scope: Scope = Scope.WORKING,
        ttl: int | None = None,
        tags: str = "",
        lane: "MemoryLane | str | None" = None,
    ) -> Memory:
        """Store a memory, typed by cognitive ``lane``. Upserts in place.

        Args:
            key: Identifier for this memory (agent-scoped).
            content: The actual memory content.
            scope: WORKING, SHORT_TERM, LONG_TERM, or SHARED.
            ttl: Time-to-live in seconds. None = permanent.
            tags: Comma-separated tags (primarily for shared memories).
            lane: Cognitive type -- ``MemoryLane.EPISODIC`` (what happened),
                ``SEMANTIC`` (what is true), or ``PROCEDURAL`` (how to do X).
                Defaults to ``EPISODIC`` (the type of an undeclared memory).
                On a fresh store the same ``key`` may hold one row per lane;
                on a legacy store the lane is recorded but key+scope stays unique.

        Returns:
            The stored Memory object.
        """
        if scope == Scope.SHARED:
            return await self.share(key, content, tags=tags)

        resolved_lane = _coerce_lane(lane)
        now = time.time()
        embedding_hash = _content_hash(content)

        with self._lock:
            conn = self._get_conn()

            # Enforce scope limits before insert
            self._enforce_limit(conn, scope)

            # Explicit update-or-insert (not ON CONFLICT) so the same code path
            # works whether the store has the legacy UNIQUE(agent_id,key,scope)
            # constraint or the new UNIQUE(agent_id,key,scope,lane) one.
            existing = conn.execute(
                "SELECT id FROM memories WHERE agent_id=? AND key=? AND scope=? AND lane=?",
                (self._agent_id, key, scope.value, resolved_lane.value),
            ).fetchone()

            if existing is None:
                # If a legacy row exists for this key+scope under a different
                # lane, the legacy UNIQUE would reject a second insert. Detect
                # that and update the legacy row in place (carrying the new lane)
                # so legacy stores keep upsert semantics on key+scope.
                legacy = conn.execute(
                    "SELECT id FROM memories WHERE agent_id=? AND key=? AND scope=?",
                    (self._agent_id, key, scope.value),
                ).fetchone()
                if legacy is not None and self._unique_excludes_lane(conn):
                    existing = legacy

            if existing is not None:
                conn.execute(
                    """UPDATE memories
                       SET content=?, accessed_at=?, ttl=?, embedding_hash=?, lane=?
                       WHERE id=?""",
                    (content, now, ttl, embedding_hash, resolved_lane.value, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO memories
                       (agent_id, key, content, scope, created_at, accessed_at,
                        access_count, ttl, embedding_hash, lane)
                       VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
                    (self._agent_id, key, content, scope.value, now, now,
                     ttl, embedding_hash, resolved_lane.value),
                )
            conn.commit()

            row = conn.execute(
                "SELECT * FROM memories WHERE agent_id=? AND key=? AND scope=? AND lane=?",
                (self._agent_id, key, scope.value, resolved_lane.value),
            ).fetchone()
            if row is None:
                # Legacy store updated a differently-laned row in place.
                row = conn.execute(
                    "SELECT * FROM memories WHERE agent_id=? AND key=? AND scope=?",
                    (self._agent_id, key, scope.value),
                ).fetchone()

        return _row_to_memory(row) if row else Memory(
            agent_id=self._agent_id, key=key, content=content,
            scope=scope, created_at=now, accessed_at=now, ttl=ttl, lane=resolved_lane,
        )

    def _unique_excludes_lane(self, conn: sqlite3.Connection) -> bool:
        """True if this store has the legacy UNIQUE(agent_id,key,scope) constraint
        (lane not part of the uniqueness), i.e. a pre-D4 database. Cached after
        first probe."""
        cached = getattr(self, "_legacy_unique", None)
        if cached is not None:
            return cached
        legacy = True  # assume legacy unless we positively see lane in a unique index
        for idx in conn.execute("PRAGMA index_list(memories)").fetchall():
            if not idx["unique"]:
                continue
            cols = [r["name"] for r in conn.execute(
                f"PRAGMA index_info({idx['name']})"
            ).fetchall()]
            if "lane" in cols:
                legacy = False
                break
        self._legacy_unique = legacy  # type: ignore[attr-defined]
        return legacy

    async def recall(
        self,
        query: str,
        scope: Scope | None = None,
        limit: int = 5,
        lane: "MemoryLane | str | None" = None,
    ) -> list[Memory]:
        """Retrieve memories by keyword match, ranked **by cognitive lane**.

        Retrieval is type-appropriate: the rank put on a match depends on the
        lane of the memory, mirroring how the three classical memory systems
        are actually used:

        - EPISODIC   -> recency dominates (the latest relevant event surfaces).
        - SEMANTIC   -> reuse/frequency dominates (the best-established fact
                        surfaces), recency is a weak tiebreak.
        - PROCEDURAL -> match strength dominates (the procedure that matches the
                        task most completely surfaces), reuse is the tiebreak.

        Args:
            query: Search string (space-separated keywords).
            scope: Restrict to a specific scope, or None for all.
            limit: Maximum results to return.
            lane: Restrict to one cognitive lane (episodic/semantic/procedural),
                or None to search every lane.

        Returns:
            List of matching Memory objects, most relevant first.
        """
        keywords = _extract_keywords(query)
        if not keywords:
            return []

        lane_filter = _coerce_lane(lane) if lane is not None else None
        scopes = [scope] if scope else list(ALL_SCOPES)
        results: list[Memory] = []

        with self._lock:
            conn = self._get_conn()
            now = time.time()

            # Search agent-scoped memories
            for s in scopes:
                if s == Scope.SHARED:
                    # Shared memory is cross-agent and untyped; lane filtering
                    # only applies to the per-agent cognitive store.
                    if lane_filter is None:
                        shared = self._search_shared_locked(conn, keywords, limit)
                        results.extend(shared)
                    continue

                rows = conn.execute(
                    "SELECT * FROM memories WHERE agent_id=? AND scope=?",
                    (self._agent_id, s.value),
                ).fetchall()

                for row in rows:
                    mem = _row_to_memory(row)
                    if mem.is_expired:
                        continue
                    if lane_filter is not None and mem.lane != lane_filter:
                        continue
                    score = _keyword_score(keywords, mem.key, mem.content)
                    if score > 0:
                        # Snapshot the PRE-access standing for lane ranking: this
                        # recall is about to stamp accessed_at=now and bump the
                        # count, which would otherwise flatten the recency signal
                        # episodic retrieval depends on. Rank by what the memory
                        # was before we touched it.
                        mem._rank_recency = mem.accessed_at  # type: ignore[attr-defined]
                        mem._rank_reuse = mem.access_count    # type: ignore[attr-defined]
                        # Update access stats (the touch).
                        conn.execute(
                            """UPDATE memories SET accessed_at=?, access_count=access_count+1
                               WHERE id=?""",
                            (now, mem.id),
                        )
                        mem.accessed_at = now
                        mem.access_count += 1
                        mem._score = score  # type: ignore[attr-defined]
                        results.append(mem)

            conn.commit()

        results.sort(key=_lane_rank_key, reverse=True)
        return results[:limit]

    async def recall_by_lane(
        self,
        query: str,
        lane: "MemoryLane | str",
        scope: Scope | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        """Type-appropriate retrieval restricted to one cognitive lane.

        Convenience wrapper over ``recall(..., lane=...)``. Returns only memories
        of the requested cognitive type, ranked by that lane's retrieval policy
        (episodic=recency, semantic=reuse, procedural=match-strength)."""
        return await self.recall(query, scope=scope, limit=limit, lane=lane)

    async def recall_by_key(self, key: str, scope: Scope | None = None) -> Memory | None:
        """Exact key lookup. Returns the memory or None."""
        with self._lock:
            conn = self._get_conn()
            now = time.time()

            if scope:
                row = conn.execute(
                    "SELECT * FROM memories WHERE agent_id=? AND key=? AND scope=?",
                    (self._agent_id, key, scope.value),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM memories WHERE agent_id=? AND key=? ORDER BY accessed_at DESC LIMIT 1",
                    (self._agent_id, key),
                ).fetchone()

            if row is None:
                # Check shared memories
                shared_row = conn.execute(
                    "SELECT * FROM shared_memories WHERE key=?",
                    (key,),
                ).fetchone()
                if shared_row:
                    return _shared_row_to_memory(shared_row)
                return None

            # Update access stats
            conn.execute(
                "UPDATE memories SET accessed_at=?, access_count=access_count+1 WHERE id=?",
                (now, row["id"]),
            )
            conn.commit()

        mem = _row_to_memory(row)
        mem.accessed_at = now
        mem.access_count = row["access_count"] + 1
        return mem

    # -- Self-editing memory-block operations ------------------------------
    # Letta/MemGPT core-memory block edits. ``remember`` already upserts a whole
    # block (full replace). These add the two finer block edits an agent needs
    # to curate its OWN memory in place: append to a block, and surgical
    # substring replace within a block -- the ``core_memory_append`` /
    # ``core_memory_replace`` pair. Both go through the same upsert path as
    # ``remember`` so lane/scope/legacy-store semantics are identical.

    async def append(
        self,
        key: str,
        content: str,
        scope: Scope = Scope.WORKING,
        lane: "MemoryLane | str | None" = None,
        sep: str = "\n",
    ) -> Memory:
        """Append ``content`` to an existing memory block, in place.

        The self-editing ``core_memory_append`` operation: the agent grows one
        of its own blocks rather than minting a new key for every fragment. If
        the block (same key+scope, and on a fresh store the same lane) does not
        yet exist, this behaves as a first write.

        Args:
            key: The block to append to (agent-scoped).
            content: Text to append.
            scope: Block scope. SHARED is not block-editable here -- a shared
                memory is cross-agent; append targets the agent's own store.
            lane: Cognitive lane of the block (defaults as in ``remember``).
            sep: Separator inserted between existing and new content when the
                block is non-empty.

        Returns:
            The updated Memory block.
        """
        if scope == Scope.SHARED:
            raise ValueError(
                "append() edits an agent's own block; SHARED memory is "
                "cross-agent. Use remember(scope=SHARED) / share() instead."
            )
        existing = await self._get_own_block(key, scope, lane)
        if existing is None or not existing.content:
            new_content = content
        else:
            new_content = f"{existing.content}{sep}{content}"
        # Preserve the existing block's lane on append unless caller overrides.
        eff_lane = lane if lane is not None else (existing.lane if existing else None)
        return await self.remember(key, new_content, scope=scope, lane=eff_lane)

    async def replace_block(
        self,
        key: str,
        old: str,
        new: str,
        scope: Scope = Scope.WORKING,
        lane: "MemoryLane | str | None" = None,
    ) -> Memory | None:
        """Surgically replace a substring inside an existing memory block.

        The self-editing ``core_memory_replace`` operation: the agent edits part
        of one of its own blocks without rewriting the whole thing. Returns the
        updated block, or ``None`` if no block exists for ``key`` (nothing to
        edit) -- an absent block is not an error, it is simply a no-op.

        Args:
            key: The block to edit (agent-scoped).
            old: Substring to find. If empty, ``new`` is appended (degenerate
                replace == append-at-end, matching Letta semantics).
            new: Replacement text (use "" to delete ``old``).
            scope: Block scope (SHARED not supported -- see ``append``).
            lane: Cognitive lane of the block (defaults as in ``remember``).
        """
        if scope == Scope.SHARED:
            raise ValueError(
                "replace_block() edits an agent's own block; SHARED memory is "
                "cross-agent. Use remember(scope=SHARED) / share() instead."
            )
        existing = await self._get_own_block(key, scope, lane)
        if existing is None:
            return None
        if old == "":
            new_content = f"{existing.content}{new}" if existing.content else new
        else:
            new_content = existing.content.replace(old, new)
        eff_lane = lane if lane is not None else existing.lane
        return await self.remember(key, new_content, scope=scope, lane=eff_lane)

    async def _get_own_block(
        self,
        key: str,
        scope: Scope,
        lane: "MemoryLane | str | None",
    ) -> Memory | None:
        """Read one of THIS agent's own blocks by key+scope (+lane on a fresh
        store) without bumping access stats. Used by the block-edit operations,
        which must read-then-write the same row.
        """
        resolved_lane = _coerce_lane(lane)
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM memories WHERE agent_id=? AND key=? AND scope=? AND lane=?",
                (self._agent_id, key, scope.value, resolved_lane.value),
            ).fetchone()
            if row is None:
                # Legacy store: key+scope is unique regardless of lane.
                row = conn.execute(
                    "SELECT * FROM memories WHERE agent_id=? AND key=? AND scope=?",
                    (self._agent_id, key, scope.value),
                ).fetchone()
        return _row_to_memory(row) if row else None

    # -- Type-appropriate storage shortcuts --------------------------------

    async def record_episode(
        self,
        key: str,
        content: str,
        scope: Scope = Scope.SHORT_TERM,
        ttl: int | None = None,
    ) -> Memory:
        """Store an EPISODIC memory: a thing that happened ("what happened").

        Episodes default to SHORT_TERM scope -- session-local events that the
        consolidator can later promote to durable knowledge if they prove
        reusable."""
        return await self.remember(
            key, content, scope=scope, ttl=ttl, lane=MemoryLane.EPISODIC
        )

    async def learn_fact(
        self,
        key: str,
        content: str,
        scope: Scope = Scope.LONG_TERM,
    ) -> Memory:
        """Store a SEMANTIC memory: a fact or principle ("what is true").

        Facts default to LONG_TERM scope -- decontextualised knowledge that
        should persist across sessions."""
        return await self.remember(key, content, scope=scope, lane=MemoryLane.SEMANTIC)

    async def learn_procedure(
        self,
        key: str,
        content: str,
        scope: Scope = Scope.LONG_TERM,
    ) -> Memory:
        """Store a PROCEDURAL memory: a skill or recipe ("how to do X").

        Procedures default to LONG_TERM scope -- reusable how-to knowledge."""
        return await self.remember(key, content, scope=scope, lane=MemoryLane.PROCEDURAL)

    # -- Skills (named, identity-bound procedures; D5) ---------------------

    async def learn_skill(
        self,
        skill: str,
        how_to: str,
        scope: Scope = Scope.LONG_TERM,
    ) -> Memory:
        """Accrue a reusable *skill* bound to this agent's identity.

        A skill is a PROCEDURAL memory addressed by a stable capability name
        (stored under the key ``skill:<name>``), so the agent's accrued know-how
        is enumerable as a capability profile (``accrued_skills``) and surfaces
        in the dock self-model alongside the declared ``capabilities`` from
        registration. This is the procedural-memory counterpart of the static
        capability tags an external worker registers with: those declare what the
        seat *can* do; skills record what it has *learned to* do and keeps
        reusing.

        No new store: this is exactly ``learn_procedure`` under the ``skill:``
        key convention. Re-learning the same skill name upserts the how-to in
        place (carrying the accrued reuse count), so refinement does not reset
        the skill's standing. Defaults to LONG_TERM (skills are cross-session by
        nature).

        Args:
            skill: The capability name (e.g. ``"open a PR against a worktree"``).
                Bare names are normalised to the ``skill:<name>`` key.
            how_to: The procedure -- the steps/recipe for the skill.
            scope: Storage scope; LONG_TERM by default.

        Returns:
            The stored Memory object (PROCEDURAL lane, ``skill:`` key).
        """
        name = _skill_name(skill) or skill.strip()
        if not name:
            raise ValueError("skill name must be non-empty")
        key = f"{_SKILL_KEY_PREFIX}{name}"
        return await self.remember(key, how_to, scope=scope, lane=MemoryLane.PROCEDURAL)

    async def recall_skill(
        self,
        task: str,
        scope: Scope | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        """Retrieve accrued skills relevant to ``task``, reinforcing reuse.

        Restricts PROCEDURAL retrieval to named skills (``skill:`` keys). Uses
        the existing PROCEDURAL ranking (match-strength leads, reuse breaks
        ties), and -- because it goes through ``recall`` -- *retrieving a skill
        for a relevant task bumps that skill's reuse count*. Reuse is the reward
        signal: a skill that keeps proving useful rises in the agent's profile
        without any separate reward table.

        Args:
            task: What the agent is about to do (free-text; keyword-matched
                against skill names and how-tos).
            scope: Restrict to a scope, or None for all.
            limit: Max skills to return.

        Returns:
            Matching skills, most-relevant-then-most-reused first.
        """
        # recall(lane=PROCEDURAL) is the established path; it bumps access_count
        # (the reuse/reward signal) and ranks by _lane_rank_key. We then keep
        # only the named-skill subset so this stays a skills view, not a general
        # procedure view. Pull a wider window before filtering so the skill
        # filter does not starve the result set.
        candidates = await self.recall(
            task, scope=scope, limit=max(limit * 4, limit), lane=MemoryLane.PROCEDURAL
        )
        skills = [m for m in candidates if _skill_name(m.key) is not None]
        return skills[:limit]

    async def accrued_skills(
        self,
        min_uses: int = 0,
        limit: int = 25,
    ) -> list[Memory]:
        """Enumerate this agent's accrued skills as a capability profile.

        Query-free, reuse-ranked view of the named skills (``skill:`` keys) the
        agent has learned -- the procedural-memory analogue of the declared
        ``capabilities`` list on the identity. Reuses ``_top_lane_blocks`` (which
        ranks PROCEDURAL by reuse then recency and does NOT perturb access stats),
        so reading the profile never inflates the very reuse counts it reports.

        Args:
            min_uses: Only return skills reused at least this many times (0 = all
                learned skills, including never-yet-reused ones).
            limit: Max skills to return.

        Returns:
            Skills ranked by reuse (most-relied-on capability first).
        """
        blocks = self._top_lane_blocks(MemoryLane.PROCEDURAL, limit=max(limit * 2, limit))
        skills = [
            m for m in blocks
            if _skill_name(m.key) is not None and m.access_count >= min_uses
        ]
        return skills[:limit]

    # -- Verification loop (verify-before-done; D8) -----------------------

    async def verify_before_done(
        self,
        task_id: str,
        result_text: str,
        *,
        code_targets: list[str | Path] | None = None,
        dock_home: str | Path | None = None,
        audit_timeout: int = 120,
    ) -> dict[str, Any]:
        """Run a self-verification step before this agent marks work done.

        This is the verify-before-completion circuit the seat lacked: the
        runtime recorded a task result and moved on without ever checking
        whether the result is actually completed work rather than a provider
        error string or an unverified claim. D8 closes that loop by reusing the
        verification machinery the repo already ships:

        - For *code* work (when ``code_targets`` names files the task touched),
          it runs the canonical ``dual_audit.DualAudit`` -- the decorrelated
          two-model (Claude+Codex) audit the ``dual-audit`` skill drives. A
          blocking finding (a ``critical``/``high`` severity agreement, where
          both models independently flag the same issue) fails verification.
          DualAudit already self-skips its Claude leg inside a nested Claude
          session (``CLAUDECODE``) and its Codex leg when ``codex`` is absent,
          so this degrades to "no blocking findings" rather than fabricating a
          verdict it cannot produce.
        - For *non-code* work, it runs a deterministic structural self-check:
          the result must be substantive (not the empty/error-prefixed strings
          the runtime already guards against marking as success) and must carry
          its own evidence. This is the ``verification-loop`` "evidence before
          assertions" flavour, run in-process with no extra model call.

        The verdict is recorded as an EPISODIC ``verification:<task_id>`` memory
        (so the agent's own history shows what it checked and what it found) and
        is mirrored to the agent's dock ``last_receipt.json`` -- the same
        continuity surface ``conductor_pass``/``last_receipt`` already use --
        so the most recent verification survives across runs. Best-effort and
        fully isolated: a verifier failure never raises into the act path; it
        records ``status="error"`` and lets the caller decide.

        Args:
            task_id: The task being verified (keys the memory + receipt).
            result_text: The work product to verify.
            code_targets: Files the task wrote/changed, to route through
                ``dual_audit``. None/empty -> structural self-check only.
            dock_home: Override the dock root (tests pass a tmp ``~/.dharma``).
            audit_timeout: Per-model timeout handed to ``DualAudit``.

        Returns:
            A verdict dict: ``{"verified": bool, "status": str, "mode": str,
            "reason": str, "blocking_findings": list, "checked_at": iso}``.
            ``status`` is one of ``passed`` / ``failed`` / ``error``.
        """
        checked_at = datetime.now(timezone.utc).isoformat()
        verdict: dict[str, Any] = {
            "task_id": task_id,
            "verified": False,
            "status": "error",
            "mode": "none",
            "reason": "",
            "blocking_findings": [],
            "checked_at": checked_at,
        }
        try:
            normalized = (result_text or "").strip()
            # Structural gate first: an empty or error-prefixed result is never
            # "completed work" regardless of mode -- it fails before any audit.
            if not normalized or _looks_like_error_result(normalized):
                verdict.update(
                    status="failed",
                    mode="structural",
                    reason="empty or error-prefixed result is not completed work",
                )
            elif code_targets:
                # Code work: route through the decorrelated dual-process audit.
                from dharma_swarm.dual_audit import DualAudit

                report = await DualAudit(timeout=audit_timeout).run(*code_targets)
                blocking = [
                    f for f in report.agreements
                    if str(f.get("severity", "")).lower() in ("critical", "high")
                ]
                verdict["blocking_findings"] = blocking
                if blocking:
                    verdict.update(
                        status="failed",
                        mode="dual_audit",
                        reason=(
                            f"{len(blocking)} blocking finding(s) both models agreed on: "
                            + "; ".join(
                                f"{f.get('location', '?')}:{f.get('title', '?')}"
                                for f in blocking[:3]
                            )
                        ),
                    )
                else:
                    verdict.update(
                        status="passed",
                        verified=True,
                        mode="dual_audit",
                        reason=(
                            f"dual audit clean ({len(report.agreements)} agreed, "
                            f"{len(report.claude_only)}+{len(report.codex_only)} single-model)"
                        ),
                    )
            else:
                # Non-code work: deterministic evidence self-check.
                verdict.update(
                    status="passed",
                    verified=True,
                    mode="structural",
                    reason="substantive result with no error signature",
                )

            # Record the verdict into the agent's own episodic history so its
            # self-model and recall reflect what it verified, not just what it
            # claimed. Reuse the existing EPISODIC lane; no new store.
            try:
                await self.record_episode(
                    f"verification:{task_id}",
                    f"[{verdict['status']}/{verdict['mode']}] {verdict['reason']}"[:500],
                )
            except Exception as mem_exc:  # pragma: no cover - best effort
                logger.debug("verify_before_done memory record failed: %s", mem_exc)

            # Mirror the latest verdict to the dock continuity surface
            # (last_receipt.json), the same file conductor continuity uses.
            self._write_verification_receipt(verdict, dock_home=dock_home)

        except Exception as exc:  # pragma: no cover - verifier never raises out
            logger.debug("verify_before_done error: %s", exc)
            verdict.update(status="error", reason=str(exc)[:200])
        return verdict

    def _write_verification_receipt(
        self,
        verdict: dict[str, Any],
        *,
        dock_home: str | Path | None = None,
    ) -> None:
        """Append the latest verification verdict to the dock ``last_receipt``.

        Writes to ``<dock>/last_receipt.json`` under a ``last_verification``
        key, preserving any existing receipt fields. This is the continuity
        surface (``last_receipt.json`` / ``conductor_pass``) the seat already
        uses to carry the most-recent run state across wakes -- the verification
        verdict rides the same channel rather than minting a new receipt file.
        Best-effort: a dock/IO problem must never fail verification.
        """
        try:
            dock = self._dock_dir(dock_home)
            dock.mkdir(parents=True, exist_ok=True)
            receipt_path = dock / "last_receipt.json"
            existing: dict[str, Any] = {}
            if receipt_path.exists():
                try:
                    existing = json.loads(receipt_path.read_text())
                    if not isinstance(existing, dict):
                        existing = {}
                except (json.JSONDecodeError, OSError):
                    existing = {}
            existing["last_verification"] = verdict
            receipt_path.write_text(json.dumps(existing, indent=2, default=str))
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("verification receipt write failed: %s", exc)

    async def forget(self, key: str, scope: Scope | None = None) -> bool:
        """Explicitly delete a memory.

        Args:
            key: The memory key to delete.
            scope: If provided, only delete from this scope.
                   If None, delete from all scopes.

        Returns:
            True if at least one memory was deleted.
        """
        with self._lock:
            conn = self._get_conn()

            if scope == Scope.SHARED or scope is None:
                shared_deleted = conn.execute(
                    "DELETE FROM shared_memories WHERE key=?",
                    (key,),
                ).rowcount

            if scope and scope != Scope.SHARED:
                deleted = conn.execute(
                    "DELETE FROM memories WHERE agent_id=? AND key=? AND scope=?",
                    (self._agent_id, key, scope.value),
                ).rowcount
            elif scope is None:
                deleted = conn.execute(
                    "DELETE FROM memories WHERE agent_id=? AND key=?",
                    (self._agent_id, key),
                ).rowcount
            else:
                deleted = 0

            conn.commit()

        total = deleted + (shared_deleted if scope in (Scope.SHARED, None) else 0)
        return total > 0

    async def share(
        self,
        key: str,
        content: str,
        tags: str = "",
    ) -> Memory:
        """Write to shared memory (all agents can see).

        Cross-agent pattern sharing: when Agent A solves problem X,
        it calls share("solved:X", strategy). When Agent B faces X,
        recall("solved:X", scope=SHARED) surfaces A's strategy.

        Args:
            key: Unique key for this shared memory.
            content: The content to share.
            tags: Comma-separated tags for discoverability.

        Returns:
            The stored Memory object.
        """
        now = time.time()

        with self._lock:
            conn = self._get_conn()

            # Enforce shared limit
            count = conn.execute(
                "SELECT COUNT(*) FROM shared_memories"
            ).fetchone()[0]
            if count >= self.MAX_SHARED:
                # Remove oldest
                conn.execute(
                    """DELETE FROM shared_memories WHERE id IN (
                       SELECT id FROM shared_memories ORDER BY created_at ASC LIMIT 1
                    )"""
                )

            conn.execute(
                """INSERT INTO shared_memories (agent_id, key, content, created_at, tags)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       content = excluded.content,
                       agent_id = excluded.agent_id,
                       created_at = excluded.created_at,
                       tags = excluded.tags
                """,
                (self._agent_id, key, content, now, tags),
            )
            conn.commit()

        return Memory(
            agent_id=self._agent_id,
            key=key,
            content=content,
            scope=Scope.SHARED,
            created_at=now,
            accessed_at=now,
            tags=tags,
        )

    async def get_context(self, budget_tokens: int = 2000) -> str:
        """Build working context from most relevant memories.

        Prioritizes:
        1. Working memory (always included first)
        2. Recently accessed short-term memories
        3. High-frequency long-term memories
        4. Relevant shared memories

        Stays within the token budget (estimated at ~4 chars/token).

        Args:
            budget_tokens: Maximum tokens for the context string.

        Returns:
            Formatted markdown string ready for prompt injection.
        """
        chars_budget = budget_tokens * 4  # ~4 chars per token estimate
        lines: list[str] = [f"## Memory Context ({self._agent_id})"]
        used = len(lines[0])

        with self._lock:
            conn = self._get_conn()

            # 1. Working memory (sorted by importance-proxy: access_count)
            working = conn.execute(
                """SELECT * FROM memories
                   WHERE agent_id=? AND scope='working'
                   ORDER BY access_count DESC, accessed_at DESC""",
                (self._agent_id,),
            ).fetchall()

            if working:
                lines.append("\n### Working Memory")
                used += 20
                for row in working:
                    mem = _row_to_memory(row)
                    if mem.is_expired:
                        continue
                    line = f"- **{mem.key}**: {mem.content}"
                    if used + len(line) + 1 > chars_budget:
                        break
                    lines.append(line)
                    used += len(line) + 1

            # 2. Recent short-term
            short_term = conn.execute(
                """SELECT * FROM memories
                   WHERE agent_id=? AND scope='short_term'
                   ORDER BY accessed_at DESC LIMIT 10""",
                (self._agent_id,),
            ).fetchall()

            if short_term and used < chars_budget - 100:
                lines.append("\n### Recent")
                used += 12
                for row in short_term:
                    mem = _row_to_memory(row)
                    if mem.is_expired:
                        continue
                    line = f"- {mem.key}: {mem.content[:200]}"
                    if used + len(line) + 1 > chars_budget:
                        break
                    lines.append(line)
                    used += len(line) + 1

            # 3. High-value long-term
            long_term = conn.execute(
                """SELECT * FROM memories
                   WHERE agent_id=? AND scope='long_term'
                   ORDER BY access_count DESC, accessed_at DESC LIMIT 5""",
                (self._agent_id,),
            ).fetchall()

            if long_term and used < chars_budget - 100:
                lines.append("\n### Long-term Knowledge")
                used += 25
                for row in long_term:
                    mem = _row_to_memory(row)
                    line = f"- {mem.key}: {mem.content[:200]}"
                    if used + len(line) + 1 > chars_budget:
                        break
                    lines.append(line)
                    used += len(line) + 1

            # 4. Shared memory (most recent)
            shared = conn.execute(
                """SELECT * FROM shared_memories
                   ORDER BY created_at DESC LIMIT 5"""
            ).fetchall()

            if shared and used < chars_budget - 100:
                lines.append("\n### Shared (Swarm)")
                used += 20
                for row in shared:
                    mem = _shared_row_to_memory(row)
                    tag_str = f" [{mem.tags}]" if mem.tags else ""
                    line = f"- {mem.key}: {mem.content[:150]}{tag_str}"
                    if used + len(line) + 1 > chars_budget:
                        break
                    lines.append(line)
                    used += len(line) + 1

        return "\n".join(lines)

    async def consolidate(self) -> int:
        """Memory consolidation to prevent unbounded growth.

        Operations:
        1. Expire TTL-based memories
        2. Merge duplicate keys (keep most recent)
        3. Enforce per-scope limits (evict least accessed)

        Returns:
            Count of memories affected (expired + evicted).
        """
        affected = 0
        now = time.time()

        with self._lock:
            conn = self._get_conn()

            # 1. Expire TTL-based memories
            expired = conn.execute(
                """DELETE FROM memories
                   WHERE ttl IS NOT NULL
                   AND (created_at + ttl) < ?""",
                (now,),
            ).rowcount
            affected += expired

            # 2. Enforce per-scope limits
            for scope, limit in [
                (Scope.WORKING, self.MAX_WORKING),
                (Scope.SHORT_TERM, self.MAX_SHORT_TERM),
                (Scope.LONG_TERM, self.MAX_LONG_TERM),
            ]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE agent_id=? AND scope=?",
                    (self._agent_id, scope.value),
                ).fetchone()[0]

                if count > limit:
                    excess = count - limit
                    # Evict least accessed, oldest first
                    evicted = conn.execute(
                        """DELETE FROM memories WHERE id IN (
                           SELECT id FROM memories
                           WHERE agent_id=? AND scope=?
                           ORDER BY access_count ASC, accessed_at ASC
                           LIMIT ?
                        )""",
                        (self._agent_id, scope.value, excess),
                    ).rowcount
                    affected += evicted

            # 3. Promote frequently-accessed short-term to long-term
            # (access_count >= 3 and older than 1 hour)
            one_hour_ago = now - 3600
            promotable = conn.execute(
                """SELECT id, key, content, ttl, embedding_hash, lane
                   FROM memories
                   WHERE agent_id=? AND scope='short_term'
                   AND access_count >= 3 AND created_at < ?""",
                (self._agent_id, one_hour_ago),
            ).fetchall()

            for row in promotable:
                row_lane = _coerce_lane(_row_value(row, "lane")).value
                # Check if already exists in long_term (same key + same lane).
                existing = conn.execute(
                    "SELECT id FROM memories WHERE agent_id=? AND key=? AND scope='long_term' AND lane=?",
                    (self._agent_id, row["key"], row_lane),
                ).fetchone()
                if existing:
                    # Update existing long-term memory
                    conn.execute(
                        "UPDATE memories SET content=?, accessed_at=? WHERE id=?",
                        (row["content"], now, existing["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO memories
                           (agent_id, key, content, scope, created_at, accessed_at,
                            access_count, ttl, embedding_hash, lane)
                           VALUES (?, ?, ?, 'long_term', ?, ?, 0, NULL, ?, ?)""",
                        (self._agent_id, row["key"], row["content"],
                         now, now, row["embedding_hash"], row_lane),
                    )
                # Remove from short-term
                conn.execute("DELETE FROM memories WHERE id=?", (row["id"],))
                affected += 1

            conn.commit()

        if affected > 0:
            logger.debug(
                "Consolidated %d memories for agent %s",
                affected, self._agent_id,
            )
        return affected

    async def sleep_consolidate(
        self,
        similarity_threshold: float = 0.6,
        decay_idle_days: float = 14.0,
        revive_window_days: float = 1.0,
    ) -> dict[str, int]:
        """Sleep-time consolidation pass over THIS agent's own blocks.

        The per-agent analogue of the organism-level ``SleepTimeAgent`` tick and
        the chetana decay/revive metabolic clock: instead of burning context
        window during an agent run, the store reorganises itself between runs.
        It reuses the existing ``consolidate()`` (TTL expiry, scope-limit
        eviction, short->long promotion) and adds the decay/revive reorg that
        ``consolidate()`` does not do, using the SAME near-duplicate metric the
        ``SleepTimeAgent`` uses on OrganismMemory:

        1. base       -- run ``consolidate()`` (TTL / limits / promotion).
        2. merge      -- within (scope, lane), fold near-duplicate blocks
                         (Jaccard >= ``similarity_threshold``) into the most
                         recently accessed one, then delete the stale duplicate.
                         (chetana "stale is the trigger for re-integration".)
        3. decay      -- demote long-idle, never-reused WORKING blocks down to
                         SHORT_TERM so the hot tier stays the live working set.
        4. revive     -- re-surface a recently rediscovered (accessed within
                         ``revive_window_days``) SHORT_TERM/LONG_TERM block back
                         into WORKING, the decay/revive counterpart to step 3.

        Every phase is best-effort and additive: nothing here can lose a block's
        content (merge keeps the survivor's content; decay/revive only move a
        block between scopes). Returns a per-phase count dict.

        Args:
            similarity_threshold: Jaccard cutoff for treating two blocks as
                near-duplicates (matches ``SleepTimeAgent`` default 0.6).
            decay_idle_days: A WORKING block untouched for this many days and
                never reused (access_count == 0) is demoted to SHORT_TERM.
            revive_window_days: A non-WORKING block accessed within this many
                days is revived to WORKING (the rediscovery signal).
        """
        base = await self.consolidate()
        now = time.time()
        merged = 0
        decayed = 0
        revived = 0

        with self._lock:
            conn = self._get_conn()

            # -- Phase 2: merge near-duplicate own blocks ------------------
            rows = conn.execute(
                "SELECT * FROM memories WHERE agent_id=? AND scope!=?",
                (self._agent_id, Scope.SHARED.value),
            ).fetchall()
            groups: dict[tuple[str, str], list[Memory]] = {}
            for row in rows:
                mem = _row_to_memory(row)
                if mem.is_expired:
                    continue
                groups.setdefault((mem.scope.value, mem.lane.value), []).append(mem)

            for group in groups.values():
                if len(group) < 2:
                    continue
                # Newest-accessed first: it is the survivor of any merge.
                group.sort(key=lambda m: m.accessed_at, reverse=True)
                dead_ids: set[int] = set()
                for i, survivor in enumerate(group):
                    if survivor.id in dead_ids:
                        continue
                    for other in group[i + 1:]:
                        if other.id in dead_ids:
                            continue
                        if _jaccard_words(
                            f"{survivor.key} {survivor.content}",
                            f"{other.key} {other.content}",
                        ) >= similarity_threshold:
                            # Survivor inherits the larger access_count so the
                            # merged block reflects total historical reuse.
                            conn.execute(
                                "UPDATE memories SET access_count=? WHERE id=?",
                                (max(survivor.access_count, other.access_count), survivor.id),
                            )
                            conn.execute("DELETE FROM memories WHERE id=?", (other.id,))
                            dead_ids.add(other.id)
                            merged += 1

            # -- Phase 3: decay long-idle WORKING blocks -------------------
            idle_cutoff = now - decay_idle_days * 86400.0
            decay_rows = conn.execute(
                """SELECT id FROM memories
                   WHERE agent_id=? AND scope=? AND access_count=0 AND accessed_at < ?""",
                (self._agent_id, Scope.WORKING.value, idle_cutoff),
            ).fetchall()
            for r in decay_rows:
                conn.execute(
                    "UPDATE memories SET scope=? WHERE id=?",
                    (Scope.SHORT_TERM.value, r["id"]),
                )
                decayed += 1

            # -- Phase 4: revive recently-rediscovered blocks --------------
            revive_cutoff = now - revive_window_days * 86400.0
            revive_rows = conn.execute(
                """SELECT id FROM memories
                   WHERE agent_id=? AND scope IN (?, ?)
                   AND access_count >= 1 AND accessed_at >= ?""",
                (self._agent_id, Scope.SHORT_TERM.value, Scope.LONG_TERM.value, revive_cutoff),
            ).fetchall()
            for r in revive_rows:
                conn.execute(
                    "UPDATE memories SET scope=? WHERE id=?",
                    (Scope.WORKING.value, r["id"]),
                )
                revived += 1

            conn.commit()

        result = {
            "base_consolidated": base,
            "merged": merged,
            "decayed": decayed,
            "revived": revived,
        }
        if merged or decayed or revived:
            logger.debug(
                "Sleep-consolidated agent %s: %s", self._agent_id, result
            )
        return result

    # -- Reflection (self-model) ------------------------------------------

    def _dock_dir(self, dock_home: str | Path | None = None) -> Path:
        """Resolve THIS agent's home dock directory.

        The dock is the canonical home for an agent's self-description files
        (``role.md``, ``state.md``, ``SOUL.md``, ``living_agent.json``) written
        by ``roaming_onboarding.onboard_roaming_agent``. ``self_model.md`` lives
        here too. The dock is keyed by the *resolved* agent_id (the same uid the
        memory store is bound to via ``for_namespace``), so the agent's memory
        and its self-model resolve to the same identity.
        """

        if dock_home is not None:
            base = Path(dock_home)
        else:
            base = Path(os.environ.get("DHARMA_HOME", Path.home() / ".dharma"))
        return base / "agents" / self._agent_id

    def _top_lane_blocks(self, lane: "MemoryLane | str", limit: int = 8) -> list["Memory"]:
        """Read this agent's most-established blocks in one cognitive lane.

        A passive, query-free, access-stat-preserving read used only by
        ``reflect_self_model``: it surfaces what the agent actually holds in a
        lane (semantic = ranked by reuse then recency; procedural = same) rather
        than what matches a keyword query, and it does NOT bump ``access_count``
        / ``accessed_at`` -- reflecting on memory must not perturb the memory.
        Persistent (SHARED is cross-agent, excluded) own blocks only. Internal
        SQL read in the same style as ``_get_own_block`` / ``_search_shared_locked``.
        """
        resolved = _coerce_lane(lane)
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT * FROM memories
                   WHERE agent_id=? AND lane=? AND scope!=?
                   ORDER BY access_count DESC, accessed_at DESC
                   LIMIT ?""",
                (self._agent_id, resolved.value, Scope.SHARED.value, limit),
            ).fetchall()
        out: list[Memory] = []
        for row in rows:
            mem = _row_to_memory(row)
            if not mem.is_expired:
                out.append(mem)
        return out

    async def reflect_self_model(
        self,
        dock_home: str | Path | None = None,
        *,
        budget_tokens: int = 1200,
    ) -> dict[str, Any]:
        """Reflect over accrued memory and (re)write ``self_model.md``.

        This is the reflection step the dock lacked: the self-model file was a
        *required* surface (the dock's reflective companion to the hand-authored
        ``SOUL.md`` and the machine-written ``living_agent.json``) but nothing in
        the repo ever performed its first write, and nothing updated it from the
        memory an agent accrues across runs. ``role.md`` / ``state.md`` are
        seeded once at onboarding and go stale; ``self_model.md`` is the surface
        that stays current because *this* method regenerates it from the live
        store.

        It reads ONLY through existing surfaces -- ``get_stats()`` (counts, lane
        distribution, latest access), ``get_context()`` (the same
        budget-bounded working/long-term projection used for prompt injection),
        and ``recall()`` (top semantic facts / procedural know-how) -- so there
        is no second read path to drift from. The dock's ``living_agent.json``
        (if present) supplies the stable identity header; everything below the
        header is derived from memory and changes as memory changes.

        The write is the metabolic counterpart to ``sleep_consolidate``: after
        the store reorganises itself between runs, the agent re-derives who it is
        from what it now holds. First call performs the required first write;
        each later call updates in place and bumps ``reflection_count`` (parsed
        back out of the previous file) so accrual across runs is observable.

        Best-effort and non-destructive: on any read failure the section is
        omitted, never half-written. Returns a small report dict
        (``{path, written, reflection_count, bytes, sections}``).
        """

        dock_dir = self._dock_dir(dock_home)
        path = dock_dir / "self_model.md"

        # Continuity: how many times have we reflected before? Parse it back out
        # of the prior file so the count survives across runs/sessions without a
        # new store. Absent / unreadable file => first reflection.
        prior_count = 0
        prior_text = ""
        try:
            if path.exists():
                prior_text = path.read_text(encoding="utf-8")
                m = re.search(r"reflection_count:\s*(\d+)", prior_text)
                if m:
                    prior_count = int(m.group(1))
        except Exception:
            prior_count = 0
        reflection_count = prior_count + 1

        # Stable identity header from the dock's living_agent.json, if onboarded.
        identity: dict[str, Any] = {}
        try:
            la_path = dock_dir / "living_agent.json"
            if la_path.exists():
                identity = json.loads(la_path.read_text(encoding="utf-8")) or {}
        except Exception:
            identity = {}

        # All three reads go through existing public surfaces.
        try:
            stats = await self.get_stats()
        except Exception:
            stats = {"agent_id": self._agent_id}
        try:
            context = await self.get_context(budget_tokens=budget_tokens)
        except Exception:
            context = ""
        # The most established facts (semantic) and most-reused know-how
        # (procedural) the agent has accrued about its own work. Read WITHOUT a
        # keyword query (reflection must surface what the agent actually holds,
        # not what matches a guessed query) and WITHOUT bumping access stats (a
        # passive observation of self must not perturb the memory it observes,
        # so consecutive reflections over an unchanged store stay identical).
        try:
            semantic = self._top_lane_blocks(MemoryLane.SEMANTIC, limit=8)
        except Exception:
            semantic = []
        try:
            procedural = self._top_lane_blocks(MemoryLane.PROCEDURAL, limit=8)
        except Exception:
            procedural = []

        now_iso = datetime.now(timezone.utc).isoformat()
        sections: list[str] = []

        # Front-matter carries the machine-trackable reflection state.
        fm = [
            "---",
            f"agent_uid: {identity.get('agent_uid', self._agent_id)}",
            f"memory_namespace: {identity.get('memory_namespace', f'agent:{self._agent_id}')}",
            f"reflection_count: {reflection_count}",
            f"last_reflected_at: {now_iso}",
            "source: agent_memory_manager.reflect_self_model",
            "---",
            "",
        ]
        sections.append("\n".join(fm))

        title = identity.get("callsign") or identity.get("agent_uid") or self._agent_id
        sections.append(f"# Self-Model — {title}")
        sections.append(
            "_Reflective self-model, regenerated from accrued memory between "
            "runs. The hand-authored `SOUL.md` is who this seat is by intent; "
            "this file is who it has become by accrual. Derived, not authored._"
        )

        # 1. Identity header (stable facts, from the dock).
        if identity:
            id_lines = ["## Identity"]
            for label, key in (
                ("role", "role"),
                ("serial", "serial"),
                ("department", "department"),
                ("squad", "squad_id"),
                ("team", "team_id"),
            ):
                val = identity.get(key)
                if val:
                    id_lines.append(f"- **{label}**: {val}")
            emb = identity.get("current_embodiment") or {}
            if emb.get("model"):
                id_lines.append(f"- **model**: {emb.get('model')}")
            if emb.get("harness"):
                id_lines.append(f"- **harness**: {emb.get('harness')}")
            inv = identity.get("identity_invariant") or {}
            if inv.get("authority_floor"):
                id_lines.append(f"- **authority floor**: {inv.get('authority_floor')}")
            sections.append("\n".join(id_lines))

        # 2. What I have accrued (memory shape — observability of growth).
        shape = ["## What I have accrued"]
        shape.append(
            f"- total memories: {stats.get('total_count', 0)} "
            f"(working {stats.get('working_count', 0)}, "
            f"short-term {stats.get('short_term_count', 0)}, "
            f"long-term {stats.get('long_term_count', 0)})"
        )
        lane_counts = stats.get("lane_counts") or {}
        if lane_counts:
            shape.append(
                "- by cognitive lane: "
                + ", ".join(f"{k} {v}" for k, v in sorted(lane_counts.items()))
            )
        if stats.get("latest_access"):
            shape.append(f"- most recent activity: {stats.get('latest_access')}")
        # Note: reflection_count is reflection-act metadata, not self-model
        # substance -- it lives only in the front-matter so the body stays a
        # pure function of memory state (and the idempotence check is honest).
        sections.append("\n".join(shape))

        # 3. What I know to be true (established semantic memory).
        if semantic:
            facts = ["## What I know to be true"]
            for mem in semantic:
                facts.append(f"- **{mem.key}**: {mem.content.strip()[:240]}")
            sections.append("\n".join(facts))

        # 4. Accrued skills (named, identity-bound capabilities; D5). The
        #    procedural-memory counterpart of the declared `capabilities` list on
        #    the registration: skills the seat has *learned* and keeps reusing,
        #    ranked by reuse (the reward signal). Surfacing reuse counts here is
        #    how the accrued capability profile becomes part of the identity's
        #    self-model, not just rows in a store.
        skills = [m for m in procedural if _skill_name(m.key) is not None]
        other_procedures = [m for m in procedural if _skill_name(m.key) is None]
        if skills:
            cap = ["## Accrued skills"]
            for mem in skills:
                name = _skill_name(mem.key) or mem.key
                uses = mem.access_count
                reuse = f" (reused {uses}x)" if uses else " (new)"
                cap.append(f"- **{name}**{reuse}: {mem.content.strip()[:240]}")
            sections.append("\n".join(cap))

        # 5. How I work (other accrued procedural know-how, not named skills).
        if other_procedures:
            how = ["## How I work"]
            for mem in other_procedures:
                how.append(f"- **{mem.key}**: {mem.content.strip()[:240]}")
            sections.append("\n".join(how))

        # 5. Live working context (the same projection used for prompt
        #    injection) -- what is currently in focus.
        if context and context.strip():
            sections.append("## Currently in focus\n" + context.strip())

        body = "\n\n".join(s for s in sections if s.strip()) + "\n"

        written = False
        try:
            dock_dir.mkdir(parents=True, exist_ok=True)
            # Idempotence: if nothing of substance changed, do not rewrite (the
            # only diff would be the timestamp/count). Compare everything below
            # the front-matter so reruns on an unchanged store are no-ops.
            def _below_fm(text: str) -> str:
                parts = text.split("---", 2)
                return parts[2] if len(parts) >= 3 else text

            if not prior_text or _below_fm(prior_text).strip() != _below_fm(body).strip():
                path.write_text(body, encoding="utf-8")
                written = True
            else:
                # Substance unchanged; keep prior file (and its count) intact.
                reflection_count = prior_count
        except Exception as exc:
            logger.debug(
                "reflect_self_model write failed for %s: %s", self._agent_id, exc
            )

        result = {
            "path": str(path),
            "written": written,
            "reflection_count": reflection_count,
            "bytes": len(body.encode("utf-8")),
            "sections": [s.splitlines()[0] for s in sections if s.strip().startswith("#")],
        }
        if written:
            logger.debug("Reflected self-model for %s: %s", self._agent_id, result)
        return result

    async def get_stats(self) -> dict[str, Any]:
        """Return memory statistics for observability."""
        with self._lock:
            conn = self._get_conn()

            stats: dict[str, Any] = {"agent_id": self._agent_id}

            for scope in (Scope.WORKING, Scope.SHORT_TERM, Scope.LONG_TERM):
                count = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE agent_id=? AND scope=?",
                    (self._agent_id, scope.value),
                ).fetchone()[0]
                stats[f"{scope.value}_count"] = count

            stats["shared_count"] = conn.execute(
                "SELECT COUNT(*) FROM shared_memories"
            ).fetchone()[0]

            stats["total_count"] = sum(
                stats.get(f"{s.value}_count", 0)
                for s in (Scope.WORKING, Scope.SHORT_TERM, Scope.LONG_TERM)
            ) + stats["shared_count"]

            # Per-lane counts -- observability of the episodic/semantic/procedural
            # separation for this agent's private store.
            lane_counts = {lane.value: 0 for lane in COGNITIVE_LANES}
            for row in conn.execute(
                "SELECT lane, COUNT(*) AS n FROM memories WHERE agent_id=? GROUP BY lane",
                (self._agent_id,),
            ).fetchall():
                lane_counts[_coerce_lane(row["lane"]).value] = (
                    lane_counts.get(_coerce_lane(row["lane"]).value, 0) + row["n"]
                )
            stats["lane_counts"] = lane_counts

            # Most recent memory
            latest = conn.execute(
                """SELECT accessed_at FROM memories
                   WHERE agent_id=? ORDER BY accessed_at DESC LIMIT 1""",
                (self._agent_id,),
            ).fetchone()
            if latest:
                stats["latest_access"] = datetime.fromtimestamp(
                    latest["accessed_at"], tz=timezone.utc
                ).isoformat()

        return stats

    async def list_keys(self, scope: Scope | None = None) -> list[str]:
        """List all memory keys, optionally filtered by scope."""
        with self._lock:
            conn = self._get_conn()
            if scope == Scope.SHARED:
                rows = conn.execute(
                    "SELECT key FROM shared_memories ORDER BY key"
                ).fetchall()
            elif scope:
                rows = conn.execute(
                    "SELECT key FROM memories WHERE agent_id=? AND scope=? ORDER BY key",
                    (self._agent_id, scope.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key FROM memories WHERE agent_id=? ORDER BY key",
                    (self._agent_id,),
                ).fetchall()
        return [r["key"] for r in rows]

    # -- Internal helpers --------------------------------------------------

    def _enforce_limit(self, conn: sqlite3.Connection, scope: Scope) -> None:
        """Enforce per-scope memory limits. Evicts oldest/least-accessed."""
        limit_map = {
            Scope.WORKING: self.MAX_WORKING,
            Scope.SHORT_TERM: self.MAX_SHORT_TERM,
            Scope.LONG_TERM: self.MAX_LONG_TERM,
        }
        limit = limit_map.get(scope)
        if limit is None:
            return

        count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE agent_id=? AND scope=?",
            (self._agent_id, scope.value),
        ).fetchone()[0]

        if count >= limit:
            # Evict 10% of the limit to avoid evicting on every insert
            evict_count = max(1, limit // 10)
            conn.execute(
                """DELETE FROM memories WHERE id IN (
                   SELECT id FROM memories
                   WHERE agent_id=? AND scope=?
                   ORDER BY access_count ASC, accessed_at ASC
                   LIMIT ?
                )""",
                (self._agent_id, scope.value, evict_count),
            )

    def _search_shared_locked(
        self,
        conn: sqlite3.Connection,
        keywords: list[str],
        limit: int,
    ) -> list[Memory]:
        """Search shared memories. Must be called with self._lock held."""
        rows = conn.execute(
            "SELECT * FROM shared_memories ORDER BY created_at DESC"
        ).fetchall()

        results: list[Memory] = []
        for row in rows:
            mem = _shared_row_to_memory(row)
            score = _keyword_score(keywords, mem.key, mem.content)
            if mem.tags:
                # Boost score if keywords match tags
                tag_score = _keyword_score(keywords, mem.tags, "")
                score += tag_score * 0.5
            if score > 0:
                mem._score = score  # type: ignore[attr-defined]
                results.append(mem)

        results.sort(key=lambda m: getattr(m, "_score", 0), reverse=True)
        return results[:limit]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


# Canonical "this is an error string, not completed work" prefixes -- the same
# set ``agent_runner._looks_like_provider_failure`` guards task results with.
# Kept in sync deliberately and duplicated (not imported) because agent_runner
# imports THIS module; the dependency must not point back. Used by the D8
# verify-before-done structural gate so the verifier and the runtime agree on
# what counts as a non-result.
_ERROR_RESULT_PREFIXES = (
    "error",
    "api error:",
    "timeout: exceeded limit",
    "not logged in · please run /login",
    "openrouter error:",
    "no openrouter_api_key set",
    "credit balance is too low",
    "credit balance",
    "insufficient_quota",
    "rate_limit_exceeded",
    "you exceeded your current quota",
    "billing hard limit",
)


def _looks_like_error_result(content: str) -> bool:
    """True when ``content`` reads as a provider/error string, not real work.

    Mirrors ``agent_runner._looks_like_provider_failure``: empty content fails;
    short content containing any error prefix fails; any content starting with
    an error prefix fails."""
    normalized = (content or "").strip().lower()
    if not normalized:
        return True
    if len(normalized) < 200 and any(p in normalized for p in _ERROR_RESULT_PREFIXES):
        return True
    return any(normalized.startswith(p) for p in _ERROR_RESULT_PREFIXES)


def _content_hash(content: str) -> str:
    """SHA-256 hash of content for dedup and future embedding keying."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _extract_keywords(query: str) -> list[str]:
    """Extract meaningful keywords from a query string."""
    # Split on whitespace and punctuation, lowercase, filter short words
    words = re.findall(r"[a-zA-Z0-9_]+", query.lower())
    # Filter out very short words (< 2 chars) and common stop words
    stop_words = {"a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "and", "or"}
    return [w for w in words if len(w) >= 2 and w not in stop_words]


def _keyword_score(keywords: list[str], key: str, content: str) -> int:
    """Score a memory by keyword match count."""
    text = f"{key} {content}".lower()
    return sum(1 for kw in keywords if kw in text)


def _jaccard_words(a: str, b: str) -> float:
    """Word-level Jaccard similarity, the same near-duplicate metric the
    organism-level ``SleepTimeAgent`` uses to fold duplicate entities. Reused
    here (not re-imported, to keep this module's lean stdlib-only dependency
    footprint) so ``sleep_consolidate`` merges per-agent blocks by exactly the
    measure the organism uses on its own memory."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    union = len(words_a | words_b)
    return (len(words_a & words_b) / union) if union else 0.0


def _row_value(row: sqlite3.Row, name: str, default: Any = None) -> Any:
    """Safely read a column from a Row, tolerating older rows that predate it."""
    try:
        return row[name]
    except (IndexError, KeyError):
        return default


def _row_to_memory(row: sqlite3.Row) -> Memory:
    """Convert a SQLite Row from the memories table to a Memory object."""
    return Memory(
        id=row["id"],
        agent_id=row["agent_id"],
        key=row["key"],
        content=row["content"],
        scope=Scope(row["scope"]),
        created_at=row["created_at"],
        accessed_at=row["accessed_at"],
        access_count=row["access_count"],
        ttl=row["ttl"],
        embedding_hash=row["embedding_hash"] or "",
        lane=_coerce_lane(_row_value(row, "lane")),
    )


def _lane_rank_key(mem: Memory) -> tuple:
    """Type-appropriate ranking key for a recalled memory.

    The primary sort is always keyword-match score (relevance must come first).
    Within equal relevance, the lane decides what "best" means:

      - EPISODIC   : recency (accessed_at) is the strong signal, then reuse.
      - SEMANTIC   : reuse (access_count) is the strong signal, then recency.
      - PROCEDURAL : match strength leads (already in score), then reuse, then
                     recency -- a procedure's value is its fit, not its age.
      - WORKING/other: the original behaviour (recency then reuse).

    Returned as a tuple sorted descending, so larger == better on every field.

    Recency/reuse are read from the PRE-access snapshot (``_rank_recency`` /
    ``_rank_reuse``) when present, because ``recall`` stamps the current access
    onto every match before sorting; ranking on the live values would flatten
    the very recency signal episodic retrieval needs. Falls back to live values
    for results that never went through the access touch (e.g. shared memory).
    """
    score = getattr(mem, "_score", 0)
    recency = getattr(mem, "_rank_recency", mem.accessed_at)
    reuse = getattr(mem, "_rank_reuse", mem.access_count)
    if mem.lane == MemoryLane.SEMANTIC:
        return (score, reuse, recency)
    if mem.lane == MemoryLane.PROCEDURAL:
        return (score, reuse, recency)
    # EPISODIC and WORKING (and any fallback): recency-first.
    return (score, recency, reuse)


def _shared_row_to_memory(row: sqlite3.Row) -> Memory:
    """Convert a SQLite Row from shared_memories table to a Memory object."""
    return Memory(
        id=row["id"],
        agent_id=row["agent_id"],
        key=row["key"],
        content=row["content"],
        scope=Scope.SHARED,
        created_at=row["created_at"],
        accessed_at=row["created_at"],
        tags=row["tags"] or "",
    )


__all__ = [
    "AgentMemoryManager",
    "Memory",
    "Scope",
    "ALL_SCOPES",
    "MemoryLane",
    "COGNITIVE_LANES",
]
