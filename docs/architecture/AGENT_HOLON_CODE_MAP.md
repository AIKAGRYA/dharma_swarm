---
title: Agent Holon Call-Chain Index
date: 2026-07-13
status: reference
---

# Agent Holon Call-Chain Index

Start at [`../persistent_agents/README.md`](../persistent_agents/README.md) for locked terminology, runtime-family
boundaries, and the document/code map. The deeper July snapshot remains
[`HOLON_RUNTIME_FULL_ESTATE_MAP.md`](HOLON_RUNTIME_FULL_ESTATE_MAP.md), superseded
for first orientation/current counts. Code/tests own implementation; onboarding
and `docs/state/LIVE_OPS_DASHBOARD.md` own live state.

This file is deliberately only a quick code index. It must not carry a second
liveness verdict or estate census.

## Direct dialogue

```text
dgc agent talk <name> <message>
  -> dharma_swarm/dgc_cli.py
  -> dharma_swarm/terminal_commands/agents.py
  -> scripts/holon_talk.py
  -> dharma_swarm/holon_bridge.py:load_holon
  -> canonical runtime provider
  -> ~/.dharma/agents/<name>/talk_receipts.jsonl
```

The installed `dgc` command currently fails outside the checkout because
`terminal_commands/agents.py` imports `scripts.holon_talk`
(`dharma_swarm/terminal_commands/agents.py:101-115`), while `pyproject.toml`
excludes `scripts*` from the package (`pyproject.toml:62-64`). The exact
packaging probe is recorded in the full estate map.

## Proposal wake cycle

```text
dgc agent run <name> --cycles N
  -> dharma_swarm/terminal_commands/agents.py
  -> scripts/holon_run.py
  -> dharma_swarm/holon_bridge.py:load_holon
  -> dharma_swarm/holon_runtime.py:run_holon_loop
  -> kill -> budget -> optional reversibility -> injected work -> compass -> persist
  -> ~/.dharma/agents/<name>/holon_events.jsonl
```

The current CLI runner asks the model to propose a next action
(`scripts/holon_run.py:32-62`). It calls the loop with `cap_usd=0.0` and without
`planned_action` or `spend_fn` (`scripts/holon_run.py:66-87`), and it does not
acquire an execution lease or call an effect executor. Treat it as a proposal
cycle, not autonomous action.

## Intended no-tools API dialogue

```text
POST /holon/{name}/chat
  -> api/main.py
  -> api/routers/holon.py
  -> dharma_swarm/holon_bridge.py
  -> provider.stream(LLMRequest)
  -> dharma_swarm/conversation_log.py
```

The route is intended to be own-model, no-tools dialogue, but it is not yet
provider-boundary-safe. It calls the general resolver
(`api/routers/holon.py:43-68`) even though the bridge provides a resolver that
rejects unsafe agentic dialogue providers
(`dharma_swarm/holon_bridge.py:198-241`). It still needs to compose that safe
resolver, bounded LivingDock context (`dharma_swarm/holon_bridge.py:277-305`),
and a normalized holon receipt path.

Do not confuse it with `POST /agents/{agent_id}/chat`. That lookalike route
builds a persona prompt and calls the generic `_agentic_stream`
(`api/routers/agents.py:423-515`); it is not sovereign-holon dialogue.

## File owners

| Change | Edit here first |
| --- | --- |
| Identity/prompt/model loading | `dharma_swarm/holon_bridge.py` |
| Direct cycle ordering/result semantics | `dharma_swarm/holon_runtime.py` |
| Cycle persistence | `dharma_swarm/holon_persistence.py` |
| Kill/cost/compass primitives | `dharma_swarm/holon_killswitch.py`, `holon_budget_guard.py`, `holon_compass.py` |
| Authority, reversibility, leases | `dharma_swarm/operator_core/` |
| Persistent service/supervision | `dharma_swarm/operator_core/living_agent_kernel*.py` |
| Model routing | `dharma_swarm/runtime_provider.py` and its provider stack |
| A2A transport and task receipts | `dharma_swarm/a2a/` |
| CLI behavior | `dharma_swarm/terminal_commands/agents.py` and package-owned talk/run implementation |
| HTTP dialogue | `api/routers/holon.py` |
| Runtime evidence | inspect `~/.dharma`; do not make it the source home |
| Parallel Hermes compatibility | versioned Dharma adapter first; treat `~/.hermes` as external |

## Lifecycle distinction

`dgc agent wake` directly calls `autonomous_agent.cli_wake`
(`dharma_swarm/terminal_commands/agents.py:42-45`), which constructs one
`AutonomousAgent` (`dharma_swarm/autonomous_agent.py:1483-1509`).
`PersistentAgent`, `AgentRunner`/`SwarmManager`, the direct holon path, and the
Living Agent Kernel are adjacent lifecycle bodies; they are not traversed by
that wake command and should not be silently called one another.

`dharma_swarm/holon_system/` is a thin navigation/facade package, not a fourth
runtime; reproduce the inventory with
`find dharma_swarm/holon_system -type f -name '*.py' -print0 | xargs -0 wc -l`.
Sarathi's source projections currently report `wake_loop_active=false` and
`alive_claim=false` (`dharma_swarm/holon_system/sarathi/gateway.py:17-23`).
