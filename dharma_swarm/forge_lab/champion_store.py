"""Concurrent-safe persistence for research-only Forge Lab champions."""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from dharma_swarm.forge_lab.champion_metadata import (
    CHAMPION_SCHEMA,
    ChampionConflict,
    ChampionStoreError,
    build_shadow_champion,
    json_copy as _json_copy,
    utc_now as _utc_now,
    validate_shadow_champion,
)
from dharma_swarm.forge_lab.ids import (
    content_digest,
)

STATE_SCHEMA = "forge_lab.shadow_champion_state.v1"
HISTORY_SCHEMA = "forge_lab.shadow_champion_transition.v1"


class ChampionStore:
    """Atomic category-local champion state with revision/CAS semantics."""

    def __init__(self, root: Path | str, *, category: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", category or ""):
            raise ChampionStoreError("category must be a filesystem-safe identifier")
        self.root = Path(root)
        self.category = category
        self.category_root = self.root / category
        self.state_path = self.category_root / "champion.json"
        self.history_path = self.category_root / "champion_history.jsonl"
        self.lock_path = self.category_root / ".champion.lock"

    def load(self) -> dict[str, Any]:
        """Load an atomically published state; missing state means revision 0."""
        return self._read_unlocked()

    def compare_and_swap(
        self,
        *,
        expected_revision: int,
        champion: Mapping[str, Any],
        reason: str = "paired_shadow_selection",
    ) -> dict[str, Any]:
        """Publish ``champion`` iff the frozen incumbent revision still matches."""
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ChampionStoreError("expected_revision must be a non-negative integer")
        candidate = _json_copy(champion)
        validate_shadow_champion(candidate)
        if candidate["category"] != self.category:
            raise ChampionStoreError("champion category does not match store category")
        if not str(reason).strip():
            raise ChampionStoreError("transition reason is required")

        with self._exclusive_lock():
            current = self._read_unlocked()
            current_champion = current.get("champion")
            # Always repair a state-first/history-second interruption before
            # allowing another transition to advance the revision.
            if current["revision"]:
                self._append_history_row(current["transition"])
            # A retry after a successful write is idempotent even if it still
            # carries the pre-write expected revision.
            if (
                isinstance(current_champion, Mapping)
                and current_champion.get("metadata_sha256") == candidate.get("metadata_sha256")
            ):
                return current
            if current["revision"] != expected_revision:
                raise ChampionConflict(
                    f"champion revision changed: expected={expected_revision} actual={current['revision']}"
                )
            if (
                isinstance(current_champion, Mapping)
                and candidate["baseline_candidate_id"] != current_champion.get("candidate_id")
            ):
                raise ChampionConflict(
                    "candidate was not paired against the current persisted champion"
                )
            updated_at = _utc_now()
            transition = self._transition_row(
                previous=current_champion,
                champion=candidate,
                from_revision=expected_revision,
                to_revision=expected_revision + 1,
                reason=reason,
                recorded_at=updated_at,
            )
            state: dict[str, Any] = {
                "schema": STATE_SCHEMA,
                "category": self.category,
                "revision": expected_revision + 1,
                "updated_at": updated_at,
                "champion": candidate,
                # Embedding the exact transition makes a state-first crash
                # recoverable: an idempotent CAS retry can repair JSONL history.
                "transition": transition,
            }
            state["state_sha256"] = content_digest(state)
            self._atomic_write_state(state)
            self._append_history_row(transition)
            return state

    def history(self) -> tuple[dict[str, Any], ...]:
        with self._exclusive_lock():
            if not self.history_path.exists():
                state = self._read_unlocked()
                if state["revision"]:
                    raise ChampionStoreError("champion state has no transition history")
                return ()
            try:
                lines = self.history_path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                raise ChampionStoreError(f"cannot read champion history: {exc}") from exc
            state_revision = self._read_unlocked()["revision"]
        result: list[dict[str, Any]] = []
        expected_revision = 0
        expected_previous: str | None = None
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ChampionStoreError(f"invalid champion history line {line_number}") from exc
            claimed = str(row.get("transition_sha256") or "")
            unsigned = dict(row)
            unsigned.pop("transition_sha256", None)
            if row.get("schema") != HISTORY_SCHEMA or claimed != content_digest(unsigned):
                raise ChampionStoreError(f"champion history integrity failure at line {line_number}")
            if row.get("category") != self.category or not isinstance(row.get("champion"), Mapping):
                raise ChampionStoreError(f"champion history category failure at line {line_number}")
            validate_shadow_champion(row["champion"])
            if (
                row.get("from_revision") != expected_revision
                or row.get("to_revision") != expected_revision + 1
                or row.get("previous_candidate_id") != expected_previous
            ):
                raise ChampionStoreError(f"champion history chain failure at line {line_number}")
            result.append(row)
            expected_revision += 1
            expected_previous = str(row["champion"]["candidate_id"])
        if expected_revision != state_revision:
            raise ChampionStoreError("champion history does not reach current state revision")
        return tuple(result)

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "schema": STATE_SCHEMA,
                "category": self.category,
                "revision": 0,
                "updated_at": None,
                "champion": None,
                "transition": None,
                "state_sha256": None,
            }
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChampionStoreError(f"cannot read champion state: {exc}") from exc
        if not isinstance(state, Mapping):
            raise ChampionStoreError("champion state root must be an object")
        if state.get("schema") != STATE_SCHEMA or state.get("category") != self.category:
            raise ChampionStoreError("champion state schema or category mismatch")
        if isinstance(state.get("revision"), bool) or not isinstance(state.get("revision"), int):
            raise ChampionStoreError("champion revision is invalid")
        claimed = str(state.get("state_sha256") or "")
        unsigned = dict(state)
        unsigned.pop("state_sha256", None)
        if claimed != content_digest(unsigned):
            raise ChampionStoreError("champion state digest mismatch")
        champion = state.get("champion")
        if not isinstance(champion, Mapping):
            raise ChampionStoreError("persisted champion metadata is missing")
        validate_shadow_champion(champion)
        transition = state.get("transition")
        if not isinstance(transition, Mapping):
            raise ChampionStoreError("persisted champion transition is missing")
        transition_champion = transition.get("champion")
        if not isinstance(transition_champion, Mapping):
            raise ChampionStoreError("persisted transition champion is invalid")
        transition_unsigned = dict(transition)
        transition_digest = str(transition_unsigned.pop("transition_sha256", ""))
        if (
            transition_digest != content_digest(transition_unsigned)
            or transition.get("to_revision") != state.get("revision")
            or transition_champion.get("metadata_sha256") != champion.get("metadata_sha256")
        ):
            raise ChampionStoreError("persisted champion transition is invalid")
        return dict(state)

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.category_root.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _atomic_write_state(self, state: Mapping[str, Any]) -> None:
        payload = (json.dumps(state, sort_keys=True, indent=2) + "\n").encode("utf-8")
        fd, temp_name = tempfile.mkstemp(prefix=".champion.", dir=self.category_root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
            _fsync_directory(self.category_root)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _transition_row(
        self,
        *,
        previous: Mapping[str, Any] | None,
        champion: Mapping[str, Any],
        from_revision: int,
        to_revision: int,
        reason: str,
        recorded_at: str,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "schema": HISTORY_SCHEMA,
            "category": self.category,
            "from_revision": from_revision,
            "to_revision": to_revision,
            "previous_candidate_id": None if previous is None else previous.get("candidate_id"),
            "champion": champion,
            "reason": reason,
            "recorded_at": recorded_at,
        }
        row["transition_sha256"] = content_digest(row)
        return row

    def _append_history_row(self, row: Mapping[str, Any]) -> None:
        rows: list[dict[str, Any]] = []
        if self.history_path.exists():
            for line_number, line in enumerate(
                self.history_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ChampionStoreError(
                        f"cannot repair invalid champion history line {line_number}"
                    ) from exc
                if existing.get("transition_sha256") == row.get("transition_sha256"):
                    return
                rows.append(existing)
        rows.append(dict(row))
        payload = "".join(
            json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
            for item in rows
        ).encode("utf-8")
        fd, temp_name = tempfile.mkstemp(prefix=".champion-history.", dir=self.category_root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.history_path)
            _fsync_directory(self.category_root)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "CHAMPION_SCHEMA",
    "HISTORY_SCHEMA",
    "STATE_SCHEMA",
    "ChampionConflict",
    "ChampionStore",
    "ChampionStoreError",
    "build_shadow_champion",
    "validate_shadow_champion",
]
