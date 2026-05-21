# Agent Authority Ladder Scaffold

Registration is identity. Authority is separate.

The registration desk creates a safe external-worker identity with evidence-only authority. An authority passport is the next layer: a reviewable, expiring statement of which lanes an agent may operate in.

## Current Ranks

- `visitor`: may show up and receive a sandbox.
- `registered_external`: has canonical registration, A2A card, telemetry identity, logs, and receipts.
- `operator_candidate`: may operate in named low-risk lanes, still evidence-only for source/runtime power.
- `scoped_contributor`: may receive explicit AgentOps packets with narrow file scopes.
- `trusted_operator`: future rank; not granted by this scaffold.
- `steward`: future rank; can recommend policy changes, never self-promote.

## Hermes M5 Scaffold

Hermes should start as:

- rank: `operator_candidate`
- lane: `morning_ops_operator`
- status: `scaffolded_not_promoted`

Allowed by the lane:

- read ops telemetry and own receipts
- produce daily/overnight operator briefings
- append action logs and wake receipts
- emit KaizenOps events
- emit Stigmergy marks
- propose AgentOps work packets

Still gated:

- source writes
- AgentOps execution
- cron changes
- external messaging
- secret access
- model/provider changes

Still forbidden:

- PR approval
- merge/push
- Meta-Dharma, telos, dharma_kernel, DGM-protected mutation
- context-bundle authoring
- self-promotion

## Command

```bash
python3 scripts/scaffold_agent_authority_passport.py \
  --agent-uid hermes_m5_bootstrap \
  --rank operator_candidate \
  --lane morning_ops_operator
```

This writes:

- `~/.dharma/external_agents/{agent_uid}/authority/passport.json`
- `~/.dharma/external_agents/{agent_uid}/authority/reviews.jsonl`

It does not dispatch work, run AgentOps, alter cron, grant source-write authority, or promote the agent automatically.
