"""Minimal subgraph-as-node with one-level parent command routing (LG08b).

Scope is exactly what the ``command_parent`` facet measures (spec §4-S8):
a compiled child graph runs as ONE parent node, and a child node returning
``Command(graph=Command.PARENT)`` aborts the child run and hands the
command to the PARENT — update applied through the parent's reducers,
``goto`` triggering parent nodes. General subgraph composition (namespaced
checkpoints, shared-state projection contracts, LG23) is out of scope.

langgraph 1.2.4 parity, verified empirically 2026-07-17:
- the child's LOCAL writes never reach parent state; only the parent
  command's ``update`` lands;
- a parent command with no parent graph bubbles to the caller as
  ``ParentCommand``.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from dharma_swarm.graph.effects import EffectsProvider
from dharma_swarm.graph.routing import Command, ParentCommand
from dharma_swarm.graph.scheduler import CompiledGraph

__all__ = ["as_node"]


def as_node(
    child: CompiledGraph,
    *,
    effects_factory: Callable[[], EffectsProvider] | None = None,
    superstep_cap: int | None = None,
) -> Callable[[Mapping[str, Any]], Any]:
    """Wrap a compiled child graph as a parent node callable.

    The child seeds from the parent's state snapshot (shared channel names;
    unknown keys fail closed inside the child's own seed validation). A
    normally-completing child returns its final state as the parent node's
    update. A child node returning ``Command(graph=Command.PARENT)`` aborts
    the child run (nothing commits there — LG06 atomicity) and the carried
    command becomes THIS node's return value, so the parent engine applies
    ``update``/``goto`` through its ordinary Command path — exactly one
    level of bubbling, langgraph parity.

    ``effects_factory`` supplies the child's effects provider per firing
    (pass a seeded factory for deterministic child replay); default is the
    child engine's live default.
    """

    async def run_subgraph(state: Mapping[str, Any]) -> Any:
        seed = dict(state)
        kwargs: dict[str, Any] = {}
        if effects_factory is not None:
            kwargs["effects"] = effects_factory()
        if superstep_cap is not None:
            kwargs["superstep_cap"] = superstep_cap
        try:
            result = await child.invoke(input=dict(seed), **kwargs)
        except ParentCommand as bubbled:
            command = bubbled.command
            return Command(
                update=command.update,
                goto=command.goto,
            )
        # Return child DELTAS, not the accumulated snapshot: a shared
        # reducer channel would otherwise fold the parent's own seed back
        # into itself (['entry'] seeded, child appends 'child' → returning
        # ['entry','child'] would re-append 'entry'). Unchanged keys emit no
        # write; a list extending its seed emits only the suffix. Non-list
        # reducer channels whose value changed still emit the full child
        # value — a recorded caveat for exotic reducers, not for last-value.
        update: dict[str, Any] = {}
        for key, value in dict(result.state).items():
            if key in seed:
                seeded = seed[key]
                if value == seeded:
                    continue
                if (
                    isinstance(value, list)
                    and isinstance(seeded, list)
                    and value[: len(seeded)] == seeded
                ):
                    update[key] = value[len(seeded) :]
                    continue
            update[key] = value
        return update

    run_subgraph.__name__ = f"subgraph[{child.graph_id}]"
    return run_subgraph
