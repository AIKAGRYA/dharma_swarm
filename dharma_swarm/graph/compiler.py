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

from typing import Mapping, Sequence

from dharma_swarm.graph.channels import BarrierChannel, Channel, TopicChannel
from dharma_swarm.graph.routing import BranchSpec, PathCallable, join_channel
from dharma_swarm.graph.scheduler import CompiledGraph
from dharma_swarm.graph.types import (
    END,
    START,
    TASKS_CHANNEL,
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
        self._join_edges: list[tuple[tuple[str, ...], str]] = []
        self._branches: list[BranchSpec] = []
        self._channels: list[tuple[str, Callable[[], Channel[Any]]]] = []

    def add_node(self, node_id: str, fn: NodeCallable) -> GraphBuilder:
        self._nodes.append(NodeSpec(node_id=node_id, fn=fn))
        return self

    def add_edge(self, source: str | Sequence[str], target: str) -> GraphBuilder:
        """Static edge. A list/tuple source declares an ALL-OF barrier join:
        the target fires only after every listed source has committed."""
        if isinstance(source, str):
            self._edges.append(EdgeSpec(source=source, target=target))
        else:
            self._join_edges.append((tuple(source), target))
        return self

    def add_conditional_edges(
        self,
        source: str,
        path: PathCallable,
        path_map: Mapping[str, str] | Sequence[str] | None = None,
    ) -> GraphBuilder:
        """Conditional routing: after ``source`` commits, ``path`` picks targets.

        ``path_map`` is REQUIRED (dict key->node, or list of node names which
        maps each name to itself). Passing None raises — this engine does not
        infer destinations from type hints (recorded deviation, fail closed).
        """
        if path_map is None:
            raise GraphCompileError(
                f"add_conditional_edges({source!r}, ...) requires an explicit "
                "path_map (dict or list); destination inference from return "
                "type hints is not supported (fail closed)",
                graph_id=self.graph_id,
            )
        mapping: dict[str, str]
        if isinstance(path_map, Mapping):
            mapping = dict(path_map)
        else:
            mapping = {name: name for name in path_map}
        self._branches.append(BranchSpec(source=source, path=path, path_map=mapping))
        return self

    def add_sequence(
        self,
        nodes: Sequence[NodeCallable | tuple[str, NodeCallable]],
    ) -> GraphBuilder:
        """Chain nodes with implicit edges (langgraph ``add_sequence`` parity).

        Each entry is ``(name, fn)`` or a bare callable (named from
        ``__name__``); consecutive entries get a static edge. The caller
        still wires START to the first node and the last node onward —
        langgraph 1.2.4 adds neither entry nor finish edges (empirical).
        """
        previous: str | None = None
        for entry in nodes:
            if isinstance(entry, tuple):
                node_id, fn = entry
            else:
                node_id, fn = getattr(entry, "__name__", ""), entry
            self.add_node(node_id, fn)
            if previous is not None:
                self.add_edge(previous, node_id)
            previous = node_id
        return self

    def add_channel(
        self, name: str, factory: Callable[[], Channel[Any]]
    ) -> GraphBuilder:
        self._channels.append((name, factory))
        return self

    def compile(
        self, *, allow_orphans: bool = False, allow_cycles: bool = False
    ) -> CompiledGraph:
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

        joins: list[tuple[tuple[str, ...], str]] = []
        for sources_tuple, target in self._join_edges:
            if len(sources_tuple) < 2:
                raise GraphCompileError(
                    f"list-form add_edge({list(sources_tuple)!r}, {target!r}) "
                    "needs at least two sources; use a plain edge for one",
                    graph_id=graph_id,
                )
            if target in (START, END):
                raise GraphCompileError(
                    f"barrier join target must be a node, not {target!r}",
                    graph_id=graph_id,
                )
            for endpoint in (*sources_tuple, target):
                if endpoint not in nodes:
                    raise UnknownEdgeEndpointError(
                        f"join edge {list(sources_tuple)!r} -> {target!r} "
                        f"references unknown node {endpoint!r}",
                        graph_id=graph_id,
                        source="+".join(sources_tuple),
                        target=target,
                        endpoint=endpoint,
                    )
            if len(set(sources_tuple)) != len(sources_tuple):
                raise GraphCompileError(
                    f"join edge {list(sources_tuple)!r} -> {target!r} repeats "
                    "a source",
                    graph_id=graph_id,
                )
            joins.append((tuple(sorted(sources_tuple)), target))

        branches: dict[str, BranchSpec] = {}
        for spec in self._branches:
            if spec.source != START and spec.source not in nodes:
                raise UnknownEdgeEndpointError(
                    f"conditional edge source {spec.source!r} is not a node",
                    graph_id=graph_id,
                    source=spec.source,
                    target="",
                    endpoint=spec.source,
                )
            if spec.source in branches:
                raise GraphCompileError(
                    f"node {spec.source!r} already has a conditional edge; one "
                    "branch per source in this slice",
                    graph_id=graph_id,
                )
            for key, dest in spec.path_map.items():
                if dest != END and dest not in nodes:
                    raise UnknownEdgeEndpointError(
                        f"conditional edge on {spec.source!r} maps {key!r} to "
                        f"unknown node {dest!r}",
                        graph_id=graph_id,
                        source=spec.source,
                        target=dest,
                        endpoint=dest,
                    )
            branches[spec.source] = spec

        if not any(edge.source == START for edge in edges) and START not in branches:
            raise GraphCompileError(
                f"graph {graph_id!r} has no entry edge from START",
                graph_id=graph_id,
            )

        dependency_edges = list(edges)
        for sources_tuple, target in joins:
            dependency_edges.extend(
                EdgeSpec(source=s, target=target) for s in sources_tuple
            )
        for source, spec in branches.items():
            dependency_edges.extend(
                EdgeSpec(source=source, target=dest)
                for dest in spec.destinations()
                if dest != END
            )
        canonical_order = self._topological_order(
            nodes, dependency_edges, graph_id, allow_cycles=allow_cycles
        )

        in_sources: dict[str, list[str]] = {}
        for edge in edges:
            if edge.target != END:
                in_sources.setdefault(edge.target, []).append(edge.source)
        for target in sorted(in_sources):
            sources = in_sources[target]
            if len(sources) > 1:
                raise FanInNotSupportedError(
                    f"node {target!r} has {len(sources)} plain incoming edges "
                    f"from {sorted(sources)}: declare an all-of join with "
                    f"add_edge({sorted(sources)!r}, {target!r}) instead "
                    "(fan-in to END is allowed)",
                    graph_id=graph_id,
                    target=target,
                    sources=tuple(sorted(sources)),
                )

        reachable: set[str] = set()
        frontier = [START]
        walk: dict[str, list[str]] = {}
        for edge in dependency_edges:
            walk.setdefault(edge.source, []).append(edge.target)
        for source, spec in branches.items():
            if END in spec.path_map.values():
                walk.setdefault(source, []).append(END)
        while frontier:
            current = frontier.pop()
            for target in walk.get(current, ()):
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
        if END not in reachable and not allow_cycles:
            raise GraphCompileError(
                f"END is not reachable from START in graph {graph_id!r}",
                graph_id=graph_id,
            )
        # Under allow_cycles, a graph may terminate only by exhausting the
        # superstep_cap (langgraph recursion_limit parity); END need not be
        # reachable — the iteration budget is the guaranteed terminator.

        successors: dict[str, list[str]] = {}
        for edge in edges:
            successors.setdefault(edge.source, []).append(edge.target)

        factories: dict[str, Callable[[], Channel[Any]]] = dict(declared)
        factories[TASKS_CHANNEL] = TopicChannel
        triggers: dict[str, list[str]] = {
            node_id: [trigger_channel(node_id)] for node_id in nodes
        }
        join_writes: dict[str, list[tuple[str, str]]] = {}
        for sources_tuple, target in joins:
            name = join_channel(sources_tuple, target)
            members = frozenset(sources_tuple)
            factories[name] = (
                lambda m=members: BarrierChannel(m)  # bind per join
            )
            triggers[target].append(name)
            for source in sources_tuple:
                join_writes.setdefault(source, []).append((name, source))

        return CompiledGraph(
            graph_id=graph_id,
            nodes=dict(nodes),
            canonical_order=canonical_order,
            successors={
                source: tuple(sorted(targets))
                for source, targets in successors.items()
            },
            triggers={
                node_id: tuple(chans) for node_id, chans in triggers.items()
            },
            channel_factories=factories,
            allow_orphans=allow_orphans,
            allow_cycles=allow_cycles,
            branches=dict(branches),
            join_writes={
                source: tuple(sorted(writes))
                for source, writes in join_writes.items()
            },
        )

    @staticmethod
    def _topological_order(
        nodes: dict[str, NodeSpec],
        edges: list[EdgeSpec],
        graph_id: str,
        *,
        allow_cycles: bool = False,
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
            if allow_cycles:
                # Cyclic: the ready predicate (channel version > versions_seen)
                # re-fires nodes on its own; canonical scan order falls back to
                # deterministic node-id sort. Termination is the superstep_cap
                # iteration budget, required by invoke() under a cyclic graph.
                return tuple(sorted(nodes))
            raise GraphCycleError(
                f"cycle detected among nodes {list(leftovers)}: cycles need "
                "compile(allow_cycles=True) + an explicit superstep_cap "
                "(the unlock is telos-gated iteration budgets, not a rewrite)",
                graph_id=graph_id,
                node_ids=leftovers,
            )
        return tuple(order)
