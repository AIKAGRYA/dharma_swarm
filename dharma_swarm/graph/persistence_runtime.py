# spine: scheduler boundary over the canonical GraphPersistenceKernel
"""Scheduler integration for thread-addressed graph persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from dharma_swarm.graph.channels import ChannelWrite
from dharma_swarm.graph.persistence import (
    GraphCheckpointRecord,
    GraphPendingWrite,
    GraphPersistenceKernel,
)
from dharma_swarm.graph.state import GraphState
from dharma_swarm.graph.types import RunCheckpoint


class ReplayTask(Protocol):
    node_id: str
    seq: int
    is_pull: bool


@dataclass
class GraphRunPersistence:
    kernel: GraphPersistenceKernel | None
    thread_id: str | None
    parent_checkpoint_id: str | None = None
    pending_write: GraphPendingWrite | None = None

    @classmethod
    def resolve(
        cls,
        kernel: GraphPersistenceKernel | None,
        thread_id: str | None,
        checkpoint_id: str | None,
        input: Mapping[str, Any] | None,
        resume_from: RunCheckpoint | None,
    ) -> tuple[GraphRunPersistence, RunCheckpoint | None]:
        if (kernel is None) != (thread_id is None):
            raise ValueError("persistence and thread_id must be provided together")
        boundary = cls(kernel, thread_id)
        if kernel is None or thread_id is None:
            return boundary, resume_from
        if resume_from is not None:
            persisted = cls._resume_record(
                kernel, thread_id, checkpoint_id, resume_from
            )
            if persisted is not None:
                boundary.parent_checkpoint_id = persisted.checkpoint_id
                boundary.pending_write = cls._pending_after(
                    kernel, thread_id, persisted
                )
            return boundary, resume_from
        persisted = kernel.get_checkpoint_record(thread_id, checkpoint_id)
        if persisted is not None and input is None:
            boundary.parent_checkpoint_id = persisted.checkpoint_id
            boundary.pending_write = cls._pending_after(kernel, thread_id, persisted)
            return boundary, persisted.checkpoint
        if checkpoint_id is not None or input is None:
            raise KeyError(
                f"checkpoint {checkpoint_id!r} not found for thread {thread_id!r}"
            )
        return boundary, resume_from

    @staticmethod
    def _resume_record(
        kernel: GraphPersistenceKernel,
        thread_id: str,
        checkpoint_id: str | None,
        resume_from: RunCheckpoint,
    ) -> GraphCheckpointRecord | None:
        if checkpoint_id is not None:
            record = kernel.get_checkpoint_record(thread_id, checkpoint_id)
            if record is None:
                raise KeyError(
                    f"checkpoint {checkpoint_id!r} not found for thread {thread_id!r}"
                )
            if record.checkpoint != resume_from:
                raise ValueError(
                    "resume_from does not match the addressed persisted checkpoint"
                )
            return record
        history = kernel.get_state_history(thread_id)
        matches = [record for record in history if record.checkpoint == resume_from]
        if len(matches) > 1:
            raise ValueError("resume_from matches multiple persisted checkpoints")
        if matches:
            return matches[0]
        if history:
            raise ValueError(
                "resume_from is not a persisted checkpoint for this thread"
            )
        return None

    @staticmethod
    def _pending_after(
        kernel: GraphPersistenceKernel,
        thread_id: str,
        record: GraphCheckpointRecord,
    ) -> GraphPendingWrite | None:
        pending = kernel.recover_pending_writes(thread_id)
        replay = [
            write for write in pending if write.checkpoint_id == record.checkpoint_id
        ]
        if len(replay) > 1:
            raise ValueError(
                f"multiple pending supersteps follow checkpoint "
                f"{record.checkpoint_id!r}"
            )
        committed_task_id = (
            f"{record.checkpoint.graph_run_id}:{record.checkpoint.superstep}"
        )
        for write in pending:
            if (
                write.checkpoint_id == record.parent_checkpoint_id
                and write.task_id == committed_task_id
            ):
                kernel.clear_pending_writes(thread_id, write.task_id)
        return replay[0] if replay else None

    def replay(
        self,
        state: GraphState,
        versions_seen: dict[str, dict[str, int]],
        triggers: Mapping[str, Sequence[str]],
        tasks: Sequence[ReplayTask],
        run_id: str,
        superstep: int,
    ) -> str:
        pending = self.pending_write
        if pending is None:
            raise ValueError("no pending writes available for replay")
        expected_task_id = f"{run_id}:{superstep}"
        if pending.task_id != expected_task_id:
            raise ValueError(
                f"pending task {pending.task_id!r} does not match {expected_task_id!r}"
            )
        task_path = "+".join(sorted(task.node_id for task in tasks))
        if pending.task_path != task_path:
            raise ValueError(
                f"pending task path {pending.task_path!r} does not match "
                f"ready tasks {task_path!r}"
            )
        start_versions = state.versions
        for task in tasks:
            if task.is_pull:
                for name in triggers[task.node_id]:
                    versions_seen[task.node_id][name] = start_versions.get(name, 0)
        state.apply_writes(
            [
                ChannelWrite(pending.task_path, channel, value, index)
                for index, (channel, value) in enumerate(pending.writes)
            ],
            superstep,
        )
        return pending.task_id

    def journal(
        self,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        *,
        task_path: str,
    ) -> None:
        if self.kernel is None or self.thread_id is None:
            return
        self.kernel.put_writes(
            self.thread_id,
            writes,
            task_id,
            checkpoint_id=self.parent_checkpoint_id,
            task_path=task_path,
        )

    def commit(
        self, checkpoint: RunCheckpoint, pending_task_id: str | None = None
    ) -> None:
        if self.kernel is None or self.thread_id is None:
            return
        record = self.kernel.put_run_checkpoint(
            self.thread_id,
            checkpoint,
            parent_checkpoint_id=self.parent_checkpoint_id,
            metadata={
                "graph_id": checkpoint.graph_id,
                "graph_run_id": checkpoint.graph_run_id,
            },
        )
        self.parent_checkpoint_id = record.checkpoint_id
        if pending_task_id is not None:
            self.kernel.clear_pending_writes(self.thread_id, pending_task_id)
