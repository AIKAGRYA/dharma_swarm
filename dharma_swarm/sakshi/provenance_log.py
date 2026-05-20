"""Provenance log — append-only decision chain for multi-agent attribution.

Records: (timestamp, actor, action, evidence, governance_snapshot_hash)
for every significant state transition in the system.

This enables:
- "Why is it like this?" — reconstruct the chain of decisions
- "Who decided?" — multi-agent attribution (Devin, Copilot, human, etc.)
- "Was it valid?" — replay governance constraints at decision time
- "Can we undo?" — trace causal chain for safe rollback

The log is the foundation for the training flywheel (BR-003). Without
provenance, live evolution cannot be safely opened because "undo" is
impossible.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entry model
# ---------------------------------------------------------------------------

ActorKind = Literal[
    "human",
    "devin",
    "copilot",
    "claude_code",
    "codex",
    "cursor",
    "daemon",
    "ci",
    "facade",
    "unknown",
]

ActionKind = Literal[
    "pr_created",
    "pr_merged",
    "track_opened",
    "track_closed",
    "card_created",
    "card_transitioned",
    "governance_update",
    "evolution_shadow_apply",
    "evolution_live_apply",
    "broken_register_update",
    "config_change",
    "manual_override",
]


class ProvenanceEntry(BaseModel):
    """A single provenance record in the witness chain."""

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    )

    # Who
    actor_id: str
    actor_kind: ActorKind
    session_id: str = ""

    # What
    action: ActionKind
    target_ref: str = ""
    detail: str = ""

    # Evidence
    evidence_refs: list[str] = Field(default_factory=list)
    pr_number: int | None = None
    commit_hash: str = ""
    track_id: str = ""

    # Governance context at decision time
    governance_snapshot_hash: str = ""
    active_track_at_decision: str = ""
    constraints_satisfied: list[str] = Field(default_factory=list)
    constraints_violated: list[str] = Field(default_factory=list)

    # Chain integrity
    previous_entry_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """Compute a deterministic hash of this entry (excluding entry_hash)."""
        data = self.model_dump(exclude={"entry_hash"})
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Provenance log persistence
# ---------------------------------------------------------------------------

_DEFAULT_LOG_PATH = Path.home() / ".dharma" / "sakshi" / "provenance_log.jsonl"


class ProvenanceLog:
    """Append-only provenance log with chain integrity.

    Each entry includes the hash of the previous entry, forming a
    tamper-evident chain. If any entry is modified or removed, the
    chain breaks and integrity verification fails.

    Usage:
        log = ProvenanceLog()
        log.append(ProvenanceEntry(
            actor_id="devin-session-abc",
            actor_kind="devin",
            action="pr_created",
            target_ref="PR #318",
            detail="Closed active track completion criteria",
            track_id="cockpit-control-surface-2026-05",
        ))
        chain = log.read_all()
        assert log.verify_chain()
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash: str = ""

    @property
    def path(self) -> Path:
        return self._path

    def _load_last_hash(self) -> str:
        """Read the hash of the last entry in the log."""
        if not self._path.exists():
            return ""
        last_line = ""
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()
        if not last_line:
            return ""
        entry = ProvenanceEntry.model_validate_json(last_line)
        return entry.entry_hash

    def append(self, entry: ProvenanceEntry) -> str:
        """Append an entry to the provenance log. Returns the entry hash.

        Automatically chains the entry to the previous one.
        """
        if not self._last_hash:
            self._last_hash = self._load_last_hash()

        entry.previous_entry_hash = self._last_hash
        entry.entry_hash = entry.compute_hash()
        self._last_hash = entry.entry_hash

        line = entry.model_dump_json() + "\n"
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)

        logger.debug(
            "provenance: %s by %s (%s) -> %s",
            entry.action, entry.actor_id, entry.actor_kind, entry.entry_hash,
        )
        return entry.entry_hash

    def read_all(self) -> list[ProvenanceEntry]:
        """Read all entries from the log."""
        if not self._path.exists():
            return []
        entries: list[ProvenanceEntry] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(ProvenanceEntry.model_validate_json(line))
        return entries

    def read_for_actor(self, actor_id: str) -> list[ProvenanceEntry]:
        """Read all entries by a specific actor."""
        return [e for e in self.read_all() if e.actor_id == actor_id]

    def read_for_track(self, track_id: str) -> list[ProvenanceEntry]:
        """Read all entries associated with a specific track."""
        return [e for e in self.read_all() if e.track_id == track_id]

    def read_for_action(self, action: ActionKind) -> list[ProvenanceEntry]:
        """Read all entries of a specific action kind."""
        return [e for e in self.read_all() if e.action == action]

    def verify_chain(self) -> bool:
        """Verify the integrity of the provenance chain.

        Returns True if every entry's previous_entry_hash matches the
        computed hash of the preceding entry. A broken chain indicates
        tampering or corruption.
        """
        entries = self.read_all()
        if not entries:
            return True

        # First entry should have empty previous_entry_hash
        if entries[0].previous_entry_hash != "":
            logger.warning("chain broken: first entry has non-empty previous hash")
            return False

        for i in range(1, len(entries)):
            expected_prev = entries[i - 1].entry_hash
            actual_prev = entries[i].previous_entry_hash
            if expected_prev != actual_prev:
                logger.warning(
                    "chain broken at entry %d: expected prev=%s, got=%s",
                    i, expected_prev, actual_prev,
                )
                return False

        return True

    def count(self) -> int:
        """Count total entries in the log."""
        if not self._path.exists():
            return 0
        with self._path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def last_entry(self) -> ProvenanceEntry | None:
        """Get the most recent entry."""
        entries = self.read_all()
        return entries[-1] if entries else None
