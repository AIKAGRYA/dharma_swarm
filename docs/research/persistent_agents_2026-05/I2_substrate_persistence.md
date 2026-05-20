# I2 - Substrate-Level Persistence

## What already works

dharma_swarm has more persistence than most surveyed systems, but much of it is system-level persistence rather than agent-level self-memory.

Agent-level persistence:

- `dharma_swarm/agent_memory.py:69`, `:325`, `:335` - `AgentMemoryBank` with per-agent save/load.
- `dharma_swarm/agent_memory_manager.py` - SQLite-backed memory manager with agent-scoped records.
- `dharma_swarm/agent_registry.py:146`, `:181`, `:189-191` - on-disk identity, task log, and fitness history.
- `dharma_swarm/profiles.py` - persistent adaptive profiles.
- `dharma_swarm/persistent_agent.py:459` - per-agent witness JSONL writes.

System-level persistence:

- Stigmergy store: shared marks/signals and substrate memory.
- Algedonic/governance traces: system pain/reward and policy feedback.
- Witness logs: audit records and findings.
- Evolution archive: proposals, experiments, traces, and possible git commits.
- Ontology and vectors: shared knowledge retrieval substrate.
- World model snapshots: system-level state of the world.
- Task boards and ledgers: durable operational state.

## How an agent sees its own past tomorrow

The current mechanism is mixed:

1. `PersistentAgent.wake` loads its `AgentMemoryBank` before acting.
2. It reads stigmergy/message-bus signals and can generate a self-task from hot paths or salient marks.
3. The underlying autonomous agent records memory after a run.
4. The witness/logging layer writes JSONL traces.
5. Registry/task logs preserve task history and fitness for Ginko-style agents.

This is enough for basic continuity. It is not yet enough for portable identity because the same "agent" is reconstructed from name, path, config, profile, registry, and substrate attribution rather than from a signed participant identity.

## Identity layer status

No keypair-per-agent identity layer was found in the surveyed dharma_swarm code. Identity is currently emergent from:

- agent name and role;
- `AgentConfig` ID/name/model/tools/autonomy;
- registry `identity.json`;
- profile JSON;
- memory directory name;
- witness/log attribution;
- task-board assignment.

That is acceptable for local operations, but it is weak for SAB. SAB needs a participant identity that can survive host migration and model swap, and that can sign contributions or at least sign attestations through a controlled key.

## Where dharma_swarm already exceeds external systems

dharma_swarm is ahead in breadth of substrate state:

- Stigmergy and witness logs give shared social traces, not just private chat memory.
- Evolution archive and DarwinEngine capture self-modification attempts.
- Registry, fitness history, task logs, profiles, and run reports give a richer longitudinal picture than many agent products expose.
- PersistentAgent already has cron/wake/self-task behavior close to Hermes Agent and beyond most framework examples.

This is the fundable strength: dharma_swarm already has a thick substrate that an auditor can inspect.

## Where dharma_swarm lags

dharma_swarm lags in participant clarity:

- No cryptographic identity per agent.
- No single participant manifest binding key, role, memory stores, tools, policy, and wake schedule.
- No portable state export equivalent to a LangGraph thread/checkpoint or AutoGen state object.
- Capability acquisition is not yet a signed, sandboxed, auditable skill process.
- The same word "agent" covers durable participants, daemons, registries, scripts, and examples.

## Minimum persistence work before SAB Phase 0

1. Add keypair-per-participant identity.
2. Add a participant manifest: key, role, memory roots, tools, policy envelope, wake schedule, and signing rules.
3. Bind `PersistentAgent` memory/witness writes to that identity.
4. Add signed contribution and signed operator-attestation records.
5. Add one agent-facing recall API over `AgentMemoryBank`, SQLite memory, stigmergy, witness logs, and registry history.

The substrate is not empty. It is too plural. The next step is consolidation around participant identity, not another persistence store.
