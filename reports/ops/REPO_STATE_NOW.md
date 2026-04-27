# Repo State Now

Generated: 2026-04-27

Reference branch: `origin/main`
Reference HEAD: `834b8c20694b05bcbc95f3d781e5cce45c4fea0e`

Read this after `docs/governance/CANONICAL_DOC_STACK.md` and before
older maps such as `CYBERNETIC_LOOP_MAP.md`,
`MODEL_ROUTING_MAP.md`, or archived design docs.

## Current Truth

- PR #28 is merged and establishes a test-proven runtime spine for the
  core task lifecycle.
- PR #35 is merged and unblocked CI for PR #28.
- PR #41 is merged and establishes the Tier-1 governance/doc stack.
- The old Loop 1 `huggingface_hub` blocker (`MM-01`) is resolved and
  must not be treated as the current runtime blocker.
- `RuntimeStateStore` is the canonical structured runtime store.
- `SessionLedger` remains the append-only JSONL session trace and also
  indexes events into `RuntimeStateStore.session_events`.
- The dashboard/API layer is real, but it exposes projected or domain
  views rather than raw runtime tables.

## Runtime Spine

The PR #28 runtime-spine proof covers the orchestrator-centric path:

`TaskBoard` -> `Orchestrator` -> `SessionLedger` +
`RuntimeStateStore`.

The proven writes are:

- `task_claims`
- `delegation_runs`
- `artifact_records`
- `session_events`
- session stubs through event indexing

Do not claim that the live daemon, full `AgentRunner` provider/tool
path, or downstream adaptive loops are closed unless a current test or
runtime run proves that claim.

## Dashboard / API

Current dashboard truth is partial:

- `api/main.py` is the live dashboard service.
- `/api/telemetry/*` exposes projected telemetry.
- `task_claims` and `delegation_runs` are visible only indirectly
  through telemetry projection.
- `artifact_records` are not projected to telemetry or dashboard
  lineage today.
- Raw runtime tables do not yet have first-class read-only dashboard
  routes.

Stale or not-yet-promotable dashboard surfaces include:

- `/api/fleet/*`
- `/api/pool/*`
- `/api/agents/{id}/config`
- `/api/agents/{id}/dispatch`
- `/api/agents/observatory`

## Memory / Substrates

Use existing substrates:

- Runtime facts: `RuntimeStateStore.memory_facts`
- Runtime fact relationships: `RuntimeStateStore.memory_edges`
- Typed ontology truth: `OntologyHub` / `ontology_runtime.py`
- Corpus/rule truth: `DharmaCorpus`
- Coordination marks: `StigmergyStore`
- Routing outcomes: `RoutingMemoryStore`

Do not add new stores, ledgers, registries, JSONL streams, or SQLite
files before a substrate registry/policy exists.

## Agent Identity / Config

Current code truth is `AgentConfig`, `AgentState`, `AgentRole`, and
`ProviderType` in `dharma_swarm/models.py`.

`AutonomousAgent.AgentIdentity` and related identity unification work
remain separate or aspirational surfaces. Do not document a unified
`AgentIdentity` as implemented until code and tests prove that
migration.

## Model Routing

`ModelRouter`, `ProviderPolicyRouter`, `RoutingMemoryStore`, and
provider-lane circuit breakers exist and are coherent inside the
routed `AgentRunner` path.

Open routing gaps:

- Persistent routing memory is not enabled by default in
  `create_default_router()`.
- Dashboard chat, autonomous agents, pulse/cron, TUI adapters,
  evolution, and runtime-provider helpers bypass the shared routed
  policy path.
- Root `MODEL_ROUTING_MAP.md` is a drift register; the canonical
  routing reference is `docs/architecture/MODEL_ROUTING_CANON.md`.

## Docs

Canonical read order:

1. `docs/governance/CANONICAL_DOC_STACK.md`
2. This file
3. Domain-specific canonical docs named by the stack
4. Historical maps only when investigating drift or design history

Historical or drift-register docs must not override current reports or
tests.
