# spine: scheduler boundary over the canonical GraphPersistenceKernel
"""Scheduler integration for thread-addressed graph persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from dharma_swarm.graph.persistence import GraphPersistenceKernel
from dharma_swarm.graph.types import RunCheckpoint


@dataclass
class GraphRunPersistence:
    kernel: GraphPersistenceKernel | None
    thread_id: str | None
    parent_checkpoint_id: str | None = None

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
        if kernel is None or thread_id is None or resume_from is not None:
            return boundary, resume_from
        persisted = kernel.get_checkpoint_record(thread_id, checkpoint_id)
        if persisted is not None and input is None:
            boundary.parent_checkpoint_id = persisted.checkpoint_id
            return boundary, persisted.checkpoint
        if checkpoint_id is not None or input is None:
            raise KeyError(
                f"checkpoint {checkpoint_id!r} not found for thread {thread_id!r}"
            )
        return boundary, resume_from

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
