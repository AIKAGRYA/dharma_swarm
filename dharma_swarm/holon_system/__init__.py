"""dharma_swarm.holon_system — product-shaped facade over the existing holon substrate.

This package is a NAVIGATION + COMPATIBILITY layer, not a rewrite. Every module
here is a thin re-export of code that already lives elsewhere in `dharma_swarm`.
The point is that a future agent can read one package tree and see the whole
"own-Hermes" holon system, instead of hunting scattered `holon_*`, `operator_core`,
`persistent_agent`, `agent_registry`, and `scripts/runtime` files.

Doctrine (see docs/sarathi_apex_build/03_HOLON_SYSTEM_CODE_MAP.md):
- NO new orchestrator, model router, task store, A2A bus, or receipt spine.
- Facades import existing symbols; they never redefine behavior.
- Subpackages that have no implemented owner yet (transport, responders,
  gateway, cli, api, sarathi) say so explicitly and point at the real owner.

Subpackages:
  identity/        -> agent_registry, external_agent_registration, load_holon
  runtime/         -> holon_bridge, holon_runtime, holon_persistence, runtime_provider
  kernel/          -> operator_core.living_agent_kernel
  authority/       -> operator_core.execution_lease, operator_core.reversibility_gate
  orchestration/   -> holon_orchestrate
  observability/   -> holon_health, holon_canonical_state
  transport/       -> scripts/runtime/a2a_*.py (runtime scripts; no repo lib yet)
  responders/      -> scripts/runtime/*semantic_responder.py (runtime scripts)
  gateway/         -> scripts/runtime/codex_composer_wake_loop.py wake shell
  cli/             -> dharma_swarm.dgc_cli
  api/             -> api/routers/holon.py
  sarathi/         -> apex holon package (SPECIFIED, not yet implemented)
"""

from __future__ import annotations

__all__ = [
    "identity",
    "runtime",
    "kernel",
    "authority",
    "orchestration",
    "observability",
    "transport",
    "responders",
    "gateway",
    "cli",
    "api",
    "sarathi",
]
