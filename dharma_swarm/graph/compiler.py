"""GraphBuilder + compile-time validation (Candidate Slice A).

The builder is a dumb recorder; ALL validation happens in ``compile()`` in
one documented order, so error precedence is deterministic and testable:

1. channel declarations (reserved names, duplicates)
2. node ids (reserved: START/END, ``__`` prefix, ``+``, empty)
3. duplicate nodes
4. edges (exact duplicates dedupe silently — pinned by test; END-as-source,
   START-as-target, and direct START->END rejected; unknown endpoints)
5. START has at least one outgoing edge
6. cycles (Kahn's algorithm, sorted pops -> deterministic canonical order);
   removing THIS check + budgeting ``superstep_cap`` is the designed cycle
   unlock — the scheduler's ready predicate needs no change
7. ordinary fan-in (>1 in-edge to one node) rejected — join semantics belong
   to a future barrier channel type, not to the ready predicate; fan-in to
   END is allowed (END never fires)
8. reachability from START (orphans unless ``allow_orphans=True``; END must
   always be reachable)

claim_mode: candidate / test_only — not wired into production dispatch.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from dharma_swarm.graph.channels import Channel
from dharma_swarm.graph.scheduler import CompiledGraph
from dharma_swarm.graph.types import (
    END,
    START,
    EdgeSpec,
    NodeCallable,
    NodeSpec,
    trigger_channel,
)

__all__ = [
    "DuplicateNodeError",
    "FanInNotSupportedError",
    "GraphBuilder",
    "GraphCompileError",
    "GraphCycleError",
    "OrphanNodeError",
    "UnknownEdgeEndpointError",
]

logger = logging.getLogger(__name__)

_RESERVED_ENDPOINTS = frozenset({START, END})


class GraphCompileError(ValueError):
    """A graph definition failed compile-time validation."""

    def __init__(self, message: str, *, graph_id: str) -> None:
        super().__init__(message)
        self.graph_id = graph_id


class DuplicateNodeError(GraphCompileError):
    def __init__(self, message: str, *, graph_id: str, node_id: str) -> None:
        super().__init__(message, graph_id=graph_id)
        self.node_id = node_id


class UnknownEdgeEndpointError(GraphCompileError):
    def __init__(
        self, message: str, *, graph_id: str, source: str, target: str, endpoint: str
    ) -> None:
        super().__init__(message, graph_id=graph_id)
        self.source = source
        self.target = target
        self.endpoint = endpoint


class OrphanNodeError(GraphCompileError):
    def __init__(
        self, message: str, *, graph_id: str, node_ids: tuple[str, ...]
    ) -> None:
        super().__init__(message, graph_id=graph_id)
        self.node_ids = node_ids


class GraphCycleError(GraphCompileError):
    def __init__(
        self, message: str, *, graph_id: str, node_ids: tuple[str, ...]
    ) -> None:
        super().__init__(message, graph_id=graph_id)
        self.node_ids = node_ids


class FanInNotSupportedError(GraphCompileError):
    def __init__(
        self, message: str, *, graph_id: str, target: str, sources: tuple[str, ...]
    ) -> None:
        super().__init__(message, graph_id=graph_id)
        self.target = target
        self.sources = sources


class GraphBuilder:
    """Fluent recorder for nodes, edges, and explicit channel declarations."""

    def __init__(self, graph_id: str = "graph") -> None:
        self.graph_id = graph_id
        self._nodes: list[NodeSpec] = []
        self._edges: list[EdgeSpec] = []
        self._channels: list[tuple[str, Callable[[], Channel[Any]]]] = []

    def add_node(self, node_id: str, fn: NodeCallable) -> GraphBuilder:
        self._nodes.append(NodeSpec(node_id=node_id, fn=fn))
        return self

    def add_edge(self, source: str, target: str) -> GraphBuilder:
        self._edges.append(EdgeSpec(source=source, target=target))
        return self

    def add_channel(
        self, name: str, factory: Callable[[], Channel[Any]]
    ) -> GraphBuilder:
        self._channels.append((name, factory))
        return self

    def compile(self, *, allow_orphans: bool = False) -> CompiledGraph:
        graph_id = self.graph_id

        declared: dict[str, Callable[[], Channel[Any]]] = {}
        for name, factory in self._channels:
            if not name or name.startswith("__"):
                raise GraphCompileError(
                    f"channel name {name!r} is reserved ('__'-prefixed and empty "
                    "names belong to the runtime)",
                    graph_id=graph_id,
                )
            if name in declared:
                raise GraphCompileError(
                    f"channel {name!r} declared more than once", graph_id=graph_id
                )
            declared[name] = factory

        for spec in self._nodes:
            node_id = spec.node_id
            if (
                not node_id
                or node_id in _RESERVED_ENDPOINTS
                or node_id.startswith("__")
                or "+" in node_id
            ):
                raise GraphCompileError(
                    f"node id {node_id!r} is reserved (START/END, '__' prefixes, "
                    "'+', and empty ids belong to the runtime)",
                    graph_id=graph_id,
                )

        nodes: dict[str, NodeSpec] = {}
        for spec in self._nodes:
            if spec.node_id in nodes:
                raise DuplicateNodeError(
                    f"duplicate node id {spec.node_id!r} in graph {graph_id!r}",
                    graph_id=graph_id,
                    node_id=spec.node_id,
                )
            nodes[spec.node_id] = spec

        edges: list[EdgeSpec] = []
        seen_edges: set[tuple[str, str]] = set()
        for edge in self._edges:
            if edge.source == END:
                raise GraphCompileError(
                    f"END cannot be an edge source ({edge.source!r} -> "
                    f"{edge.target!r})",
                    graph_id=graph_id,
                )
            if edge.target == START:
                raise GraphCompileError(
                    f"START cannot be an edge target ({edge.source!r} -> "
                    f"{edge.target!r})",
                    graph_id=graph_id,
                )
            if edge.source == START and edge.target == END:
                raise GraphCompileError(
                    "direct START -> END edge is rejected in this slice (an "
                    "empty graph has nothing to run)",
                    graph_id=graph_id,
                )
            for endpoint in (edge.source, edge.target):
                if endpoint not in _RESERVED_ENDPOINTS and endpoint not in nodes:
                    raise UnknownEdgeEndpointError(
                        f"edge {edge.source!r} -> {edge.target!r} references "
                        f"unknown node {endpoint!r}",
                        graph_id=graph_id,
                        source=edge.source,
                        target=edge.target,
                        endpoint=endpoint,
                    )
            key = (edge.source, edge.target)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append(edge)

        if not any(edge.source == START for edge in edges):
            raise GraphCompileError(
                f"graph {graph_id!r} has no entry edge from START",
                graph_id=graph_id,
            )

        canonical_order = self._topological_order(nodes, edges, graph_id)

        in_sources: dict[str, list[str]] = {}
        for edge in edges:
            if edge.target != END:
                in_sources.setdefault(edge.target, []).append(edge.source)
        for target in sorted(in_sources):
            sources = in_sources[target]
            if len(sources) > 1:
                raise FanInNotSupportedError(
                    f"node {target!r} has {len(sources)} incoming edges from "
                    f"{sorted(sources)}: ordinary fan-in joins require barrier "
                    "channels and are not yet supported in this slice (fan-in "
                    "to END is allowed)",
                    graph_id=graph_id,
                    target=target,
                    sources=tuple(sorted(sources)),
                )

        reachable: set[str] = set()
        frontier = [START]
        successors: dict[str, list[str]] = {}
        for edge in edges:
            successors.setdefault(edge.source, []).append(edge.target)
        while frontier:
            current = frontier.pop()
            for target in successors.get(current, ()):
                if target not in reachable:
                    reachable.add(target)
                    if target != END:
                        frontier.append(target)

        orphans = tuple(sorted(set(nodes) - reachable))
        if orphans and not allow_orphans:
            raise OrphanNodeError(
                f"nodes unreachable from START: {list(orphans)}; pass "
                "allow_orphans=True to permit (they will never fire)",
                graph_id=graph_id,
                node_ids=orphans,
            )
        if END not in reachable:
            raise GraphCompileError(
                f"END is not reachable from START in graph {graph_id!r}",
                graph_id=graph_id,
            )

        return CompiledGraph(
            graph_id=graph_id,
            nodes=dict(nodes),
            canonical_order=canonical_order,
            successors={
                source: tuple(sorted(targets))
                for source, targets in successors.items()
            },
            triggers={
                node_id: (trigger_channel(node_id),) for node_id in nodes
            },
            channel_factories=dict(declared),
            allow_orphans=allow_orphans,
        )

    @staticmethod
    def _topological_order(
        nodes: dict[str, NodeSpec], edges: list[EdgeSpec], graph_id: str
    ) -> tuple[str, ...]:
        in_degree = {node_id: 0 for node_id in nodes}
        internal_successors: dict[str, list[str]] = {}
        for edge in edges:
            if edge.source in nodes and edge.target in nodes:
                in_degree[edge.target] += 1
                internal_successors.setdefault(edge.source, []).append(edge.target)

        queue = sorted(n for n, degree in in_degree.items() if degree == 0)
        order: list[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for target in sorted(internal_successors.get(current, ())):
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)
                    queue.sort()

        if len(order) != len(nodes):
            leftovers = tuple(sorted(set(nodes) - set(order)))
            raise GraphCycleError(
                f"cycle detected among nodes {list(leftovers)}: cycles are not "
                "yet supported in this slice (acyclic-only scheduler; the "
                "unlock is telos-gated iteration budgets, not a rewrite)",
                graph_id=graph_id,
                node_ids=leftovers,
            )
        return tuple(order)
