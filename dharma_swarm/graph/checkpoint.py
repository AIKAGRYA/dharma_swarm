# spine: persists dispatch-shaped checkpoints, receipts via runtime_state (owner: runtime_state) — no new store
"""Atomic, crash-safe dispatch checkpoints for the graph runtime.

Absorbed from ``durable_execution.DurableWorkflow`` before its deletion
(dharmagraph-engine-2026-07, Phase 0a): the tmp+rename+fsync atomic write,
full-state restore, and the ``_record_runtime_receipt`` spine hook that ties
checkpoints to ``ExecutionIdentity``/``RuntimeReceipt``.

The record is dispatch-shaped (run_id, superstep, node_id, state_ref,
created_at) — deliberately NOT the loop/fitness-shaped ``LoopCheckpoint``
from ``dharma_swarm.checkpoint``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity

__all__ = ["DispatchCheckpoint", "GraphCheckpointStore"]

logger = logging.getLogger(__name__)

DEFAULT_CHECKPOINT_DIR = Path(
    os.getenv("DHARMA_GRAPH_CHECKPOINT_DIR", str(Path.home() / ".dharma" / "graph" / "checkpoints"))
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DispatchCheckpoint:
    """One superstep's durable dispatch record."""

    run_id: str
    superstep: int
    node_id: str
    state_ref: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DispatchCheckpoint:
        return cls(
            run_id=str(data["run_id"]),
            superstep=int(data["superstep"]),
            node_id=str(data["node_id"]),
            state_ref=str(data["state_ref"]),
            created_at=str(data["created_at"]),
        )


class GraphCheckpointStore:
    """Crash-safe checkpoint log for one graph run.

    Every ``checkpoint()`` persists the FULL run state to disk atomically
    (tmp file in the target directory, fsync, ``os.replace``) so a restore
    after ``kill -9`` sees either the previous state or the new state,
    never a torn file.
    """

    def __init__(
        self,
        run_id: str,
        persist_dir: Path | None = None,
        runtime_state: RuntimeStateStore | None = None,
        execution_identity: ExecutionIdentity | None = None,
    ) -> None:
        self.run_id = run_id
        self._persist_dir = persist_dir or DEFAULT_CHECKPOINT_DIR / run_id
        self._checkpoints: list[DispatchCheckpoint] = []
        self._created_at: str = _utc_now_iso()
        self._runtime_state = runtime_state
        self._execution_identity = execution_identity

    # -- Checkpointing ---------------------------------------------------

    def checkpoint(self, superstep: int, node_id: str, state_ref: str) -> Path:
        """Append a dispatch checkpoint and persist full state atomically.

        Returns:
            Path to the state file.

        Raises:
            ValueError: if ``superstep`` regresses below the latest record.
        """
        latest = self.latest()
        if latest is not None and superstep < latest.superstep:
            raise ValueError(
                f"superstep {superstep} regresses below latest {latest.superstep} "
                f"for run {self.run_id}"
            )
        record = DispatchCheckpoint(
            run_id=self.run_id,
            superstep=superstep,
            node_id=node_id,
            state_ref=state_ref,
            created_at=_utc_now_iso(),
        )
        self._checkpoints.append(record)
        try:
            target = self._write_state()
        except BaseException:
            self._checkpoints.pop()
            raise
        self._record_runtime_receipt(
            "checkpointed",
            {
                "run_id": self.run_id,
                "checkpoint_path": str(target),
                "superstep": superstep,
                "node_id": node_id,
                "checkpoint_count": len(self._checkpoints),
            },
        )
        return target

    def _write_state(self) -> Path:
        state = {
            "run_id": self.run_id,
            "created_at": self._created_at,
            "checkpointed_at": _utc_now_iso(),
            "checkpoints": [c.to_dict() for c in self._checkpoints],
        }
        target = self._persist_dir / "state.json"
        target.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp", prefix=".gckpt_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps(state, indent=2, default=str))
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.debug("Checkpointed graph run %s to %s", self.run_id, target)
        return target

    # -- Restore -----------------------------------------------------------

    @classmethod
    def restore(
        cls,
        run_id: str,
        persist_dir: Path | None = None,
        runtime_state: RuntimeStateStore | None = None,
        execution_identity: ExecutionIdentity | None = None,
    ) -> GraphCheckpointStore:
        """Restore a run's checkpoint log from its on-disk state.

        Raises:
            FileNotFoundError: if no checkpoint state exists.
            json.JSONDecodeError: if the state file is corrupt.
        """
        base = persist_dir or DEFAULT_CHECKPOINT_DIR / run_id
        state_path = base / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"No checkpoint found at {state_path}")

        data = json.loads(state_path.read_text(encoding="utf-8"))
        store = cls(
            run_id=str(data["run_id"]),
            persist_dir=base,
            runtime_state=runtime_state,
            execution_identity=execution_identity,
        )
        store._created_at = data.get("created_at", store._created_at)
        store._checkpoints = [DispatchCheckpoint.from_dict(c) for c in data["checkpoints"]]
        logger.info(
            "Restored graph run %s (%d checkpoints) from %s",
            run_id,
            len(store._checkpoints),
            state_path,
        )
        return store

    # -- Queries -------------------------------------------------------------

    def latest(self) -> DispatchCheckpoint | None:
        """Return the most recent checkpoint, or None if empty."""
        return self._checkpoints[-1] if self._checkpoints else None

    @property
    def checkpoints(self) -> list[DispatchCheckpoint]:
        """All checkpoints in append order."""
        return list(self._checkpoints)

    # -- Spine hook ------------------------------------------------------------

    def _record_runtime_receipt(self, status: str, payload: dict[str, Any]) -> None:
        """Record checkpoint state in RuntimeStateStore when identity is provided."""
        if self._runtime_state is None or self._execution_identity is None:
            return
        identity = self._execution_identity.require_for_dispatch()
        side_effect_key = f"graph_checkpoint:{self.run_id}"
        try:
            self._runtime_state.record_execution_identity_sync(
                identity,
                source="graph.checkpoint",
                metadata={"run_id": self.run_id},
            )
            receipt = self._runtime_state.build_runtime_receipt(
                identity,
                receipt_type="workflow_checkpoint",
                status=status,
                side_effect_key=side_effect_key,
                payload=payload,
            )
            self._runtime_state.record_runtime_receipt_sync(receipt)
        except Exception:
            logger.warning(
                "graph checkpoint receipt failed for run %s", self.run_id, exc_info=True
            )
