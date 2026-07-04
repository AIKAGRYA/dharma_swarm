# A2A Always-On Spine Master Plan

Date: 2026-07-01
Status: implementation spine, not a claim of full production readiness

This document pins the target shape for a working, speaking, always-on A2A system. It folds the current NATS lane, the Claude reconciliation handoff, the LangGraph parity lane, MCP/tool interop, and the agentic design-pattern atlas into one spine.

## Plain Model

Think of the system as a body:

- A2A is the nervous system: it carries tasks, status, artifacts, and replies between agents.
- NATS JetStream is the nerve fiber: it gives durable delivery, ack/nack, redelivery, and replayable evidence.
- Runtime receipts and idempotency records are the immune system: they stop duplicate side effects and separate truth from vibes.
- MCP is the hand/tool layer: agents use tools through scoped adapters, not by reaching into every subsystem directly.
- LangGraph is the long-running workflow brainstem: use it for durable multi-step orchestration after the transport truth is stable.
- Voice is an I/O organ: speech goes to operator intent, intent becomes an A2A task, replies become speech again.

The mistake to avoid: do not create a new coordination substrate every time the system feels incomplete. First route through the existing A2A/runtime_state owners; only add a new owner when no current owner can satisfy the contract.

## Current Truth

- Main closed `runtime-truth-nats-2026-06` as `VERIFIED_SLICE`, not `SUBSTRATE_TRUSTED`.
- PR #739 produced useful NATS hardening and live local evidence, but it originated from `agent/magpie-seed`; this branch ports the useful slice onto current `origin/main`.
- The live operator contact path is still `scripts/runtime/a2a_send.py`; it is compatibility contact, not the canonical `A2ANatsTransport.publish_task` path.
- `A2ANatsTransport` is the correct canonical transport owner for task envelopes, receipt/idempotency, redelivery, MaxDeliver, and DLQ proof.
- AGNI has agent-specific bridges for Hermes and Codex, but no proven fleet-wide mirror between local `DHARMA_FLEET` and AGNI `DHARMA_A2A`.
- `NodeGateway` and card/registry surfaces exist, but gateway initialization and Agent Card signature verification are not production-enforced.
- The Claude `coordination_substrate/**` code is superseded. Keep its anti-sprawl doctrine and `pramana_probe`; do not wire the package.

## Target Spine

```text
Voice / CLI / Dashboard
  -> OperatorIntent
  -> Planner / Router / Human approval policy
  -> A2A Task envelope
  -> A2ANatsTransport on JetStream
  -> Agent runtime / handler
  -> MCP or local tool adapters
  -> RuntimeReceipt + IdempotencyRecord + trace
  -> Pramana / Final Boss / eval gates
  -> A2A artifact/reply
  -> Voice / CLI / Dashboard response
```

The transport contract is more important than the UI. A beautiful voice loop on a weak task path gives a talking puppet. A receipted A2A path with a thin voice adapter gives a real always-on agent system.

## Pattern Integration Matrix

| Pattern | System owner | Integration rule |
|---|---|---|
| Prompt chaining | Planner/runtime handler | Chain only inside a task context with trace and receipt boundaries. |
| Routing | A2A router + Agent Card skills | Route by capability, security, broker reachability, and current load. |
| Parallelization | A2A fanout + LangGraph later | Parallel work must retain parent run id and merge receipts deterministically. |
| Reflection | Pramana/final boss/eval lanes | Reflection writes verdicts and revisions, not silent mutations. |
| Tool use | MCP/local tool adapters | Tools are scoped, audited, and called behind policy. |
| Planning | OperatorIntent -> planner | Plans are task artifacts; execution remains receipted. |
| Multi-agent | A2A tasks | Agents communicate through task envelopes, not hidden shared memory. |
| Memory management | RuntimeStateStore + memory kernel | Memory writes need provenance, purpose, and recall tests. |
| Learning/adaptation | Governance/evolution lanes | Adaptation requires eval delta and rollback path. |
| MCP | Tool plane | MCP is for external capabilities, not agent presence or task truth. |
| Goal monitoring | Runtime receipts + status projections | Monitor by receipts, ack tier, and stale-heartbeat gates. |
| Exception recovery | NATS redelivery + DLQ + repair tasks | Failures become retry, DLQ, or human escalation, never swallowed exceptions. |
| Human in the loop | Approval policy | Approval is a task state and receipt, not a chat aside. |
| RAG | Memory/retrieval adapters | Retrieval is a tool with source receipts, not untracked context stuffing. |
| A2A | Canonical transport | A2A is the inter-agent contract. NATS is the internal durable binding. |
| Resource optimization | Broker/load/router metrics | Route by cost, latency, model availability, and reliability class. |
| Reasoning techniques | Planner/evaluator | Reasoning style is metadata and testable output quality, not a hidden prompt boast. |
| Guardrails/safety | Policy + auth + signatures | Enforce Agent Card verification, scoped keys, redaction, and no secret commits. |
| Evaluation/monitoring | Pramana + final boss + CI | Every readiness claim needs executable evidence. |
| Prioritization | Active track portfolio | Work enters through owned surfaces and WIP limits. |
| Exploration/discovery | Scout agents | Discovery produces reports and candidate tasks; it does not wire production. |

## Merge Order

1. Land the main-based NATS hardening slice:
   - `A2ANatsTransport` envelope, identity, idempotency, ack/nack, retry, MaxDeliver, DLQ, and source-freshness evidence gates.
   - Keep main's `runtime-truth-nats-2026-06` closeout truth as `VERIFIED_SLICE`; do not reopen it by accident.
2. Land Claude keepers:
   - `docs/architecture/A2A_COORDINATION_SUBSTRATE.md`
   - `docs/ops/A2A_LOCAL_RECONCILIATION_HANDOFF.md`
   - `scripts/governance/pramana_probe.py`
   - `tests/test_pramana_probe.py`
3. Make one canonical task path:
   - Either route production sends through `A2ANatsTransport.publish_task`, or explicitly keep `a2a_send.py` as compatibility contact that cannot satisfy production-readiness gates.
4. Add dual-broker truth:
   - Local `DHARMA_FLEET` survey plus AGNI `DHARMA_A2A` survey.
   - Mirror only after the survey proves what is absent; use allowlisted subjects and loop-prevention headers.
5. Add always-on supervisor:
   - launchd/systemd process supervisor
   - heartbeat, stale detection, restart policy, DLQ drain, and operator-visible status
   - no autonomous destructive action without approval policy
6. Add voice:
   - speech-to-text -> OperatorIntent
   - A2A task -> agent reply/artifact
   - text-to-speech
   - voice never bypasses task receipts
7. Add LangGraph parity:
   - use for long-running, human-interruptible workflows after A2A transport truth is stable
   - map LangGraph thread/checkpoint semantics to local `ExecutionIdentity` and runtime receipts

## Hard Gaps

- No proven local-fleet to AGNI mirror.
- No enforced Agent Card signature verification.
- `NodeGateway.init_gateway()` is not proven live in the API lifespan.
- `NodeRegistry` has stored `api_key` material in cleartext in local state; never commit or print it.
- `A2ANatsTransport` still needs a production caller before the system can claim canonical always-on A2A.
- Voice is not implemented as a receipted adapter yet.

## Definition Of Done

A future PR may claim "always-on speaking A2A" only when all of this is true:

- One command starts the broker, supervisor, gateway, and at least one agent.
- One spoken or CLI operator intent becomes a canonical A2A task.
- The task crosses NATS through `A2ANatsTransport` or an explicitly equivalent transport.
- The handler emits a receipt and an artifact/reply.
- Duplicate sends do not duplicate side effects.
- Handler failure redelivers or DLQs with evidence.
- Local and AGNI broker status are reported separately.
- Agent Card signatures or an equivalent trust gate are enforced.
- A final boss/eval gate can replay the evidence without depending on prose.

## Upstream References Checked

- A2A Protocol specification: https://a2a-protocol.org/latest/specification/
- MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- NATS JetStream concepts: https://docs.nats.io/nats-concepts/jetstream

