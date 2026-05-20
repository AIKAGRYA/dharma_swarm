# Pattern Catalog

## Keypair identity attached to participant state

Source systems: SAB need surfaced by dharma_swarm audit; partial analogs in signed bridge/witness code in dharmic-agora.

Solves: identity continuity across restarts, host moves, and model swaps. Makes "the agent acted" auditable.

Port effort: medium.

Conflict: none. It should formalize current name/profile/registry identity rather than replace it.

## Memory as append-only log plus retrieval

Source systems: Letta, Hermes Agent, ElizaOS, dharma_swarm AgentMemoryBank, witness logs.

Solves: an external auditor can inspect what the agent could have known, while the agent gets useful recall.

Port effort: medium.

Conflict: dharma_swarm already has many stores. The risk is adding another store instead of indexing current memory, stigmergy, witness, and registry traces.

## Thread/checkpoint participant state

Source systems: LangGraph, AutoGen.

Solves: durable execution and resumability. Gives a precise object to export before/after each wake cycle.

Port effort: medium.

Conflict: current state is spread across directories. Needs a manifest and state-index layer.

## Capability acquisition through signed skill bundles

Source systems: Hermes Agent, OpenClaw/ClawHub, ElizaOS plugins.

Solves: agents can grow capability without arbitrary unmanaged code execution.

Port effort: high.

Conflict: must not bypass telos gates, sandbox policy, or operator attestation.

## Cron/wake-cycle autonomy

Source systems: Hermes Agent, AI Garden GitHub Action, OpenClaw cron/webhooks, Cursor automations, dharma_swarm PersistentAgent.

Solves: operator backs compute and schedule; agent acts on recurring obligations.

Port effort: low for PersistentAgent, medium for other species.

Conflict: none, but wake authority must be explicit in participant manifests.

## Operator attestation as explicit signed claim

Source systems: dharma_swarm witness/audit needs; OpenAI/Codex approval modes as product pattern; dharmic-agora witness-event chain as local pattern.

Solves: separates "operator approved capability envelope" from "operator chose each action." This is central to operator-distance.

Port effort: medium.

Conflict: requires discipline in UI/CLI workflows so approvals are logged, not implied.

## Isolated workspace per participant

Source systems: OpenClaw, Hermes Agent terminal backends, Devin/Codex cloud sandboxes, Manus sandbox.

Solves: bounded side effects and simpler audit. Each participant has filesystem, tools, logs, and policy envelope.

Port effort: medium.

Conflict: dharma_swarm currently uses shared `~/.dharma` paths heavily. Needs per-participant roots or an index over shared roots.

## Shared world-state repository

Source systems: AI Garden.

Solves: simple durable memory and public audit through commits. Good for early external demos.

Port effort: low to medium.

Conflict: not every agent action belongs in git; use for social/world contributions, not secrets or high-volume logs.

## Reviewable background work artifacts

Source systems: Cursor, Devin, Codex, AI Garden.

Solves: lets an operator audit outputs after the fact without driving the action.

Port effort: low.

Conflict: none. dharma_swarm already emits reports/logs; the work is standardizing them per participant.

## Plugin/provider adapter for SAB

Source systems: ElizaOS plugins, Letta tools, Hermes skills, OpenClaw skills.

Solves: lets external systems join SAB through their native extension mechanism.

Port effort: medium.

Conflict: SAB should keep a narrow adapter contract. Avoid redesigning SAB around any one framework.

## Keystone pattern

The keystone is keypair identity bound to an append-only event/memory log. Without it, memory and autonomy remain local conveniences. With it, operator-distance becomes auditable.
