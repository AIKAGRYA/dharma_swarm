# spine: adapter over the canonical GraphPersistenceKernel
"""LangGraph-shaped sync/async checkpoint lifecycle adapter."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from dharma_swarm.graph.state import state_digest
from dharma_swarm.graph.types import RunCheckpoint


class CheckpointSaverAdapter:
    def get_tuple(self, config: Mapping[str, Any]) -> dict[str, Any] | None:
        thread_id, checkpoint_id = self._config_ids(config)
        record = self.get_checkpoint_record(thread_id, checkpoint_id)
        return None if record is None else record.to_dict()

    def list(
        self,
        config: Mapping[str, Any] | None,
        *,
        before: Mapping[str, Any] | None = None,
        limit: int | None = None,
        filter: Mapping[str, Any] | None = None,
    ) -> Iterable[dict[str, Any]]:
        del filter
        thread_id = self._config_ids(config or {"configurable": {"thread_id": ""}})[0]
        records = self.get_state_history(thread_id)
        if before:
            _, before_id = self._config_ids(before)
            before_index = next(
                (
                    index
                    for index, record in enumerate(records)
                    if record.checkpoint_id == before_id
                ),
                len(records),
            )
            records = records[:before_index]
        if limit is not None:
            records = records[-limit:]
        return [record.to_dict() for record in records]

    def put(
        self,
        config: Mapping[str, Any],
        checkpoint: Mapping[str, Any],
        metadata: Mapping[str, Any],
        new_versions: Mapping[str, Any],
    ) -> dict[str, Any]:
        del new_versions
        thread_id, parent_id = self._config_ids(config)
        channel_values = dict(checkpoint.get("channel_values", {}))
        channels = {
            name: {"version": 1, "value": value}
            for name, value in channel_values.items()
        }
        run_checkpoint = RunCheckpoint(
            graph_run_id=str(metadata.get("graph_run_id", thread_id)),
            graph_id=str(metadata.get("graph_id", "langgraph-compatible")),
            superstep=int(metadata.get("superstep", 0)),
            state_digest=state_digest(channel_values),
            channels=channels,
            versions_seen=dict(checkpoint.get("versions_seen", {})),
        )
        record = self.put_run_checkpoint(
            thread_id,
            run_checkpoint,
            checkpoint_id=str(checkpoint.get("id", "")) or None,
            parent_checkpoint_id=parent_id,
            metadata=metadata,
        )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": record.checkpoint_id,
            }
        }

    async def aget_tuple(self, config: Mapping[str, Any]) -> dict[str, Any] | None:
        return self.get_tuple(config)

    async def alist(
        self, config: Mapping[str, Any] | None, **kwargs: Any
    ) -> Iterable[dict[str, Any]]:
        return self.list(config, **kwargs)

    async def aput(
        self,
        config: Mapping[str, Any],
        checkpoint: Mapping[str, Any],
        metadata: Mapping[str, Any],
        new_versions: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: Mapping[str, Any],
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, checkpoint_id = self._config_ids(config)
        self.put_writes(
            thread_id,
            writes,
            task_id,
            checkpoint_id=checkpoint_id,
            task_path=task_path,
        )

    async def adelete_thread(self, thread_id: str) -> None:
        self.delete_thread(thread_id)

    async def adelete_for_runs(self, run_ids: Sequence[str]) -> None:
        self.delete_for_runs(run_ids)

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        self.copy_thread(source_thread_id, target_thread_id)

    async def aprune(
        self, thread_ids: Sequence[str], *, strategy: str = "keep_latest"
    ) -> None:
        self.prune(thread_ids, strategy=strategy)

    async def aget_delta_channel_history(
        self, *, thread_id: str, channels: Sequence[str]
    ) -> Mapping[str, list[dict[str, Any]]]:
        return self.get_delta_channel_history(thread_id=thread_id, channels=channels)
