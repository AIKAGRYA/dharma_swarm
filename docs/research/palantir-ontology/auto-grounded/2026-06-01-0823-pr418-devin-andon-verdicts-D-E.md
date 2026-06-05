# Auto-Grounding: PR #418 — Devin Andon Verdicts (Slices D + E)

**Artifact:** PR #418 — `andon(verdict): devin slices D + E — workflow state partially_confirmed, A2A collision overstated`
**Author:** app/devin-ai-integration
**Branch:** `devin/1780298217-andon-verdict-D-E` (based on `perplexity-grounding/1780289724-vocabulary-census`)
**Link:** https://github.com/AmitabhainArunachala/dharma_swarm/pull/418
**Grounded by:** perplexity-computer (auto-grounding, scheduled cron 7fb7e39e)
**Date:** 2026-06-01T08:23Z
**Standing posture:** Adversarial. Be the adult. PhD-grade external grounding against 5th-grade reality. Co-equal contributor — claude synthesizes, John merges, perplexity grounds.

---

## What it claims

PR #418 delivers Devin's verdicts on two unclaimed slices from the RED-severity andon I pulled at 2026-06-01T06:28Z. It adds two verdict files under `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/` and refreshes DocOps counts (markdown_files 751→773).

**Slice D (workflow state ownership) — verdict `partially_confirmed`.** Devin enumerates 13 state surfaces (`RuntimeStateStore`, `SwarmManager`, `LoopSupervisor`, `MissionState`, `IterationDepth`, `DurableState`, `CanonicalWorkflowState`, `WaitState`, `AMIROSRegistry`, `JobState`, etc.), declares `runtime_state.py:RuntimeStateStore` the "canonical control plane," confirms `CanonicalWorkflowState` (`operator_core/contracts.py:217`) exists as a typed contract with **no runtime producer**, and frames the multi-owner pattern as "**layered, not competing — cosmetic fragmentation, not operational collision**." The actionable gap surfaced: "no first-class `workflowRun` that traces from dispatch through execution to outcome."

**Slice E (A2A external/internal collision) — verdict `overstated`.** Devin enumerates 4 `A2ATask` instantiation sites (`a2a_server.py:257`, `a2a_client.py:348`, `a2a_bridge.py:120`, `node_gateway.py:210`), describes a three-layer architecture (server/client/gateway/bridge), concludes the dual use is "**intentional and well-bounded**" because of `X-A2A-Key` auth at the gateway, `metadata["source"]` source tagging, separate task stores, and `_MAX_DELEGATION_DEPTH = 10` cycle detection. Concludes the design "**conforms to A2A 1.0 spec**" and that `A2ATask.from_agent` being a plain string is "cosmetic, not dangerous."

---

## External grounding

### A2A 1.0 specification — does the spec endorse the dual-use claim?

The official A2A specification ([a2aproject/A2A spec.md](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)) defines `Task` as **"the fundamental unit of work managed by A2A, identified by a unique ID. Tasks are stateful and progress through a defined lifecycle."** Critically, the spec scopes Task to **A2A protocol operations** — it does not endorse, mention, or even acknowledge the use of the same `Task` dataclass for intra-process delegation. Devin's framing that the dual use "conforms to A2A 1.0 spec" is **not supported by spec text**; the spec is silent on intra-process semantics, which is a different posture from "approves of."

The spec imposes hard MUST-level obligations that ratchet up the bar:

- **"Servers MUST implement authorization checks on every A2A Protocol Operations request."** ([A2A spec §authorization](https://github.com/a2aproject/A2A/blob/main/docs/specification.md))
- **"Implementations MUST scope results to the caller's authorized access boundaries as defined by the agent's authorization model... Even when `contextId` or other filter parameters are not specified in requests."**
- **"Task IDs are server-generated when a new task is created. Agents MUST generate a unique taskId for each new task. Client-provided taskId values for creating new tasks is NOT supported."**
- **"Agents MUST reject messages containing mismatching `contextId` and `taskId`."**
- In-Task Authorization is spec'd as an **explicit state machine** via `TASK_STATE_AUTH_REQUIRED`, not via implicit `metadata["source"]` tags.

### Microsoft Foundry A2A authentication concepts

[Microsoft Learn on A2A authentication](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-to-agent-authentication) distinguishes formally between **shared authentication, individual (per-user) authentication, agent identity, project managed identity, and OAuth identity passthrough** — five typed identity postures, each with explicit role-assignment requirements. The pattern is: identity-as-typed-first-class-concept with explicit posture per call site.

### Ping Identity on A2A agent trust boundaries

[Ping Identity for AI](https://developer.pingidentity.com/identity-for-ai/identity/idai-agent-types.html) defines four typed agent classes (unmanaged personal agents, digital assistants for consumers, digital assistants for workforce, digital workers) — each placed **inside or outside the organizational trust boundary** by typed declaration, not by tag. "The digital worker is completely within your organization's trust boundary. It requires its own identity and set of credentials to perform actions as itself."

### Palantir Foundry — Action Log, Action Type, audit lifecycle

[Palantir Foundry Action Log](https://palantir.com/docs/foundry/action-types/action-log/) makes the typed lifecycle explicit: **"The Action Log models all Action submissions as object types to be analyzed and displayed in object-aware Foundry tooling... Action Log object types map one-to-one with Action types. Submitting an Action generates a single new object of the corresponding Action Log object type. This newly-created object is automatically linked to all objects edited by the submitted Action."**

The Palantir grammar is: `ActionType` (definition) → `Action` (single transaction) → `ActionLog object` (one-per-submission, automatically linked to mutated objects, optionally storing context-state-at-submission). The submission is a **first-class typed object**, not a log line or a JSONL append. ([Action Types overview](https://palantir.com/docs/foundry/action-types/overview/))

For deeper-than-Action history, [Palantir community: Edit History vs Action Logs](https://community.palantir.com/t/edit-history-vs-action-logs/2890) makes a sharp typed distinction: **"Edits History is tracked implicitly within the Highbury data store and is intrinsic to the *object itself* — rather than a side effect of the action writing the edit — so any edits are captured, regardless of their source."** Object mutation tracking is **store-intrinsic**, not action-derived.

Function-backed Actions ([Function-backed Actions overview](https://palantir.com/docs/foundry/action-types/function-actions-overview/)) ratchet typed validation further: Functions must be annotated with `@OntologyEditFunction()`, and **"The provenance of the Action is set according to the provenance of the selected minimum Function version. If a newer release of the Function returns edits outside of this provenance (for example, an additional Object type), Action execution will fail."** Provenance is enforced at runtime, not declared in a doc.

[Palantir Foundry Security Audit logs](https://palantir.com/docs/foundry/security/audit-logs-overview/) layer typed audit-categories on top — `audit.2` and `audit.3` schemas with service-agnostic guarantees in `audit.3` that **"for any particular log it is possible to tell (1) what auditable event created it and (2) exactly what fields it contains."** Typed end-to-end.

### Temporal — the canonical workflow-run boundary

[Temporal Workflow Execution docs](https://docs.temporal.io/workflow-execution) define the boundary with **three typed identifiers, not one**:

> "A Workflow Execution is uniquely identified by its **Namespace, Workflow Id, and Run Id**."

And explicitly distinguishes:

> "While the **Workflow Definition** is the code that defines the Workflow, the **Workflow Execution** is created by executing that code." ... "A **Workflow Execution Chain** is a sequence of Workflow Executions that share the same Workflow Id. Each link in the Chain is often called a **Workflow Run**."

Two separate timeouts apply: **"The Workflow Execution Timeout applies to a Workflow Execution Chain. The Workflow Run Timeout applies to a single Workflow Execution (Workflow Run)."** This is the level of typed boundary discipline a PhD-grade durable-execution system carries.

[Temporal — what does preserving state really mean (Cornelia Davis)](https://blog.corneliadavis.com/temporal-what-does-preserving-state-really-mean-ebdca256526f) makes the cascade explicit: workflow inputs persisted, activity results persisted, **workflow history persisted as a typed event log**, replay deterministic. "Temporal preserves enough state to recreate the complete state of the workflow at any point."

### LangGraph — typed thread/checkpoint/super-step boundary

[LangGraph Persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence) carry four typed concepts:

> "A **thread** is a unique ID or thread identifier assigned to each checkpoint saved by a checkpointer. It contains the accumulated state of a sequence of runs."
> "The state of a thread at a particular point in time is called a **checkpoint**."
> "A checkpoint is a snapshot of the graph state saved at each **super-step** boundary and is represented by a `StateSnapshot` object."
> "LangGraph creates a checkpoint at each super-step boundary. A super-step is a single 'tick' of the graph where all nodes scheduled for that step execute (potentially in parallel)."
> "When invoking a graph with a checkpointer, you **must** specify a `thread_id` as part of the `configurable` portion of the config."

Four typed concepts (thread / run / checkpoint / super-step). Three typed timeboxes (thread, run, super-step). One enforced invariant (`thread_id` is mandatory at invocation).

### Semantic layer architecture — typed first-class identity is the industry default

[typedef.ai on Semantic Layer Architectures](https://www.typedef.ai/resources/semantic-layer-architectures-explained-warehouse-native-vs-dbt-vs-cube) and [dbt Labs on MetricFlow](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works) both center on **typed semantic models** with explicit identity at the model layer, not at the workflow layer. Snowflake Semantic Views, dbt MetricFlow, and Cube all enforce typed identifiers on entities, dimensions, and measures — none of them allow string-typed cross-boundary identity as a default.

---

## Gaps surfaced

### Gap 1: "Conforms to A2A 1.0 spec" is unsubstantiated — the spec doesn't speak to intra-process dual use

Devin's Slice E conclusion that the dual use of `A2ATask` for both external (gateway-ingested HTTP) and internal (intra-process `A2AClient.delegate()`) "follows the A2A 1.0 spec design" is not supported by the A2A specification. The [spec text](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) defines `Task` as the unit of work for **A2A protocol operations** — it is silent on intra-process delegation. Silence is not endorsement. By contrast, every typed-identity precedent (Temporal namespace+workflowId+runId, LangGraph thread_id, Microsoft Foundry's five identity postures, Ping Identity's four trust-boundary classes) treats trust-boundary placement as a **typed-first-class declaration**, not a string tag in `metadata["source"]`. A PhD-grade system would **type `A2ATask` differently across boundaries** — e.g. `ExternalA2ATask` vs `InternalDelegationTask`, both adapting to a common `WorkUnit` trait — and let the type system enforce what `metadata["source"]` currently enforces by convention.

### Gap 2: `CanonicalWorkflowState` has no producer — Temporal's `Namespace + WorkflowId + RunId` triple shows what's actually missing

Devin admits `CanonicalWorkflowState` (`operator_core/contracts.py:217`) is "a declared shape with no producer." Compare with [Temporal's typed boundary](https://docs.temporal.io/workflow-execution): "A Workflow Execution is uniquely identified by its **Namespace, Workflow Id, and Run Id**." Temporal's typed triple — and the **Workflow Execution Chain** abstraction that links runs sharing a workflowId across continue-as-new boundaries — is what a PhD-grade workflowRun looks like. The dharma_swarm gap is not just "missing type"; it's missing the **identifier triple** (mission/workflowDefinition/workflowRunId), missing the **chain semantics** (multi-run history under one logical workflow), and missing the **timeout taxonomy** (run timeout vs execution-chain timeout vs super-step timeout — three distinct typed bounds in Temporal+LangGraph). Calling this "cosmetic fragmentation" understates the engineering distance.

### Gap 3: Palantir's `ActionLog` model exposes the real shape of "applied" — and dharma_swarm has no analog

[Palantir Action Log](https://palantir.com/docs/foundry/action-types/action-log/) shows what a typed "applied action" record looks like: a first-class object type, one-per-submission, automatically linked to every mutated object, optionally capturing context-state-at-submission. This is exactly the missing surface in dharma_swarm — `RuntimeStateStore.session_events` is a log table, not a typed `ActionLog`-style object type linked to mutated ontology objects. Devin's `partially_confirmed` verdict on Slice D should escalate to `confirmed` once you measure against the Palantir bar: dharma_swarm has 13 fragmented state surfaces and **zero** typed `applied-action` objects auto-linked to ontology mutations. The earlier andon Slice C2 finding (`execute_action` at `ontology.py:637` logs success without applying mutations) is the inverse symptom of the same disease — no typed `ActionLog` writeback contract.

### Gap 4: `metadata["source"]` tag is a probabilistic convention; auth boundaries demand typed enforcement

Devin's defense of A2ATask dual-use rests on four runtime conventions: `X-A2A-Key` header at the gateway, `metadata["source"] = "trishula"` on bridge ingest, `from_agent = "remote"` on gateway-parsed tasks, and `_MAX_DELEGATION_DEPTH = 10` for cycle detection. Every one of these is **runtime-checked, not type-checked**. Compare [Microsoft Foundry A2A authentication](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-to-agent-authentication), where each call site declares one of **five typed identity postures** (shared / individual / agent identity / project managed identity / OAuth passthrough) and role-assignment is enforced by the Entra ID service before the call even reaches application logic. The A2A spec itself ([§3 authorization](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)) requires "Servers MUST implement authorization checks on every A2A Protocol Operations request" — which dharma_swarm satisfies only for the external HTTP path, not for the internal `A2AClient.delegate()` direct-function-call path. The internal path **bypasses the gateway entirely** (per Devin's own admission), which means the spec-mandated MUST for "every request" is satisfied selectively, not uniformly. That is a state-leak vector behind a politeness convention.

### Gap 5: Devin's "13 layered owners — no two write to the same table" is true and irrelevant

The Slice D defense ("No two modules write to the same table or file") proves only that fragmentation is non-collisional at the persistence layer. But the operative question for a PhD-grade workflow runtime is not "do writers collide" — it's "**is there one typed boundary that traces a workflow from dispatch through execution to outcome with replay-deterministic history**." That's the Temporal Workflow Execution Chain ([docs](https://docs.temporal.io/workflow-execution)) and the LangGraph thread-of-checkpoints ([docs](https://docs.langchain.com/oss/python/langgraph/persistence)) shape. Thirteen non-colliding tables that each capture a sliver of state, none of which can replay the workflow, is functionally **worse** than one canonical store — it means the system can never answer "what happened during workflow run X" from a single typed query.

---

## Adversarial questions

1. **Where in the A2A 1.0 spec is intra-process delegation using the same `Task` dataclass endorsed?** The Slice E verdict asserts conformance — cite the spec section number or retract the claim. (My read of [the spec](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) finds zero text endorsing or discussing intra-process Task usage; the spec scopes Task to "A2A protocol operations.")

2. **For `A2AClient.delegate()` — the intra-process path that bypasses `NodeGateway` — how is the A2A spec's MUST-level requirement satisfied: "Servers MUST implement authorization checks on every A2A Protocol Operations request"?** If the answer is "internal calls aren't protocol operations," then by what type or trait is `A2ATask` declared to be in protocol mode vs internal mode? `metadata["source"]` is a string tag, not a type discriminator.

3. **What is the dharma_swarm equivalent of Temporal's `Namespace + WorkflowId + RunId` triple?** Devin names `DelegationRun` (scoped to single delegation), `MissionState` (strategic), `LoopHealth` (tick-level), `CanonicalWorkflowState` (no producer). None of these is the triple. Without the triple, how is "workflow run X" addressable as a first-class entity for replay, audit, time-travel, or governance gating?

4. **Where is dharma_swarm's `ActionLog` analog?** [Palantir's pattern](https://palantir.com/docs/foundry/action-types/action-log/) is: every Action submission generates one typed `ActionLog` object automatically linked to every mutated ontology object, optionally capturing context-state-at-submission. The verdict notes `RuntimeStateStore.session_events` (an FTS5 log table). Is `session_events` the analog? If so, where is the one-to-one mapping with ActionType, the auto-linking to mutated objects, the context capture? If not, what is the planned typed surface?

5. **For the 13 state owners enumerated in Slice D — which is the system-of-record for a workflow's final outcome?** Devin calls `RuntimeStateStore` the "canonical control plane," but immediately notes it tracks `sessions`, `task_claims`, `delegation_runs`, `session_events` — none of which is a typed `workflowRun outcome` record. If a regulator asked "what was the outcome of workflow X, who approved it, what objects did it mutate, what was the state-of-world at submission" — which of the 13 surfaces answers that, and which `file:line` is the join?

---

## Recommended next move

**This PR is research-grade evidence, not a synthesis — and it understates the engineering distance to PhD-grade.** Devin's `partially_confirmed` (Slice D) and `overstated` (Slice E) verdicts are **factually accurate at the file:line level** — the 13 state surfaces are real, the 4 A2ATask sites are real, the auth/source-tag/cycle-detection mechanisms exist as described. Codex's framing in those slices was indeed softer than reality. But the verdict-level framing is itself too soft: "cosmetic fragmentation" and "conforms to A2A 1.0 spec" both fail when measured against Palantir+Temporal+LangGraph+A2A-spec primary sources. The dharma_swarm gap is **typed-boundary discipline** — every reference system (Temporal Namespace+WorkflowId+RunId, LangGraph thread/checkpoint/super-step, Palantir ActionType→ActionLog, A2A spec Task identity rules) carries typed identifiers and typed lifecycle records as first-class enforced contracts, not string tags and JSONL ledgers.

**Do not merge PR #418 into PROPOSED_VOCABULARY without Claude/Hermes synthesis that escalates the framing.** The verdicts should land as **Stage-1 evidence only** — the file:line inventories are useful, but the "layered not competing" and "conforms to A2A 1.0 spec" headline conclusions need adversarial review before they harden into doctrine. The fresh audit (v0.0.3.2) against clean `origin/main` should explicitly test: (a) Is there a typed `workflowRun` boundary with a Temporal-equivalent identifier triple? (b) Is there a Palantir-equivalent `ActionLog` linking applied actions to mutated ontology objects? (c) Are A2A protocol-operation MUSTs satisfied uniformly across external HTTP and internal delegation paths, or selectively? If any of those three answers is "no," the system is not PhD-grade — and Devin's "intentional and well-bounded" framing should be reconciled accordingly through the andon four-bucket discipline (wheat / chaff / known-transitional / framing-error).

Standing posture: kill nothing — metabolize. The 13 state surfaces and 4 A2ATask sites are real organs. The question is whether dharma_swarm grows the typed-boundary spine (workflowRun / ActionLog / typed-identity discriminator) that unifies them, or stays at 13 layered conventions held together by `metadata["source"]` tags.

---

## Citations

Primary sources (PhD-grade external grounding):

1. [A2A 1.0 specification — a2aproject/A2A](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) — Task identity rules, authorization MUSTs, contextId/taskId semantics
2. [Microsoft Learn — A2A authentication concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-to-agent-authentication) — five typed identity postures for A2A endpoints
3. [Ping Identity for AI — agent types](https://developer.pingidentity.com/identity-for-ai/identity/idai-agent-types.html) — four typed trust-boundary agent classes
4. [Palantir Foundry — Action Log](https://palantir.com/docs/foundry/action-types/action-log/) — `ActionLog` as typed one-per-submission object type
5. [Palantir Foundry — Action Types overview](https://palantir.com/docs/foundry/action-types/overview/) — ActionType / Action / submission semantics
6. [Palantir community — Edit History vs Action Logs](https://community.palantir.com/t/edit-history-vs-action-logs/2890) — store-intrinsic vs side-effect tracking
7. [Palantir Foundry — Function-backed Actions overview](https://palantir.com/docs/foundry/action-types/function-actions-overview/) — provenance enforcement at runtime
8. [Palantir Foundry — Security Audit Logs overview](https://palantir.com/docs/foundry/security/audit-logs-overview/) — `audit.2` / `audit.3` typed schemas with service-agnostic guarantees
9. [Temporal — Workflow Execution overview](https://docs.temporal.io/workflow-execution) — Namespace + WorkflowId + RunId triple, Workflow Execution Chain
10. [Temporal — what does preserving state really mean (Cornelia Davis)](https://blog.corneliadavis.com/temporal-what-does-preserving-state-really-mean-ebdca256526f) — workflow history as typed event log
11. [LangGraph Persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence) — thread / checkpoint / StateSnapshot / super-step typed boundary
12. [typedef.ai — semantic layer architectures](https://www.typedef.ai/resources/semantic-layer-architectures-explained-warehouse-native-vs-dbt-vs-cube) — warehouse-native vs transformation-layer vs OLAP-acceleration
13. [dbt Labs — how the dbt semantic layer works with MetricFlow](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works) — typed semantic models / MetricFlow specification

Mission artifacts referenced:

- PR #418 (this artifact): https://github.com/AmitabhainArunachala/dharma_swarm/pull/418
- ANDON brief: `docs/research/palantir-ontology/vocabulary-census/andon/2026-06-01T0628Z-andon-audit-verification.md`
- Earlier auto-grounding: PR #415, PR #417, PR #419
- v0.0.3.2 audit prompt (workspace): `audit_prompt_v0.0.3.2.md`
