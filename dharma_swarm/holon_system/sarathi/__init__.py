"""Sarathi apex holon package — SPECIFIED, NOT YET IMPLEMENTED.

Sarathi is the apex continuity holon that sits ON TOP of the holon_system organs
above (identity + runtime + kernel + authority + orchestration + transport +
responders + gateway + observability). It is NOT a parallel build.

Planned modules (see docs/sarathi_apex_build/05_SARATHI_APEX_MAP.md):
  gateway.py    -> read fleet state, reversibility-classify, select ONE lane, emit brief
  pulse.py      -> single governed wake tick wrapping holon_runtime.holon_wake_cycle
  roster.py     -> sub-holon roster (codex/fable/fugu/hermes) load + status
  brief.py      -> operator-facing daily brief generation
  scoreboard.py -> where Hermes still wins vs where Sarathi now wins (receipts only)

Deliberately EMPTY of implementation: creating stub gateway/pulse/roster/brief/
scoreboard modules now would be theater (an "apex" that does nothing). Per the
anti-sprawl harness, these are specified in the doc and built only behind proof
gates 6-10 (docs/sarathi_apex_build/06_PROOF_GATES.md). The eventual runtime
wrapper `~/.dharma/agents/sarathi/gateway/sarathi_gateway.py` must be a thin
shim: `from dharma_swarm.holon_system.sarathi.gateway import main`.

Current honest status: Sarathi = identity + committed reversibility gate + a
reusable wake-shell profile + read-only proof receipts. Body NOT breathing;
wake_loop_active is false.
"""

from __future__ import annotations

# Intentionally no exports until the modules are implemented behind proof gates.
IMPLEMENTED = False
PLANNED_MODULES = ("gateway", "pulse", "roster", "brief", "scoreboard")

__all__ = ["IMPLEMENTED", "PLANNED_MODULES"]
