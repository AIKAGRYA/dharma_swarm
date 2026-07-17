"""Typed state, input, output, and context schemas (LG01 parity).

langgraph-StateGraph-parity typed front door over the neutral builder:
a typed schema (TypedDict / dataclass / Pydantic model) compiles to one
channel per annotated key — ``Annotated[T, reducer]`` becomes a
:class:`ReducerChannel` with a batching-invariant fold, every other key a
:class:`LastValueChannel` (>1 concurrent write fails closed, langgraph
``InvalidUpdateError`` parity). Input/output schemas are projections
(filter on seed, filter on result — langgraph 1.2.4 FILTERS undeclared
input keys, it does not reject them; verified empirically 2026-07-17).
Context is runtime-injected into nodes that declare a second positional
parameter; it is never state and never checkpointed.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import contextvars
import dataclasses
import inspect
from typing import (
    Annotated,
    Any,
    Callable,
    Mapping,
    get_args,
    get_origin,
    get_type_hints,
)

from dharma_swarm.graph.channels import Channel, LastValueChannel, ReducerChannel
from dharma_swarm.graph.compiler import GraphBuilder
from dharma_swarm.graph.scheduler import CompiledGraph
from dharma_swarm.graph.state import state_digest
from dharma_swarm.graph.types import GraphRunResult

__all__ = [
    "RemainingSteps",
    "SchemaError",
    "TypedCompiledGraph",
    "TypedStateGraph",
    "context_schema",
    "input_schema",
    "output_schema",
    "typed_state_schema",
]


class RemainingSteps:
    """Managed-value marker: the field receives the remaining superstep budget.

    Annotate a state field with this CLASS (``remaining: RemainingSteps``) and
    every pull task observes ``superstep_cap - superstep`` in its input
    snapshot — langgraph ``RemainingSteps`` parity (limit N ⇒ first step sees
    N-1; empirical 1.2.4). The field is plan-time injected: it is never a
    channel, never written, never checkpointed, and the budget resets on
    every invoke (resume included).
    """

_ACTIVE_CONTEXT: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "dharmagraph_active_context", default=None
)


class SchemaError(TypeError):
    """A schema class or a value failed schema interpretation (fail closed)."""


def _schema_fields(schema: type) -> dict[str, tuple[Any, Callable[[Any, Any], Any] | None]]:
    """Map field name -> (annotation, reducer|None) for a supported schema.

    Supported: TypedDict (via ``get_type_hints(include_extras=True)``),
    dataclasses, and Pydantic v2 models (``model_fields`` + annotations).
    ``Annotated[T, reducer]`` marks a reducer field when the FIRST metadata
    entry is callable (langgraph convention).
    """
    if not isinstance(schema, type):
        raise SchemaError(
            f"schema must be a class, got {type(schema).__name__!r}"
        )
    try:
        hints = get_type_hints(schema, include_extras=True)
    except NameError:
        # A schema defined inside a function cannot resolve OUR marker
        # through its module globals under `from __future__ import
        # annotations` — retry with the marker supplied, then fail closed.
        try:
            hints = get_type_hints(
                schema,
                include_extras=True,
                localns={"RemainingSteps": RemainingSteps},
            )
        except Exception as exc:
            raise SchemaError(
                f"cannot resolve type hints for schema {schema.__name__!r}: {exc}"
            ) from exc
    except Exception as exc:  # unresolvable forward refs fail closed
        raise SchemaError(
            f"cannot resolve type hints for schema {schema.__name__!r}: {exc}"
        ) from exc
    if dataclasses.is_dataclass(schema):
        names = [f.name for f in dataclasses.fields(schema)]
    elif hasattr(schema, "model_fields"):  # pydantic v2
        names = list(schema.model_fields)
    elif hasattr(schema, "__annotations__"):  # TypedDict / plain annotations
        names = [n for n in hints if not n.startswith("_")]
    else:
        raise SchemaError(
            f"unsupported schema kind {schema!r}: expected TypedDict, "
            "dataclass, or Pydantic model"
        )
    fields: dict[str, tuple[Any, Callable[[Any, Any], Any] | None]] = {}
    for name in names:
        annotation = hints.get(name, Any)
        reducer: Callable[[Any, Any], Any] | None = None
        if get_origin(annotation) is Annotated:
            args = get_args(annotation)
            metadata = args[1:]
            if metadata and callable(metadata[0]):
                reducer = metadata[0]
            annotation = args[0]
        fields[name] = (annotation, reducer)
    if not fields:
        raise SchemaError(f"schema {schema.__name__!r} declares no fields")
    return fields


def _empty_value(annotation: Any) -> Any:
    origin = get_origin(annotation) or annotation
    try:
        if isinstance(origin, type):
            return origin()
    except Exception:
        return None
    return None


def typed_state_schema(
    schema: type,
) -> dict[str, Callable[[], Channel[Any]]]:
    """Compile a typed schema into channel factories, one per annotated key.

    ``Annotated[T, reducer]`` -> :class:`ReducerChannel` (batching-invariant
    fold, empty value from ``T()``); every other key -> LastValueChannel.
    Managed-value fields (:class:`RemainingSteps`) get NO channel — they are
    plan-time injected, never state.
    """
    factories: dict[str, Callable[[], Channel[Any]]] = {}
    for name, (annotation, reducer) in _schema_fields(schema).items():
        if annotation is RemainingSteps:
            continue
        if reducer is not None:
            empty = _empty_value(annotation)
            factories[name] = (
                lambda r=reducer, e=empty: ReducerChannel(r, empty_value=e)
            )
        else:
            factories[name] = LastValueChannel
    return factories


def managed_remaining_field(schema: type) -> str | None:
    """The schema's :class:`RemainingSteps` field name, if declared (max one)."""
    matches = [
        name
        for name, (annotation, _reducer) in _schema_fields(schema).items()
        if annotation is RemainingSteps
    ]
    if len(matches) > 1:
        raise SchemaError(
            f"schema declares {len(matches)} RemainingSteps fields "
            f"{sorted(matches)}; at most one is supported (fail closed)"
        )
    return matches[0] if matches else None


def input_schema(schema: type) -> frozenset[str]:
    """The seed projection: keys OUTSIDE this set are filtered from input
    (langgraph 1.2.4 parity: undeclared input keys are dropped, not errors)."""
    return frozenset(_schema_fields(schema))


def output_schema(schema: type) -> frozenset[str]:
    """The result projection: only these keys appear in the typed result."""
    return frozenset(_schema_fields(schema))


def context_schema(schema: type) -> type:
    """Declare the runtime-context type nodes may receive as their second
    positional parameter. Context is injected per-invoke, never part of
    state, never checkpointed."""
    _schema_fields(schema)  # validate shape now, fail closed at declaration
    return schema


def current_context() -> Any:
    """The invoking run's context object (None outside a typed invoke)."""
    return _ACTIVE_CONTEXT.get()


def _wants_context(fn: Callable[..., Any]) -> bool:
    try:
        parameters = [
            p
            for p in inspect.signature(fn).parameters.values()
            if p.kind
            in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
    except (TypeError, ValueError):
        return False
    return len(parameters) >= 2


def _context_adapter(node_id: str, fn: Callable[..., Any]) -> Callable[[Any], Any]:
    def adapter(state: Mapping[str, Any]) -> Any:
        return fn(state, _ACTIVE_CONTEXT.get())

    adapter.__name__ = f"ctx_adapter[{node_id}]"
    return adapter


class TypedStateGraph:
    """Typed front door over :class:`GraphBuilder` (langgraph StateGraph parity).

    Declares channels from the state schema at construction; nodes with a
    second positional parameter receive the per-invoke context object.
    """

    def __init__(
        self,
        state: type,
        *,
        input: type | None = None,
        output: type | None = None,
        context: type | None = None,
        graph_id: str = "typed-graph",
    ) -> None:
        self._builder = GraphBuilder(graph_id)
        self._state_fields = frozenset(_schema_fields(state))
        self._remaining_field = managed_remaining_field(state)
        for name, factory in typed_state_schema(state).items():
            self._builder.add_channel(name, factory)
        # langgraph parity (empirical): the state schema is the DEFAULT
        # input projection — undeclared seed keys are dropped, not errors.
        # Managed fields are never seedable, so they stay outside the set.
        self._input_keys = (
            input_schema(input)
            if input is not None
            else self._state_fields - {self._remaining_field}
        )
        self._output_keys = output_schema(output) if output is not None else None
        self._context_type = context_schema(context) if context is not None else None
        for keys, label in (
            (self._input_keys, "input"),
            (self._output_keys, "output"),
        ):
            if keys is not None and not keys <= self._state_fields:
                raise SchemaError(
                    f"{label} schema keys {sorted(keys - self._state_fields)} "
                    "are not state-schema keys (fail closed)"
                )

    def add_node(self, node_id: str, fn: Callable[..., Any]) -> "TypedStateGraph":
        wrapped = _context_adapter(node_id, fn) if _wants_context(fn) else fn
        self._builder.add_node(node_id, wrapped)
        return self

    def add_edge(self, source: Any, target: str) -> "TypedStateGraph":
        self._builder.add_edge(source, target)
        return self

    def add_conditional_edges(
        self, source: str, path: Callable[..., Any], path_map: Any = None
    ) -> "TypedStateGraph":
        self._builder.add_conditional_edges(source, path, path_map)
        return self

    def compile(self, **kwargs: Any) -> "TypedCompiledGraph":
        inner = self._builder.compile(**kwargs)
        if self._remaining_field is not None:
            inner = dataclasses.replace(
                inner, managed_remaining=self._remaining_field
            )
        return TypedCompiledGraph(
            inner,
            input_keys=self._input_keys,
            output_keys=self._output_keys,
            context_type=self._context_type,
        )


class TypedCompiledGraph:
    """A compiled typed graph: projections + context around ``invoke``."""

    def __init__(
        self,
        inner: CompiledGraph,
        *,
        input_keys: frozenset[str] | None,
        output_keys: frozenset[str] | None,
        context_type: type | None,
    ) -> None:
        self.inner = inner
        self.input_keys = input_keys
        self.output_keys = output_keys
        self.context_type = context_type

    async def invoke(
        self,
        input: Mapping[str, Any] | None = None,
        *,
        context: Any = None,
        **kwargs: Any,
    ) -> GraphRunResult:
        if context is not None and self.context_type is None:
            raise SchemaError(
                "invoke(context=...) requires a context schema declaration"
            )
        seed = input
        if (
            seed is not None
            and self.input_keys is not None
            and isinstance(seed, Mapping)
        ):
            # Non-mapping inputs (Command(resume=...)) bypass projection and
            # reach the engine's own input handling unchanged.
            seed = {k: v for k, v in seed.items() if k in self.input_keys}
        token = _ACTIVE_CONTEXT.set(context)
        try:
            result = await self.inner.invoke(input=seed, **kwargs)
        finally:
            _ACTIVE_CONTEXT.reset(token)
        if self.output_keys is not None:
            projected = {
                k: v for k, v in result.state.items() if k in self.output_keys
            }
            # Keep the result self-consistent: state_digest always digests
            # the state THIS result carries (checkpoints keep the full one).
            result = dataclasses.replace(
                result, state=projected, state_digest=state_digest(projected)
            )
        return result
