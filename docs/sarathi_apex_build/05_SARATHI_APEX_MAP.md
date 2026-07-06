# 05 — Sarathi Apex Map

## What Sarathi is

Sarathi is intended to be the apex continuity holon over the holon system: a
chief-of-staff seat that can observe holon/runtime state, prepare briefs, route
work, and take only code-deterministic reversible-safe actions unattended.

## What Sarathi is not yet

Sarathi is not yet a breathing holon. Current evidence shows identity and one
ported safety/wake brick, not unattended metabolism. `wake_loop_active=true` is
still forbidden until an unattended proof exists.

## Repo-side package target (Phase C)

```text
dharma_swarm/holon_system/sarathi/
  gateway.py
  pulse.py
  roster.py
  brief.py
  scoreboard.py
```

Runtime wrapper target:

```text
~/.dharma/agents/sarathi/gateway/sarathi_gateway.py
```

The runtime wrapper should import repo-owned code; it should not become the
source of truth.

## Runtime surfaces still needed

```text
~/.dharma/a2a_bus/state/sarathi.json
~/.dharma/a2a_bus/inboxes/sarathi/
~/.dharma/a2a_bus/bridge_heartbeats/sarathi.json
~/.dharma/agents/sarathi/gateway/sarathi_gateway.py
~/.dharma/agents/sarathi/HOLARCHY_CONTRACT.md
~/.dharma/agents/sarathi/SUB_HOLON_ROSTER.yaml
```

These are listed for Phase C/runtime integration; this Phase A docs commit does
not create mutable runtime state.

## Admission boundary

Sarathi may summarize and prepare operator-facing state before the overnight
proof. It may not self-promote, approve leases, push, email, trade, spend, or
alter production state unattended. The reversibility gate is code, not a model
judgment.
