# Hermes Task — Full Persistent Agent Index

Date: 2026-05-28
Requester: John Shrader
Repo: AmitabhainArunachala/dharma_swarm
Priority: P0

## Mission

Hermes, perform a full index of every persistent, semi-persistent, scaffolded, dormant, implied, or operational agent surface in Dharma Swarm.

The goal is not a shallow file list. The goal is to make the swarm legible enough that agents can start firing together across providers through a single coordination fabric.

## Core Questions

1. What persistent agents currently exist in the repo?
2. Which agents are real runtime entities, and which are only prompts/docs/scaffolds?
3. Which agents have identity, filesystem, memory, role, skills, routing metadata, or lifecycle state?
4. Which providers are each agent meant to run on: OpenAI/Codex, Claude/Claude Code, Grok, Gemini, local model, shell process, browser agent, GitHub agent, or internal Python worker?
5. Which agents are currently connected to orchestrator, A2A, message bus, registry, dashboard, CLI, CI, or runtime state?
6. Which agents are duplicated, stale, renamed, dead, or conflicting?
7. What minimal control-plane schema would allow every persistent agent to be discoverable and callable?

## Required Search Scope

Index at minimum:

- `.agents/`
- `agents/`
- `dharma_swarm/agents/`
- `dharma_swarm/a2a/`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/message_bus.py`
- `dharma_swarm/runtime_state.py`
- `docs/`
- `specs/`
- `promotion_worktrees/`
- `AGENTS.md`
- `WARP.md`
- CI/workflow files
- dashboard/API surfaces that mention agents
- any registry, identity, memory, handoff, evidence, signal, VSM, TRISHULA, Kaizen, Venture Cell, or Control Plane files

Use ripgrep or equivalent searches for:

- `agent`
- `AgentIdentity`
- `AgentCard`
- `Hermes`
- `persistent`
- `registry`
- `orchestrator`
- `router`
- `handoff`
- `inbox`
- `outbox`
- `memory`
- `skill`
- `capability`
- `provider`
- `codex`
- `claude`
- `grok`
- `gemini`
- `openai`
- `a2a`
- `mcp`
- `trishula`
- `vsm`
- `kaizen`
- `controlplane`
- `venture cell`

## Output Required

Create a report at:

`docs/reports/hermes_persistent_agent_index_2026-05-28.md`

The report must include:

### 1. Executive Map

A concise map of the agent ecosystem as it actually exists now.

### 2. Persistent Agent Table

For every discovered agent or agent-like surface, include:

| Agent / Surface | Path(s) | Runtime Status | Provider Target | Role | Skills | Memory / FS | Routing Hook | Evidence Hook | A2A Readiness | Problems |

Runtime status should use:

- `live`
- `callable-but-partial`
- `scaffolded`
- `prompt-only`
- `dormant`
- `stale/unknown`

### 3. Provider Matrix

Map which agents can plausibly run under:

- OpenAI / Codex
- Claude / Claude Code
- Grok
- Gemini
- local model
- GitHub action
- shell / Python worker

### 4. Activation Graph

Show how work should flow if John asks:

> “Run Dharma Swarm against this repo goal.”

Include:

- entrypoint
- router
- registry
- planner
- worker agents
- reviewer agents
- synthesis agent
- evidence log
- dashboard/status surface

### 5. Gaps Blocking Agents From Firing Together

Be blunt. Identify the top 10 blockers preventing persistent agents from operating as one cross-provider swarm.

Examples may include:

- no canonical agent registry
- duplicated role names
- no provider adapter abstraction
- no universal task envelope
- no state lifecycle
- no evidence receipt standard
- no cross-provider handoff protocol
- no routing fitness score
- no dashboard truth surface
- no background runner
- A2A scaffold not spec-correct enough

### 6. Proposed Canonical Schema

Draft the smallest useful schema for `PersistentAgentDescriptor`, including:

```yaml
id:
name:
role:
provider_targets:
model_preferences:
skills:
input_modes:
output_modes:
permissions:
working_directory:
memory_paths:
inbox_path:
outbox_path:
evidence_path:
a2a_card_path:
mcp_tools:
routing_tags:
latency_class:
cost_class:
trust_level:
lifecycle_state:
last_seen:
owner:
```

### 7. Immediate Build Plan

Give John a concrete 3-PR path:

1. PR 1: persistent agent inventory + descriptor schema
2. PR 2: registry loader + router integration
3. PR 3: cross-provider activation loop with evidence receipts

Each PR should list files to create/edit, tests to add, and success criteria.

## Constraints

- Do not invent agents that are not grounded in repo files.
- Clearly mark inferred agents vs explicit agents.
- Prefer grep-backed evidence with file paths and line numbers.
- Avoid metaphysical language unless it maps to concrete repo surfaces.
- Preserve Dharma Swarm vision, but translate it into operational architecture.
- Treat A2A 1.0 compatibility as a near-term design constraint.

## Desired End State

After this report, John should be able to say:

> “Here are all my persistent agents. Here is what each does. Here is which provider can run it. Here is how Hermes routes between them. Here is what is missing before they all fire together.”

That is the deliverable.
