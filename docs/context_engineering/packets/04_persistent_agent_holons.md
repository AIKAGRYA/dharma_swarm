# Packet 04: Persistent Agent Holons And Tmux Substrate

Packet ID: `ctx.persistent-agent-holons`

Use when touching persistent agents, sovereign holons, wake loops, tmux lanes,
agent hierarchy, long-running service health, or agent identity files.

Do not use for A2A semantic proof. Use `ctx.runtime-spine-a2a-nats` for
transport and task receipts.

## Authority Model

- Identity owners: `/Users/dhyana/.dharma/agents/**`, agent registry commands,
  holon identity files
- Runtime owners: holon services, wake loops, health rows, receipts
- Substrate owner: `docs/ops/TMUX_AGENT_SUBSTRATE.md`
- Evidence owners: `reports/agentops/**`, tmux status, process probes, last
  receipts

Core invariant: tmux is inspectable execution evidence, not identity authority
or completion proof.

## Mission

Keep persistent agents alive, inspectable, and accountable without confusing
terminal liveness with useful work. Agents need an identity, a task lease or
mission, a wake mechanism, a health signal, and receipts outside the pane.

## Vision Anchors

- `foundations/THE_ORGANISM.md`: holons as living organs of the organism.
- `docs/vision_maps/NORTH_STAR.md`: why persistent agents must serve coherent
  action.
- `docs/architecture/AGENT_HIERARCHY_MATURITY_MAP.md`: maturity target for the
  agent hierarchy.
- `docs/sovereign_holons/CODEX_COMPOSER_WAKE_LOOP.md`: long-running composer
  wake-loop vision.
- `reports/swarm_genome/2026-06-11/SYNTHESIS.md`: holon organ in the organism
  synthesis.

## Current Reality Anchors

- Run `make onboard` for current holon and active-track state.
- `docs/governance/ACTIVE_TRACK.yaml`: composer holon and admission lanes.
- `reports/agentops/PERSISTENT_AGENT_HIERARCHY_20260630.md`: current hierarchy.
- `reports/agentops/PERSISTENT_AGENT_CENSUS_20260630.md`: current census.
- `tmux ls`: inspectable terminal substrate liveness only.

## Dense Docs

- `docs/ops/TMUX_AGENT_SUBSTRATE.md`: tmux substrate contract and limits.
- `reports/a2a/codex_holon_always_live_upgrade.md`: always-live holon upgrade
  context.
- `reports/agentops/**`: agent receipts, census, hierarchy, and review evidence.
- `docs/agents/**/CONTEXT_ENGINEERING.md`: named seat context when the task is
  seat-specific.

## Work-Lane Anchors

- `composer-holon-spine-longrun-2026-06`: composer wake loop and receipts.
- `agent-admission-semantic-commons-2026-06`: identity, naming, and admission.
- Persistent-agent promotion requires receipts outside the pane, not a running
  process alone.

## Evidence Boundary

- Canonical owner: identity files, agent registry, health rows, holon code, and
  receipts.
- Projection: tmux status, process lists, dashboards, and agentops summaries.
- Transient recall: prior claims of "always live" only justify checking current
  identity and health.
- Forbidden-to-cite: pane text as completion proof, process existence as useful
  work, stale identity material, or secrets from agent homes.

## Future-Agent Review Hooks

- Before acting, state whether you are proving identity, liveness, health,
  output, or semantic completion.
- Before claiming complete, cite the receipt outside the pane that proves useful
  work.
- If evolving this packet, request a five-lane multi-agent/model review when
  practical; otherwise record the skip or failure reason in a handoff receipt.

## First Reads

L0 Safety:

- `make onboard`
- `docs/ops/TMUX_AGENT_SUBSTRATE.md`

L1 Route:

- `reports/agentops/PERSISTENT_AGENT_HIERARCHY_20260630.md`
- `reports/agentops/PERSISTENT_AGENT_CENSUS_20260630.md`

L2 Owners:

- `dharma_swarm/holon_canonical_state.py`
- `dharma_swarm/holon_l4_service.py`
- `dharma_swarm/holon_truth_projection.py`
- `scripts/runtime/codex_composer_wake_loop.py`
- `dharma_swarm/terminal_commands/`

L3 Evidence:

- `/Users/dhyana/.dharma/agents/<agent>/last_receipt.json`
- `/Users/dhyana/.dharma/agents/<agent>/identity.json`
- `/Users/dhyana/.dharma/agents/<agent>/living_agent.json`
- `reports/agentops/semantic_receipts/**`

L4 Search:

- `rg -n "holon_health|living_agent|identity.json|wake_loop|tmux" dharma_swarm scripts tests docs reports`

L5 Seat:

- Load `codex_composer`, `opus_composer`, `fable_composer`, `sarathi`, or
  `qwen_code` only after confirming the identity file and current health.

## Live Probes

```bash
make onboard
make tmux-status
dgc agent list
tmux ls
```

When changing holon code:

```bash
pytest tests/test_holon_canonical_state.py tests/test_holon_truth_projection.py
```

Use process probes only as runtime evidence:

```bash
pgrep -fl "holon|codex_composer|conductor"
```

## Retrieval Contract

- Query: "persistent agent hierarchy codex composer health"
  Source family: `reports/agentops/**`, `~/.dharma/agents/**`.
- Query: "tmux agent substrate authority not completion proof"
  Source family: `docs/ops/TMUX_AGENT_SUBSTRATE.md`.
- Query: "holon canonical state truth projection"
  Source family: holon modules and tests.

## Operating Loop

1. Identify the agent level: conductor, sovereign holon, living agent,
   workcell/passport, preset, or local pool.
2. Confirm identity source.
3. Confirm runtime health source.
4. Confirm work authority: task, lease, mission, or operator instruction.
5. Inspect tmux only after identity and authority are known.
6. Verify code changes with holon tests or receipt checks.
7. Leave a handoff with identity, health, lane, and proof separated.

## Guardrails

- Do not paste secrets into tmux panes.
- Do not kill all tmux sessions as cleanup.
- Do not run modifying agents on one dirty worktree without a lease or separate
  worktree.
- Do not call an agent complete because a pane exists.
- Do not claim sovereign service health from A2A bridge health.
- Do not mutate `/Users/dhyana/.dharma/agents` identity files without a clear
  owner and receipt.

## Context Budget

- Tiny: `make onboard`, tmux substrate, this packet.
- Standard: tiny plus persistent hierarchy report, specific agent identity,
  current health row, last receipt.
- Deep: standard plus holon modules, wake loop code, process/tmux captures, and
  relevant tests.

## Done Criteria

Complete means:

- identity, runtime health, work authority, and proof are separated;
- no tmux-only completion claim is made;
- code changes are covered by tests or explicit verification;
- handoff identifies whether the lane is safe to keep running.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.persistent-agent-holons.
Separate identity, health, work authority, and completion proof. Tmux is an
inspectable substrate only. Start with make onboard and TMUX_AGENT_SUBSTRATE.
Confirm the specific agent's identity files, health row, and last receipt before
acting. Verify narrowly and leave a handoff that does not collapse A2A bridge
liveness, tmux liveness, and sovereign holon service health.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.persistent-agent-holons",
  "agent_id": "",
  "agent_level": "",
  "identity_sources": [],
  "health_sources": [],
  "tmux_sessions_seen": [],
  "work_authority": "",
  "receipts": [],
  "commands_run": [],
  "safe_to_keep_running": true,
  "claims_with_citations": [],
  "claims_not_made": [],
  "next_packet": "",
  "residual_risk": "",
  "next_action": "",
  "next_step": ""
}
```
