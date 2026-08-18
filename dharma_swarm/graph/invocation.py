"""Invocation surfaces (LG12 parity) over ``CompiledGraph``'s committed run loop.

Split out of ``scheduler.py`` (which owns the run lifecycle itself — seeding,
resume, the commit barrier, and checkpoints — via
:meth:`CompiledGraph._run_supersteps`); this module owns everything layered
on top of that one loop.

Invocation surfaces (LG12 parity): the run lifecycle IS the async
generator :meth:`~dharma_swarm.graph.scheduler.CompiledGraph._run_supersteps`,
which emits one :class:`SuperstepEmission` per COMMITTED barrier (seed
included) and a final ``GraphRunResult``. Every public surface in
:class:`InvocationSurfacesMixin` is a projection of that one loop, so no
surface can observe uncommitted state: ``invoke`` (async, the historical
entry point) drains it and returns the result; ``stream`` re-yields each
barrier; ``invoke_sync`` / ``stream_sync`` run the same coroutine on a
PRIVATE event loop and fail closed inside a live loop (an async-native
engine never re-enters a running loop). The ``stream_mode`` / ``version``
pair matches langgraph 1.2.4 empirically: ``values`` yields the
post-barrier state snapshot (seed snapshot first), ``updates`` yields one
``{node: writes}`` chunk PER TASK in canonical node order (never for the
seed), and ``version="v2"`` wraps each chunk as the StreamPart mapping
``{"type", "ns", "data"}`` with ``ns=()`` for flat graphs. Recorded
deviation: ``invoke(stream_mode="values", version="v2")`` returns this
engine's ``GraphRunResult`` envelope, not langgraph's ``GraphOutput`` — the
envelope is the sovereign result type and carries the digest the receipt
chain anchors.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncIterator, Awaitable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, TypeVar

from dharma_swarm.graph.channels import ChannelWrite
from dharma_swarm.graph.errors import GraphRuntimeError
from dharma_swarm.graph.types import RESERVED_PREFIX, GraphRunResult

__all__ = [
    "InvocationSurfacesMixin",
    "StreamMode",
    "StreamVersion",
    "SuperstepEmission",
    "run_on_private_loop",
]

StreamMode = Literal["values", "updates"]
StreamVersion = Literal["v1", "v2"]

_T = TypeVar("_T")


@dataclass(frozen=True)
class SuperstepEmission:
    """One COMMITTED barrier, as seen by every invocation surface.

    ``values`` is the post-commit user-state snapshot (already deep-copied
    by :meth:`GraphState.snapshot`). ``updates`` is one ``{node: writes}``
    mapping per executed TASK, in canonical node order then Send task order
    — langgraph 1.2.4 emits a separate updates chunk per task, not one per
    superstep (verified empirically). ``is_seed`` marks the superstep-0
    emission, which has state but no task updates.
    """

    superstep: int
    values: Mapping[str, Any]
    updates: tuple[Mapping[str, Mapping[str, Any]], ...] = ()
    is_seed: bool = False


def _reject_running_loop(surface: str) -> None:
    """Fail closed when a sync surface is called from inside a live loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise GraphRuntimeError(
        f"{surface} needs a private event loop but one is already running in "
        "this thread; await the async surface instead (fail closed — an "
        "async-native engine never re-enters a running loop)"
    )


def run_on_private_loop(
    factory: Callable[[], Awaitable[_T]], surface: str
) -> _T:
    """Run one engine coroutine from sync code on a private event loop.

    The coroutine is built only AFTER the live-loop check, so a fail-closed
    call never leaves an un-awaited coroutine behind.
    """
    _reject_running_loop(surface)
    return asyncio.run(factory())  # type: ignore[arg-type]


def _validate_stream_contract(stream_mode: str, version: str) -> None:
    if stream_mode not in ("values", "updates"):
        raise ValueError(
            f"stream_mode {stream_mode!r} is not supported; expected "
            "'values' or 'updates' (fail closed)"
        )
    if version not in ("v1", "v2"):
        raise ValueError(
            f"version {version!r} is not supported; expected 'v1' or 'v2' "
            "(fail closed)"
        )


def _stream_chunks(
    emission: SuperstepEmission, stream_mode: str, version: str
) -> list[Any]:
    """Project one barrier into the chunks a stream surface yields."""
    if stream_mode == "values":
        chunks: list[Any] = [emission.values]
    else:
        chunks = list(emission.updates)
    if version == "v2":
        return [
            {"type": stream_mode, "ns": (), "data": chunk} for chunk in chunks
        ]
    return chunks


class InvocationSurfacesMixin:
    """Sync / async / streaming / typed-v2 projections of the run loop.

    Mixed into :class:`~dharma_swarm.graph.scheduler.CompiledGraph`, which
    supplies the state these methods project: ``canonical_order`` and the
    async generator ``_run_supersteps`` (the run lifecycle itself, defined
    in ``scheduler.py``).
    """

    canonical_order: tuple[str, ...]

    async def invoke(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> GraphRunResult | list[Any]:
        """Run to quiescence (async) and return the committed outcome.

        Default ``stream_mode="values"`` is the historical contract: the
        :class:`GraphRunResult` envelope, unchanged. ``stream_mode="updates"``
        returns the LIST of per-task update chunks the stream would have
        yielded — raw dicts under ``version="v1"``, StreamPart mappings
        (``{"type", "ns", "data"}``) under ``version="v2"`` — matching
        langgraph 1.2.4's ``Pregel.ainvoke(stream_mode=..., version=...)``.
        Run keywords (``effects``, ``resume_from``, ``persistence``, ...)
        pass through to :meth:`_run_supersteps` unchanged.
        """
        _validate_stream_contract(stream_mode, version)
        parts: list[Any] = []
        result: GraphRunResult | None = None
        async for kind, payload in self._run_supersteps(input, **kwargs):
            if kind == "result":
                result = payload
            elif stream_mode != "values":
                parts.extend(_stream_chunks(payload, stream_mode, version))
        if stream_mode == "values":
            assert result is not None  # the generator always ends with one
            return result
        return parts

    def invoke_sync(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> GraphRunResult | list[Any]:
        """Blocking twin of :meth:`invoke` on a private event loop.

        langgraph is sync-native with async twins; this engine is the mirror
        image, so the sync surface is a thin private-loop wrapper and fails
        closed (``GraphRuntimeError``) when a loop is already running in this
        thread rather than silently nesting loops or spawning hidden threads.
        """
        _validate_stream_contract(stream_mode, version)
        return run_on_private_loop(
            lambda: self.invoke(
                input, stream_mode=stream_mode, version=version, **kwargs
            ),
            "CompiledGraph.invoke_sync",
        )

    async def stream(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """Yield each COMMITTED barrier as it lands (langgraph astream parity).

        ``values`` yields the seed snapshot first, then the state after every
        committed superstep; ``updates`` yields one ``{node: writes}`` chunk
        per executed task and nothing for the seed. Failure doctrine is
        preserved by construction: the run raises out of the generator and
        nothing is yielded past the last COMMITTED barrier.
        """
        _validate_stream_contract(stream_mode, version)
        async for kind, payload in self._run_supersteps(input, **kwargs):
            if kind != "step":
                continue
            for chunk in _stream_chunks(payload, stream_mode, version):
                yield chunk

    def stream_sync(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        stream_mode: StreamMode = "values",
        version: StreamVersion = "v1",
        **kwargs: Any,
    ) -> Iterator[Any]:
        """Blocking twin of :meth:`stream`, pumped on a private event loop.

        Eagerly fails closed inside a live loop (this is a plain function
        returning a generator, so the check does not wait for the first
        ``next()``). The private loop is closed when the iterator is
        exhausted or garbage-collected.
        """
        _validate_stream_contract(stream_mode, version)
        _reject_running_loop("CompiledGraph.stream_sync")
        emitter = self.stream(
            input, stream_mode=stream_mode, version=version, **kwargs
        )

        def _pump() -> Iterator[Any]:
            loop = asyncio.new_event_loop()
            try:
                while True:
                    try:
                        yield loop.run_until_complete(emitter.__anext__())
                    except StopAsyncIteration:
                        return
            finally:
                loop.run_until_complete(emitter.aclose())
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

        return _pump()

    def _update_chunks(
        self, writes: Sequence[ChannelWrite]
    ) -> tuple[Mapping[str, Mapping[str, Any]], ...]:
        """One ``{node: writes}`` chunk per TASK, in canonical dispatch order.

        Reserved (``__``) routing writes never surface. Chunk order is the
        compiled canonical node order then Send task order — never the
        effects-driven execution order — so a stream is as execution-order
        invariant as the committed state it reports.
        """
        grouped: dict[tuple[str, int], dict[str, Any]] = {}
        for write in writes:
            if write.channel.startswith(RESERVED_PREFIX):
                continue
            grouped.setdefault((write.node_id, write.task_seq), {})[
                write.channel
            ] = copy.deepcopy(write.value)
        rank = {node: index for index, node in enumerate(self.canonical_order)}
        return tuple(
            {node_id: payload}
            for (node_id, task_seq), payload in sorted(
                grouped.items(),
                key=lambda item: (
                    rank.get(item[0][0], len(rank)),
                    item[0][0],
                    item[0][1],
                ),
            )
        )
