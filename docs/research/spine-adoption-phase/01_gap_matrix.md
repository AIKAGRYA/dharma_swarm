# Spine Adoption Saturation — Surface Gap Matrix

**Date:** 2026-06-01
**Audit source:** `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2` (base HEAD `2737b26d`, branch `codex/runtime-truth-spine-v2`)
**Synthesized by:** perplexity-computer (Stage-1 evidence-only)
**Authority chain:** blast-radius audit (`execution_identity_lineage_blast_radius_audit.md`, 41KB, dated 2026-06-01) + v2 build report + evidence plan
**Verification command run by v2 build:** `159 passed, 2 warnings in 11.99s`

---

## Coverage Snapshot (auditor's own count)

| Bucket | Count | Percent |
| --- | --- | --- |
| Classified surfaces | 16/16 | 100% |
| **Joined** (canonical identity + receipts) | 5/16 | **31.25%** |
| **Adapter-ready** (carries identity, enforcement pending) | 4/16 | 25.0% |
| **Joined or adapter-ready** | 9/16 | 56.25% |
| **Missing / Quarantine** | 7/16 | 43.75% |

**PhD-grade frame:** Temporal/DBOS/Restate would call this state "partial durable execution coverage." A production durable-execution platform considers the system safe only when **100% of side-effecting boundaries are joined or explicitly quarantined**. We are at 31% canonical and 56% adapter-ready. The remaining 43.75% includes **ToolRegistry, Ontology actions, Workflow/checkpoint, MessageBus consume, raw MessageBus send, engine artifacts, and self-mod proposals** — every one of which is a side-effecting boundary by Temporal's own definition ([temporal.io/blog/idempotency-and-durable-execution](https://temporal.io/blog/idempotency-and-durable-execution)).

---

## Surface Gap Matrix — 16 surfaces × {adopted | adapted | quarantine | legacy / missing}

| # | Surface | Status | Evidence (file:line) | What's Missing | Risk if Untreated |
|---|---|---|---|---|---|
| 1 | **A2A local submit** | **joined** | `a2a/a2a_server.py:273` (`require_execution_identity=False`); identity ensure at `:399`; idempotency `:345`; receipt `:367` | Default is `require_execution_identity=False`. Production mode flip pending. | Duplicate A2A submits possible when ingress called without identity. |
| 2 | A2A HTTP node gateway | adapter-ready | (per evidence plan §Surface Matrix) Top-level identity fields parsed/serialized | Identity not required across hop; HTTP boundary can drop fields | Cross-node lineage breaks; `external_a2a_task_id` parallel A2A IDs may not join. |
| 3 | **RuntimeLifecycle task claim** | **joined** | `runtime_lifecycle.py:108` (`require_identity=True` mode rejects missing trace/correlation/claim) | Strongest current canonical seam | None on enforced path; legacy bypass at `runtime_state.py:1595` still exists. |
| 4 | **RuntimeLifecycle delegation run** | **joined** | `runtime_lifecycle.py:362` (`child_spawned` receipt), `:375` (`child_completed`) | None on canonical path | Orphan child runs from `opportunity_dispatcher.py:155` legacy path. |
| 5 | **RuntimeLifecycle artifact record** | **joined** | `runtime_lifecycle.py:416`, `:453`, `:474` (`artifact` + `artifact_written` receipts) | None on this path | Engine artifact store (`engine/artifacts.py:111`) writes independent artifact_ids — **parallel lineage**. |
| 6 | **MessageBus emit_event (idempotent path)** | **joined** | `message_bus.py:598` (key param), `:615` (identity construct), `:625` (idempotency check), `:631` (begin), `:675` (complete) | Path only triggered when caller supplies `idempotency_key` | Callers without idempotency_key silently bypass guard. |
| 7 | MessageBus send (raw) | **missing** | `message_bus.py:184` — raw insert, no identity | Identity, receipt, idempotency | Unjoinable message delivery; consumer cannot reconstruct sender run. |
| 8 | MessageBus consume_events | **missing** | `message_bus.py:683` — marks consumed without receipt | `message_consumed` receipt + receiver-side idempotency | False idempotency: presence of key ≠ pre-side-effect guard ([Kafka idempotent consumer + outbox](https://www.lydtechconsulting.com/blog/kafka-idempotent-consumer-transactional-outbox)). |
| 9 | Orchestrator result persistence | adapter-ready | (per v2 evidence plan) Provenance/artifact path carries run/trace/correlation | Hard boundary not closed | Free-text path was just gated at `orchestrator.py:2467` (`allow_free_text_result_path`), but generalized enforcement not in place. |
| 10 | TaskBoard task metadata | adapter-ready | `task_board.py:29` (trace_id column), `:207` (`_new_id`), `:212` (copies ambient `CorrelationContext.trace_id`) | Stores **trace only**, not full ExecutionIdentity. No mandatory adapter. | TaskBoard is the dispatch fan-out point. Without mandatory adapter, every downstream organ inherits underdetermined identity. |
| 11 | Checkpoint human interrupt | adapter-ready | `checkpoint.py:78`, `:102` (`auto_approve=False` default — **fail closed** — landed in v2) | Durable wait/approval receipts pending | Approval state not durably joined to run; resume after restart loses approval lineage. |
| 12 | **Ontology execute_action** | **missing (queued)** | `ontology.py:763` (execute), `:798` (telos gate), `:872` (success log); `ActionDef.modifies` at `:161`, `requires_approval` at `:174`; **`ontology_action_id` absence count = 0** | C2 tollbooth: declared `modifies` / `requires_approval` must become **enforced** runtime contracts. Action ID must be generated and joined to run. | Domain mutations cannot be reconstructed from `run_id`. Palantir's own model (Action Log object-per-Action — [palantir.com/docs/foundry/action-types/action-log/](https://palantir.com/docs/foundry/action-types/action-log/)) generates one Action Log object per Action submission and foreign-keys it to every edited object. **We don't have that.** |
| 13 | **Tool registry side effects** | **missing** | `tool_registry.py:58` (class), `:129` (dispatch) — **no ExecutionIdentity, no run_id, no trace_id, no idempotency hits in file-level search** | Mandatory identity + `side_effect_intent` / `side_effect_complete` receipts | Tools are the primary effect surface. A tool call that writes to disk, sends a message, or calls an external API with no idempotency is a **classic dual-write** failure ([microservices.io/patterns/data/transactional-outbox.html](https://microservices.io/patterns/data/transactional-outbox.html)). |
| 14 | **Graph / workflow checkpoints** | **missing** | `workflow.py:231` (`workflow_id` generation), `workflow_graph.py:240` (defaults `wfg_<ts>`), `durable_execution.py:99`, `:220` | **No `workflow_id → run_id` mapping receipt anywhere in audited search** | Cannot reconstruct ledger from `workflow_id`. Temporal's published contract: `WorkflowId` + `RunId` form a 2-tuple where WorkflowId is business identity and RunId is platform identity, both visible in event history ([docs.temporal.io/workflow-execution/workflowid-runid](https://docs.temporal.io/workflow-execution/workflowid-runid)). We have neither mapping. |
| 15 | **Self-modification proposals** | **missing** | `proposal_id` widespread, but `verification_id`, `promotion_id`, `revert_id` **absence count = 0**. `runtime_state.py:2364` has self-mod receipt helpers — **not called on hot path** | proposal/gate/apply/verify/promote/revert receipt chain | Self-mod lifecycle cannot be reconstructed as one runtime chain. A proposal can pass gates and apply without runtime-ledger linkage. |
| 16 | NATS / JetStream | **quarantine** | (per v2 evidence plan) Not selected for local deterministic evidence; no live NATS calls | Quarantine boundary explicitly named | OK as long as quarantine is enforced — but currently any code can publish to NATS without identity. |
| 17 | MCP server / tool access | **missing** | (per v2 evidence plan) MCP/tool boundary needs adapter before side effects | Adapter | Same risk as #13 plus external service surface. |
| 18 | Free-text file extraction | **quarantine** | `orchestrator.py:2467` requires `task_metadata.get("allow_free_text_result_path") is True` — **landed in v2** | Path stays quarantined until deterministic tollbooth | OK if quarantine enforced; risk if flag becomes default-true anywhere. |

**Note:** the evidence plan calls out 16 surfaces. The blast-radius audit's §11 lists 27 file groups in the **blast radius** of mandatory identity. The 16-surface matrix is the audit boundary; the 27-file group is the migration boundary. Both numbers matter.

---

## Same-Name Collision Risks (PhD-grade ID hygiene)

The auditor's §3 lists 12 same-name collisions. The three most dangerous for a Palantir-grounded PhD-bar system:

1. **`trace_id`** has **three independent generators**: `CorrelationContext` (`correlation_context.py:64`), `RuntimeEnvelope` (`runtime_contract.py:67`), `ExecutionIdentity` (`identity.py:78`). **Risk:** code can believe it is traced while missing run/claim/idempotency. **Palantir-grade fix:** require `trace_id` to be carried **inside** `ExecutionIdentity` at all runtime boundaries — never accept a bare `trace_id` arg.

2. **`run_id`** has **four independent generators**: canonical (`identity.py:80`), `RuntimeStateStore.new_run_id`, workflow-local (`workflow.py:231`), legacy sync (`opportunity_dispatcher.py:157`). **Risk:** legacy helpers can write `delegation_runs` rows without `execution_identities`. **Temporal-grade fix:** `execution_identities.run_id` must become the FK-owner for all runtime runs ([Temporal best practice: business-meaningful WorkflowIds as idempotency keys](https://temporal.io/blog/idempotency-and-durable-execution)).

3. **`workflow_id` vs `run_id`** — **no mapping found**. **Risk:** checkpoints cannot be reconstructed by `run_id` unless caller manually records a mapping. **DBOS-grade fix:** every workflow start records a `workflow_started` mapping receipt that joins `workflow_id` to `run_id` ([DBOS workflow IDs as idempotency keys](https://docs.dbos.dev/tutorials/idempotency-tutorial)).

---

## External Anchors (PhD vs 5th Grade)

| Concern | Industry Reference | dharma_swarm v2 Status | Gap |
|---|---|---|---|
| Workflow ID as business idempotency key | Temporal: "Use business-meaningful WorkflowIds as idempotency keys" ([temporal.io/blog](https://temporal.io/blog/idempotency-and-durable-execution)) | `ExecutionIdentity.idempotency_key` exists, optional, only enforced on A2A and MessageBus-emit paths | Tool, ontology, workflow, self-mod paths don't enforce idempotency_key |
| WorkflowId + RunId 2-tuple | Temporal canonical contract ([docs.temporal.io](https://docs.temporal.io/workflow-execution/workflowid-runid)) | `task_id + run_id` present, but `workflow_id` is a third parallel ID with no mapping | Mapping receipt missing |
| Transactional outbox for at-least-once + idempotent consumer | Industry standard ([microservices.io](https://microservices.io/patterns/data/transactional-outbox.html), [decodable.co](https://www.decodable.co/blog/revisiting-the-outbox-pattern)) | MessageBus emit has idempotency pre-side-effect, but raw send + consume don't | Consume-side receipts + receiver idempotency missing |
| Action Log: one log object per action submission, FK-linked to every edited object | Palantir Foundry Action Log ([palantir.com](https://palantir.com/docs/foundry/action-types/action-log/)) | `ActionDef.modifies` declared in `ontology.py:161` but not **enforced**; `ontology_action_id` doesn't exist | C2 tollbooth slice queued, not landed |
| Immutable workflow definitions with versioning | Restate immutable deployments ([restate.dev](https://www.restate.dev/blog/solving-durable-executions-immutability-problem)); Temporal worker versioning + patch API | No workflow version field on identity or receipt | All proposals/self-mods run on current code; no version-pinning |
| Strangler-fig façade for legacy migration | Microsoft Azure Architecture Center ([learn.microsoft.com](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)); Thoughtworks ([thoughtworks.com](https://www.thoughtworks.com/en-us/insights/articles/embracing-strangler-fig-pattern-legacy-modernization-part-one)) | `create_task_claim_sync` and `create_delegation_run_sync` are legacy bypasses with no façade | No deprecation shim, no CI guard against legacy callers |
| Shadow runs during migration | DBOS migration playbook ([thinhdanggroup.github.io](https://thinhdanggroup.github.io/migrate-temporal-to-dbos/)); shadow agent deployment | No shadow path. Migration is direct toggle of `require_identity` | Risk of regression on flip-day |

---

## The Five Adversarial Holes (PhD-grade, named)

1. **The "idempotency_key present" ≠ "idempotency enforced" trap.**
   - **Evidence:** `runtime_state.py:2501` (`try_begin_idempotent_side_effect`) is the **only** pre-side-effect guard. The field `idempotency_key` appears 207 times in code. Pre-guard is invoked on **two** paths (A2A submit, MessageBus emit).
   - **Temporal frame:** "Activities aren't the only thing in Temporal that might be executed twice" ([temporal.io/blog](https://temporal.io/blog/idempotency-and-durable-execution)). Every side-effecting boundary needs explicit pre-guard. **We have ~5%.**

2. **The "run_id without execution_identity" ledger lie.**
   - **Evidence:** `create_task_claim_sync` (`runtime_state.py:1595`) and `create_delegation_run_sync` (`runtime_state.py:1686`) write `task_claims` and `delegation_runs` rows. `OpportunityDispatcher` uses both (`:184`, `:193`). Neither writes to `execution_identities`.
   - **Consequence:** `get_run_ledger(run_id)` returns partial truth. A query "what happened to run X?" returns claims/runs but no identity row. **This is the equivalent of a Foundry Action that doesn't write an Action Log object.**

3. **The "parallel artifact lineage" fork.**
   - **Evidence:** `RuntimeArtifactStore.create_text_artifact` (`artifact_store.py:40`) accepts optional run/trace. `engine/artifacts.py:90`'s `create_artifact` generates artifact_id independently with **no run/trace**.
   - **Consequence:** Two artifact systems coexist. An artifact created via the engine path is unjoinable to any run. Palantir's model is one artifact lineage per Ontology object type with **mandatory** writeback ([palantir.com/docs/foundry/object-edits/materializations](https://palantir.com/docs/foundry/object-edits/materializations/)).

4. **The "workflow_id is not run_id" silent split.**
   - **Evidence:** `workflow.py:231`, `workflow_graph.py:240` (defaults `wfg_<ts>`), `durable_execution.py:99`. **No mapping receipt anywhere.**
   - **Consequence:** dharma_swarm has a workflow system and a runtime-truth-spine system that don't share identity. Temporal explicitly designed against this: WorkflowId + RunId is a single tuple, queryable as one unit from event history.

5. **The "self-mod ID set is half-built" governance gap.**
   - **Evidence:** `proposal_id` widespread. `verification_id`, `promotion_id`, `revert_id` absence count = 0. Self-mod receipt helpers exist at `runtime_state.py:2364` and are **never called**.
   - **Consequence:** the most security-sensitive surface (self-modification) is the **least joined**. A proposal can be applied with no runtime receipt that says "this code change ran." This is the exact gap an AI-safety review board would flag first.

---

## The Five Adversarial Questions (the artifact does not answer)

1. **What is the metric?** The v2 report cites 31.25% joined / 56.25% joined-or-adapter-ready. Is **100% joined** the goal, or is some quarantine permanent? If the latter, who approves what stays quarantined? (Palantir's Action Log assumes 100% — every Action is logged.)

2. **What is the CI gate?** There's no test that fails when new code adds a row to `task_claims` / `delegation_runs` / `artifact_records` without a matching `execution_identities` row. Without this gate, the legacy bypass re-opens with the next merge.

3. **What is the workflow-version contract?** Self-modification implies code changes. Temporal pins WorkflowId to a worker BuildId; Restate uses immutable deployments. dharma_swarm has neither. **If proposal P applied on code v17 needs to revert on code v23, what determines compatibility?**

4. **What is the shadow path?** Flipping `require_identity=True` on A2A ingress is a one-way door. DBOS's published migration playbook ([thinhdanggroup.github.io](https://thinhdanggroup.github.io/migrate-temporal-to-dbos/)) uses shadow runs comparing old + new for a defined window before cutover. We have no shadow.

5. **What survives a restart mid-flight?** RuntimeStateStore is SQLite. If the process dies between `try_begin_idempotent_side_effect` and `complete_idempotent_side_effect`, what is the recovery rule? Temporal's answer: history replay. DBOS's answer: workflow version + recoverable state. **dharma_swarm has no published recovery rule.**

---

## Recommended Migration Posture

The v2 work is **real and substantial** — the auditor's verdict ("ExecutionIdentity is no longer vapor, but it is still optional infrastructure unless the remaining boundary surfaces are adapted or quarantined") is the correct read.

The next phase should not be "add more features." It should be **saturation** — drive joined-or-quarantined from 56% to 100% on the named surfaces, with CI gates that prevent regression. This is exactly the **strangler-fig** pattern: keep the legacy paths alive while progressively routing canonical surfaces through `ExecutionIdentity`, then retire the legacy.

Three named slices, in order:

1. **Slice A — Close the legacy bypass + add CI gate.** `create_task_claim_sync`, `create_delegation_run_sync`. The deepest fork. Required first because all downstream truth depends on the ledger not lying.

2. **Slice B — Wire adapters into the 5 missing boundaries.** TaskBoard create, MessageBus consume, ToolRegistry dispatch, raw MessageBus send, RuntimeArtifactStore writes. Compatibility-first: optional `require_identity` toggle that defaults false, tests prove fail-closed when true.

3. **Slice C — Mapping receipts for parallel lineages.** `workflow_id ↔ run_id`, `proposal_id ↔ run_id`, `ontology_action_id ↔ run_id` (and create that ID), `event_id ↔ run_id`, `engine_artifact_id ↔ run_id`. Mapping preserves local meaning; ledger becomes queryable.

The auditor named these same three slices independently. **Three-source convergence**: claude C2 doctrine, v0.0.3.3 audit §21 ExecutionIdentity ExecPlan, v2 worktree auditor's §14. All point at the same fix.

---

## What This Phase Is Not

- **Not adding new agents.** No new fleet members until spine adoption hits a defined saturation bar.
- **Not amending doctrine.** Doctrine already converged ("kill nothing — metabolize", co-equal contributors, runtime truth spine).
- **Not merging C2 ontology + spine in one PR.** The v2 auditor explicitly queued C2 ontology tollbooth as a separate slice. Mixing them re-introduces blast-radius confusion.
- **Not building a new durable execution engine.** dharma_swarm is **not Temporal/DBOS/Restate**. It's a custom spine on top of SQLite. The goal is operational discipline, not feature parity with industry workflow engines.

---

## Verdict — perplexity-computer, stage-1 evidence-only

The v2 work moves dharma_swarm from "vapor canonical identity" to "real canonical identity on 5 surfaces with adapters on 4 more, all backed by 159 passing tests." This is a **material PhD-relevant advance** — not 5th grade anymore on the joined paths. **But the remaining 43.75% of named surfaces are the surfaces that an AI-safety review would prioritize first**: tools, ontology actions, workflow checkpoints, self-mod proposals.

The next phase is **saturation + CI enforcement + mapping receipts**. The auditor's three slices are the right slices. The master spec and Codex 5.5 plan in this folder execute them.
