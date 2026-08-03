"""Memory organ for the Sarathi apex — a governed read, never a write.

Sarathi had no memory at all: before this organ, ``grep -c memory_kernel`` over
``dharma_swarm/holon_system/sarathi/*.py`` returned 0, even though
``MemoryKernel`` is the canonical front door for agent memory per ``CLAUDE.md``.
She planned every wake cycle from the backlog alone, with no recall.

This organ reads through that front door and nothing else. It does not open a
store, walk a path, or write anything: ``MemoryKernel.preview_memory_pack``
performs the admission and returns a :class:`MemoryContextPack` whose own
warnings state the contract (``preview_only_no_runtime_prompt_injection``,
``preview_does_not_promote_or_write_memory``).

The kernel is **injected**, matching ``BootPack``'s discipline — the organ never
constructs one, so a caller without memory configured degrades to an empty
excerpt instead of fabricating recall. Source stays thin per Gate-9: no runtime
paths, no liveness constants, no unattended claims.
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.memory_kernel import (
    MemoryContextBudget,
    MemoryContextPack,
    render_memory_context_pack_markdown,
)

# The apex seat reads under a deliberately tight budget. Defaults that matter,
# each verified live against `MemoryContextBudget`:
#   include_content=False        -- carry references, not payloads
#   require_context_admissible   -- an atom must be marked admissible to appear
#   allow_projections=False      -- never plan from a projection of a source
#   allow_high_risk=False        -- exclude high canon/PII risk atoms
#   reject_stale=True            -- tightened here; an apex seat planning
#                                   delegations must not recall stale state
SARATHI_MEMORY_BUDGET = MemoryContextBudget(
    max_candidate_atoms=50,
    max_admitted_atoms=8,
    max_total_chars=4000,
    max_atom_chars=600,
    include_content=False,
    require_context_admissible=True,
    allow_projections=False,
    allow_high_risk=False,
    reject_stale=True,
)


def build_memory_pack(
    kernel: Any | None,
    *,
    budget: MemoryContextBudget | None = None,
    query: Any | None = None,
) -> MemoryContextPack | None:
    """Read a governed memory pack through the kernel's front door.

    Returns ``None`` when no kernel is injected — the honest representation of
    "this deployment has no memory configured". Callers must not substitute an
    empty pack for a missing one; the two mean different things in a brief.
    """
    if kernel is None:
        return None
    return kernel.preview_memory_pack(budget=budget or SARATHI_MEMORY_BUDGET, query=query)


def render_memory_excerpt(pack: MemoryContextPack | None) -> str:
    """Render a pack for injection into ``BootPack.memory_excerpt``.

    A missing kernel renders empty. A pack that admitted nothing renders its
    own markdown anyway, because "memory was consulted and admitted 0 atoms"
    is a materially different fact from "memory was never consulted", and the
    operator brief must be able to tell them apart.
    """
    if pack is None:
        return ""
    return render_memory_context_pack_markdown(pack)


def memory_pack_summary(pack: MemoryContextPack | None) -> dict[str, Any]:
    """Machine-readable counts for the operator brief and receipts.

    ``consulted`` is the flag that distinguishes a deployment with no memory
    from one whose policy admitted nothing.
    """
    if pack is None:
        return {"consulted": False, "candidates": 0, "admitted": 0, "omitted": 0}
    return {
        "consulted": True,
        "candidates": pack.candidate_count,
        "admitted": pack.admitted_count,
        "omitted": pack.omitted_count,
        "truncated": pack.candidate_truncated,
        "warnings": list(pack.warnings),
    }
