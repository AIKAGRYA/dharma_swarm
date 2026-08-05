"""Config, context, and runtime injection into nodes (LG30 parity).

langgraph ``langgraph/runtime.py`` + ``langgraph/config.py`` parity, verified
empirically against installed 1.2.4 (2026-08-05):

- Every accessor (:func:`get_runtime`, :func:`get_config`, :func:`get_store`,
  :func:`get_stream_writer`) FAILS CLOSED outside a running node: langgraph
  raises ``RuntimeError("Called get_config outside of a runnable context")``
  from all four because they funnel through ``get_config``. DharmaGraph
  raises :class:`RuntimeAccessError`, which is a ``GraphRuntimeError`` and
  therefore a ``RuntimeError`` — so ``except RuntimeError`` behaves
  identically on both arms.
- Inside a node the accessors resolve; ``get_store()`` returns ``None`` when
  the graph was invoked without a store, and ``get_runtime().context`` is
  ``None`` when a context schema was declared but no context was passed
  (both non-raising — empirical langgraph 1.2.4 behavior, NOT an error).
- ``execution_info`` identifies the executing task, ``previous`` is ``None``
  for ordinary graph runs (it carries prior output only for the functional
  entrypoint API, which this slice does not claim).

Binding discipline mirrors ``interrupts.push_frame`` / ``pop_frame``: the
executor binds ONE runtime per task inside the task's own asyncio context,
so concurrent tasks of a superstep never observe each other's runtime and
nothing leaks outside node execution. The runtime is never state, never a
channel, never checkpointed, and never digested.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import contextvars
import hashlib
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

from dharma_swarm.graph.errors import GraphRuntimeError
from dharma_swarm.graph.store import KVStore

__all__ = [
    "ExecutionInfo",
    "GraphRuntime",
    "RuntimeAccessError",
    "bind_runtime",
    "get_config",
    "get_runtime",
    "get_store",
    "get_stream_writer",
    "normalized_config",
    "unbind_runtime",
]

_OUTSIDE_MESSAGE = (
    "Called graph runtime accessor outside of a running node (fail closed); "
    "config/context/store/stream_writer exist only for the duration of a task"
)


class RuntimeAccessError(GraphRuntimeError):
    """An injection accessor was called outside a running node (fail closed).

    Subclasses ``GraphRuntimeError`` (hence ``RuntimeError``) so callers that
    catch ``RuntimeError`` — the type langgraph raises — behave identically
    against either engine.
    """


@dataclass(frozen=True, slots=True)
class ExecutionInfo:
    """Read-only identity of the currently executing task.

    DharmaGraph-native vocabulary (``run_id`` / ``node_id`` / ``task_seq`` /
    ``superstep``) deliberately matches ``GraphRunEvent`` and
    ``derive_graph_side_effect_key`` so receipts, interrupts, and runtime
    injection all name a task the same way. ``task_id`` is the stable digest
    of that identity — the portable equivalent of langgraph's opaque
    ``ExecutionInfo.task_id`` — and ``node_attempt`` is 1-indexed.
    """

    run_id: str
    node_id: str
    task_seq: int = 0
    superstep: int = 0
    node_attempt: int = 1

    @property
    def task_id(self) -> str:
        """Deterministic 32-hex id for ``(run, node, task_seq, superstep)``."""
        digest = hashlib.sha256(
            f"{self.run_id}:{self.node_id}:{self.task_seq}:{self.superstep}".encode(
                "utf-8"
            )
        ).hexdigest()
        return digest[:32]


def _noop_stream_writer(_chunk: Any) -> None:
    """Default writer: accepts and discards (langgraph no-op writer parity)."""


def normalized_config(
    config: Mapping[str, Any] | None, *, thread_id: str | None = None
) -> dict[str, Any]:
    """Build the RunnableConfig-shaped mapping nodes observe.

    langgraph 1.2.4 hands nodes a config carrying ``callbacks`` /
    ``configurable`` / ``metadata`` (empirical), with the invoking thread id
    merged into ``configurable``. Caller-supplied keys are preserved
    verbatim; only missing structure is filled in, and an explicit
    ``configurable.thread_id`` always wins over the invoke's ``thread_id``
    so a caller can never have their own config silently overwritten.
    """
    if config is not None and not isinstance(config, Mapping):
        raise RuntimeAccessError(
            f"invoke(config=...) must be a Mapping, got "
            f"{type(config).__name__!r} (fail closed)"
        )
    resolved: dict[str, Any] = dict(config or {})
    raw_configurable = resolved.get("configurable")
    if raw_configurable is not None and not isinstance(raw_configurable, Mapping):
        raise RuntimeAccessError(
            "invoke(config={'configurable': ...}) must be a Mapping, got "
            f"{type(raw_configurable).__name__!r} (fail closed)"
        )
    configurable = dict(raw_configurable or {})
    if thread_id is not None:
        configurable.setdefault("thread_id", thread_id)
    resolved["configurable"] = configurable
    resolved.setdefault("callbacks", None)
    resolved.setdefault("metadata", {})
    return resolved


@dataclass(frozen=True)
class GraphRuntime:
    """Everything injected into a node that is not graph state.

    ``context`` is the caller's per-invoke context object, ``store`` the
    injected :class:`KVStore` (``None`` when none was passed),
    ``stream_writer`` the custom-stream sink, ``previous`` the prior
    entrypoint output (always ``None`` for graph runs this slice), and
    ``execution_info`` the executing task's identity. ``config`` is the
    RunnableConfig-shaped mapping :func:`get_config` returns.
    """

    context: Any = None
    store: KVStore | None = None
    stream_writer: Callable[[Any], None] = _noop_stream_writer
    previous: Any = None
    execution_info: ExecutionInfo | None = None
    config: Mapping[str, Any] = field(default_factory=dict)

    def for_task(
        self,
        *,
        run_id: str,
        node_id: str,
        task_seq: int = 0,
        superstep: int = 0,
    ) -> GraphRuntime:
        """This runtime refined with one task's :class:`ExecutionInfo`.

        The run-scoped template is built once per invoke; the executor calls
        this per task so ``execution_info`` is never shared or stale.
        """
        return replace(
            self,
            execution_info=ExecutionInfo(
                run_id=run_id,
                node_id=node_id,
                task_seq=task_seq,
                superstep=superstep,
            ),
        )


_RUNTIME_CTX: contextvars.ContextVar[GraphRuntime | None] = contextvars.ContextVar(
    "dharmagraph_runtime", default=None
)


def bind_runtime(runtime: GraphRuntime) -> contextvars.Token:
    """Executor-only: bind the running task's runtime."""
    return _RUNTIME_CTX.set(runtime)


def unbind_runtime(token: contextvars.Token) -> None:
    """Executor-only: unbind the running task's runtime."""
    _RUNTIME_CTX.reset(token)


def get_runtime() -> GraphRuntime:
    """The running node's :class:`GraphRuntime`.

    Raises :class:`RuntimeAccessError` outside a node — langgraph
    ``get_runtime`` raises ``RuntimeError`` in the same position.
    """
    runtime = _RUNTIME_CTX.get()
    if runtime is None:
        raise RuntimeAccessError(_OUTSIDE_MESSAGE)
    return runtime


def get_config() -> Mapping[str, Any]:
    """The running node's RunnableConfig-shaped mapping.

    Always carries a ``configurable`` sub-mapping, so callers may read
    ``get_config()["configurable"].get(...)`` without defensive branching
    (langgraph 1.2.4 returns ``callbacks`` / ``configurable`` / ``metadata``).
    """
    return get_runtime().config


def get_store() -> KVStore | None:
    """The injected store, or ``None`` when the run was given no store.

    Raises outside a node; returns ``None`` inside a node whose run carried
    no store — exactly langgraph 1.2.4 (a graph compiled without a store
    yields ``None`` rather than raising).
    """
    return get_runtime().store


def get_stream_writer() -> Callable[[Any], None]:
    """The custom-stream sink; a no-op writer when the run had none."""
    return get_runtime().stream_writer
