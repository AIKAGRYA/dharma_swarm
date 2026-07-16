# spine: extends graph checkpoints under ~/.dharma/graph/checkpoints — no new truth store
"""Thread-addressed persistence kernel for DharmaGraph checkpoints."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence
from dharma_swarm.graph._persistence_io import (
    atomic_write_serialized,
    read_serialized_state,
)
from dharma_swarm.graph._persistence_lock import locked_persistence_file
from dharma_swarm.graph._persistence_state import (
    derive_updated_checkpoint,
    extract_state,
)
from dharma_swarm.graph.channels import Channel
from dharma_swarm.graph.checkpoint import DEFAULT_CHECKPOINT_DIR
from dharma_swarm.graph.persistence_adapter import CheckpointSaverAdapter
from dharma_swarm.graph.types import RunCheckpoint

__all__ = [
    "DeltaChannelHistory",
    "GraphCheckpointRecord",
    "GraphPendingWrite",
    "GraphPersistenceKernel",
    "GraphSerializer",
    "JsonGraphSerializer",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(raw: str) -> str:
    if not raw:
        raise ValueError("thread_id/checkpoint_id must not be empty")
    safe = "".join(ch if ch.isalnum() or ch in "._=-" else "_" for ch in raw)[:80]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{safe}-{digest}"


class GraphSerializer(Protocol):
    def dumps_typed(self, obj: Any) -> tuple[str, bytes]: ...

    def loads_typed(self, data: tuple[str, bytes]) -> Any: ...


class JsonGraphSerializer:
    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return (
            "json",
            json.dumps(
                obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8"),
        )

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        kind, payload = data
        if kind != "json":
            raise ValueError(f"unsupported graph serializer payload type {kind!r}")
        return json.loads(payload.decode("utf-8"))


@dataclass(frozen=True)
class GraphCheckpointRecord:
    thread_id: str
    checkpoint_id: str
    parent_checkpoint_id: str | None
    checkpoint: RunCheckpoint
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)

    @property
    def graph_run_id(self) -> str:
        return self.checkpoint.graph_run_id

    @property
    def superstep(self) -> int:
        return self.checkpoint.superstep

    @property
    def state_digest(self) -> str:
        return self.checkpoint.state_digest

    @property
    def state(self) -> dict[str, Any]:
        return extract_state(self.checkpoint.channels)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checkpoint"] = asdict(self.checkpoint)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphCheckpointRecord":
        return cls(
            thread_id=str(data["thread_id"]),
            checkpoint_id=str(data["checkpoint_id"]),
            parent_checkpoint_id=(
                None
                if data.get("parent_checkpoint_id") is None
                else str(data["parent_checkpoint_id"])
            ),
            checkpoint=RunCheckpoint(**dict(data["checkpoint"])),
            metadata=dict(data.get("metadata", {})),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True)
class GraphPendingWrite:
    thread_id: str
    checkpoint_id: str | None
    task_id: str
    task_path: str
    writes: tuple[tuple[str, Any], ...]
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphPendingWrite":
        return cls(
            thread_id=str(data["thread_id"]),
            checkpoint_id=(
                None
                if data.get("checkpoint_id") is None
                else str(data["checkpoint_id"])
            ),
            task_id=str(data["task_id"]),
            task_path=str(data.get("task_path", "")),
            writes=tuple((str(ch), value) for ch, value in data.get("writes", ())),
            created_at=str(data["created_at"]),
        )


DeltaChannelHistory = list[dict[str, Any]]


class GraphPersistenceKernel(CheckpointSaverAdapter):
    def __init__(
        self,
        persist_dir: Path | None = None,
        *,
        serializer: GraphSerializer | None = None,
    ) -> None:
        self.persist_dir = persist_dir or DEFAULT_CHECKPOINT_DIR / "threads"
        self.serde = serializer or JsonGraphSerializer()

    def put_run_checkpoint(
        self,
        thread_id: str,
        checkpoint: RunCheckpoint,
        *,
        checkpoint_id: str | None = None,
        parent_checkpoint_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GraphCheckpointRecord:
        with locked_persistence_file(self._thread_path(thread_id)):
            state = self._read_thread_unlocked(thread_id)
            return self._append_run_checkpoint_unlocked(
                thread_id,
                checkpoint,
                state,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
                metadata=metadata,
            )

    def _append_run_checkpoint_unlocked(
        self,
        thread_id: str,
        checkpoint: RunCheckpoint,
        state: dict[str, Any],
        *,
        checkpoint_id: str | None = None,
        parent_checkpoint_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GraphCheckpointRecord:
        """Append to an already locked thread state without re-locking."""
        records = [
            GraphCheckpointRecord.from_dict(item)
            for item in state.get("checkpoints", [])
        ]
        resolved_checkpoint_id = checkpoint_id or self._next_checkpoint_id(
            checkpoint, records
        )
        existing = next(
            (
                record
                for record in records
                if record.checkpoint_id == resolved_checkpoint_id
            ),
            None,
        )
        if existing is not None:
            if existing.checkpoint == checkpoint and (
                parent_checkpoint_id is None
                or existing.parent_checkpoint_id == parent_checkpoint_id
            ):
                return existing
            raise ValueError(
                f"checkpoint_id {resolved_checkpoint_id!r} already exists for "
                f"thread {thread_id!r}"
            )
        if parent_checkpoint_id is None and records:
            parent_checkpoint_id = records[-1].checkpoint_id
        record = GraphCheckpointRecord(
            thread_id=thread_id,
            checkpoint_id=resolved_checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            checkpoint=checkpoint,
            metadata=dict(metadata or {}),
        )
        state.setdefault("checkpoints", []).append(record.to_dict())
        state["updated_at"] = _utc_now_iso()
        self._write_thread(thread_id, state)
        return record

    def get_run_checkpoint(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> RunCheckpoint | None:
        record = self.get_checkpoint_record(thread_id, checkpoint_id)
        return None if record is None else record.checkpoint

    def get_checkpoint_record(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> GraphCheckpointRecord | None:
        records = self.get_state_history(thread_id)
        if not records:
            return None
        if checkpoint_id is None:
            return records[-1]
        for record in records:
            if record.checkpoint_id == checkpoint_id:
                return record
        return None

    def get_state(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> dict[str, Any]:
        record = self.get_checkpoint_record(thread_id, checkpoint_id)
        if record is None:
            raise KeyError(f"checkpoint not found for thread {thread_id!r}")
        return record.state

    def get_state_history(self, thread_id: str) -> list[GraphCheckpointRecord]:
        state = self._read_thread(thread_id, create=False)
        return [
            GraphCheckpointRecord.from_dict(r) for r in state.get("checkpoints", [])
        ]

    def update_state(
        self,
        thread_id: str,
        values: Mapping[str, Any],
        *,
        channel_factories: Mapping[str, Callable[[], Channel[Any]]] | None = None,
        checkpoint_id: str | None = None,
        as_node: str = "__manual_update__",
    ) -> GraphCheckpointRecord:
        # Latest selection, derivation, and append form one mutation. Explicit
        # checkpoint_id still means an intentional historical branch; an
        # unnamed concurrent update always composes atop the latest commit.
        with locked_persistence_file(self._thread_path(thread_id)):
            persisted = self._read_thread_unlocked(thread_id, create=False)
            records = [
                GraphCheckpointRecord.from_dict(item)
                for item in persisted.get("checkpoints", [])
            ]
            if checkpoint_id is None:
                base = records[-1] if records else None
            else:
                base = next(
                    (
                        record
                        for record in records
                        if record.checkpoint_id == checkpoint_id
                    ),
                    None,
                )
            if base is None:
                raise KeyError(f"checkpoint not found for thread {thread_id!r}")

            checkpoint = derive_updated_checkpoint(
                base.checkpoint,
                values,
                channel_factories=channel_factories,
                as_node=as_node,
            )
            return self._append_run_checkpoint_unlocked(
                thread_id,
                checkpoint,
                persisted,
                parent_checkpoint_id=base.checkpoint_id,
                metadata={"source": "update_state", "as_node": as_node},
            )

    def bulk_update_state(
        self,
        thread_id: str,
        updates: Iterable[Mapping[str, Any]],
        *,
        channel_factories: Mapping[str, Callable[[], Channel[Any]]] | None = None,
        as_node: str = "__bulk_update__",
    ) -> GraphCheckpointRecord:
        record: GraphCheckpointRecord | None = None
        for values in updates:
            record = self.update_state(
                thread_id,
                values,
                channel_factories=channel_factories,
                as_node=as_node,
            )
        if record is None:
            raise ValueError("bulk_update_state requires at least one update")
        return record

    def put_writes(
        self,
        thread_id: str,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        *,
        checkpoint_id: str | None = None,
        task_path: str = "",
    ) -> None:
        with locked_persistence_file(self._thread_path(thread_id)):
            state = self._read_thread_unlocked(thread_id)
            state["pending_writes"].append(
                GraphPendingWrite(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    task_id=task_id,
                    task_path=task_path,
                    writes=tuple(writes),
                ).to_dict()
            )
            state["updated_at"] = _utc_now_iso()
            self._write_thread(thread_id, state)

    def recover_pending_writes(self, thread_id: str) -> list[GraphPendingWrite]:
        state = self._read_thread(thread_id, create=False)
        return [GraphPendingWrite.from_dict(w) for w in state.get("pending_writes", [])]

    def clear_pending_writes(self, thread_id: str, task_id: str | None = None) -> None:
        with locked_persistence_file(self._thread_path(thread_id)):
            state = self._read_thread_unlocked(thread_id, create=False)
            if task_id is None:
                state["pending_writes"] = []
            else:
                state["pending_writes"] = [
                    w
                    for w in state.get("pending_writes", [])
                    if w.get("task_id") != task_id
                ]
            state["updated_at"] = _utc_now_iso()
            self._write_thread(thread_id, state)

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        if not self._thread_path(source_thread_id).exists():
            raise KeyError(f"thread {source_thread_id!r} not found")
        state = copy.deepcopy(self._read_thread(source_thread_id, create=False))
        for record in state.get("checkpoints", []):
            record["thread_id"] = target_thread_id
        for write in state.get("pending_writes", []):
            write["thread_id"] = target_thread_id
        state["updated_at"] = _utc_now_iso()
        with locked_persistence_file(self._thread_path(target_thread_id)):
            self._write_thread(target_thread_id, state)

    def delete_thread(self, thread_id: str) -> None:
        path = self._thread_path(thread_id)
        with locked_persistence_file(path):
            if path.exists():
                path.unlink()

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        wanted = set(run_ids)
        for path in self.persist_dir.glob("*.json"):
            with locked_persistence_file(path):
                state = self._read_path(path)
                removed_checkpoint_ids = {
                    record["checkpoint_id"]
                    for record in state.get("checkpoints", [])
                    if record.get("checkpoint", {}).get("graph_run_id") in wanted
                }
                state["checkpoints"] = [
                    r
                    for r in state.get("checkpoints", [])
                    if r.get("checkpoint", {}).get("graph_run_id") not in wanted
                ]
                state["pending_writes"] = [
                    write
                    for write in state.get("pending_writes", [])
                    if write.get("checkpoint_id") not in removed_checkpoint_ids
                    and not any(
                        str(write.get("task_id", "")).startswith(f"{run_id}:")
                        for run_id in wanted
                    )
                ]
                self._atomic_write(path, state)

    def prune(
        self, thread_ids: Sequence[str], *, strategy: str = "keep_latest"
    ) -> None:
        if strategy != "keep_latest":
            raise ValueError("only keep_latest prune strategy is supported")
        for thread_id in thread_ids:
            with locked_persistence_file(self._thread_path(thread_id)):
                state = self._read_thread_unlocked(thread_id, create=False)
                if state.get("checkpoints"):
                    latest = dict(state["checkpoints"][-1])
                    latest["parent_checkpoint_id"] = None
                    state["checkpoints"] = [latest]
                    state["pending_writes"] = []
                    state["updated_at"] = _utc_now_iso()
                    self._write_thread(thread_id, state)

    def get_delta_channel_history(
        self, *, thread_id: str, channels: Sequence[str]
    ) -> Mapping[str, DeltaChannelHistory]:
        wanted = set(channels)
        history: dict[str, DeltaChannelHistory] = {name: [] for name in channels}
        previous: dict[str, Any] = {}
        for record in self.get_state_history(thread_id):
            current = record.state
            for name in wanted:
                if current.get(name) != previous.get(name):
                    history[name].append(
                        {
                            "checkpoint_id": record.checkpoint_id,
                            "superstep": record.superstep,
                            "value": copy.deepcopy(current.get(name)),
                        }
                    )
            previous = current
        return history

    def _read_thread(self, thread_id: str, *, create: bool = True) -> dict[str, Any]:
        return self._read_thread_unlocked(thread_id, create=create)

    def _read_thread_unlocked(
        self, thread_id: str, *, create: bool = True
    ) -> dict[str, Any]:
        path = self._thread_path(thread_id)
        if not path.exists():
            if not create:
                return {"checkpoints": [], "pending_writes": []}
            return {
                "schema": "dharma_swarm.graph.persistence.v1",
                "thread_id": thread_id,
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
                "checkpoints": [],
                "pending_writes": [],
            }
        return self._read_path(path)

    def _read_path(self, path: Path) -> dict[str, Any]:
        return read_serialized_state(path, self.serde)

    def _write_thread(self, thread_id: str, state: Mapping[str, Any]) -> None:
        self._atomic_write(self._thread_path(thread_id), state)

    def _atomic_write(self, target: Path, payload: Mapping[str, Any]) -> None:
        atomic_write_serialized(target, payload, self.serde)

    def _thread_path(self, thread_id: str) -> Path:
        return self.persist_dir / f"{_safe_id(thread_id)}.json"

    def _next_checkpoint_id(
        self, checkpoint: RunCheckpoint, records: Sequence[GraphCheckpointRecord]
    ) -> str:
        base = (
            f"{checkpoint.superstep:06d}-{checkpoint.state_digest.split(':')[-1][:12]}"
        )
        used = {record.checkpoint_id for record in records}
        if base not in used:
            return base
        index = 1
        while f"{base}-{index}" in used:
            index += 1
        return f"{base}-{index}"

    def _config_ids(self, config: Mapping[str, Any]) -> tuple[str, str | None]:
        configurable = dict(config.get("configurable", {}))
        thread_id = str(configurable.get("thread_id", ""))
        checkpoint_id = configurable.get("checkpoint_id")
        if not thread_id:
            raise ValueError("config.configurable.thread_id is required")
        return thread_id, None if checkpoint_id is None else str(checkpoint_id)
