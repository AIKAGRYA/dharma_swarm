# RFC: Verified Experiment Loop

**Status:** PROPOSED (RFC / design only — no runtime code)
**Layer:** Selection / evidence layer (sits *above* the Runtime Truth Spine)
**Depends on:** Runtime Truth Spine (`dharma_swarm/spine/`) reaching its Definition of Done
**Author lane:** Parallel to Runtime Truth Spine completion; does not modify runtime behavior
**Non-goal of this document:** Implementing the loop. This RFC defines objects, lifecycles, gates, and integration points only.

> Doctrine framing: **the Spine is the substrate; the Verified Experiment Loop is the selection/evidence layer.** Every claim, bet, experiment, result, and decision in this RFC is identified, traced, and made tamper-evident by Spine primitives that already exist (`ExecutionIdentity`, `EvidenceReceipt`, the `runtime_state` ledger, the `tollbooth`). This RFC adds no new identity, no new ledger, and no new transport.

---

## 1. Thesis

The Verified Experiment Loop exists to make swarm improvement **verifiable rather than vibes-based**. Today the swarm can mutate itself (`dgm_loop.py`), score fitness (`archive.py` 9-dimensional `FITNESS_DIMENSIONS`), and canary-promote (`canary.py`), but there is no single, auditable spine-grounded chain that proves a given change actually improved the system at equal budget, with claims linked to evidence and decisions.

Core loop:

```
Raw source / idea / repo issue
  → claim extraction
  → BetCard
  → experiment design
  → execution-grounded result
  → decision: kill / hold / mutate / scale / archive
  → wiki/memory update
  → routing/evolution update
```

Each arrow must be backed by a Spine `EvidenceReceipt` and carry one continuous `ExecutionIdentity` so the whole chain is replayable and tamper-evident. A change that cannot show this chain is not "improved" — it is unverified.

---

## 1a. Prior Art Inside This Repo

VEL graduates and joins existing systems. It does not create a parallel experiment/evidence stack. The following existing repo objects are direct prior art for VEL concepts:

| Existing system | Path | VEL concept it covers | Status |
|---|---|---|---|
| `recursive_discovery.py` | `dharma_swarm/recursive_discovery.py:78-160` | **Closest existing shadow Verified Experiment Loop.** Full bet→eval→candidate→experiment→witness→promotion chain with content-hashed receipts, recorded through `evaluation_registry` and observed in `control_surface.py`. | Graduate/extend — do not deprecate or supersede |
| `RuntimeReceipt` + `IdempotencyRecord` | `dharma_swarm/runtime_state.py:632,650` | Canonical persisted runtime receipt + exactly-once substrate (`IdempotencyRecord` = `INSERT OR IGNORE`; `record_runtime_receipt` = `INSERT OR REPLACE`, overwrite-idempotent not exactly-once). On the A2A path both are already written by `A2AServer.submit()` (`a2a_server.py:369`). | Existing persisted receipt to **associate** spine evidence with — do not mint a second one (see §3.3a) |
| `ExperimentRecord` / `ExperimentLog` | `dharma_swarm/experiment_log.py:16-88` | Append-only experiment log with `proposal_id`, `evidence_tier`, `promotion_state`. | Extend for VEL experiments — do not create new store |
| `Hypothesis` / `_RESEARCH_THREAD` | `dharma_swarm/self_research.py:24`; `ontology.py:1190` | Research question / falsifiable claim pipeline. | Extend/wrap for BetCard — do not create standalone class |
| `ArchiveEntry` / `EvolutionArchive` | `dharma_swarm/archive.py:135-289` | MAP-Elites archive with `FitnessScore` (9-dim), Merkle-chained. | Reuse for EvolutionCandidate storage |
| `DecisionRecord` / `DecisionLog` | `dharma_swarm/decision_ontology.py:161-485` | Typed decisions with evidence, objections, deterministic scoring. | Reuse — do not create second `DecisionRecord` class |
| `MemoryKernelReviewedCanonicalReceipt` | `dharma_swarm/memory_kernel/promotion_gate.py:80` | Multi-gate memory promotion proof with digest + rollback ref + `human_approved`. | Reuse for WikiUpdate terminal |
| `cost_tracker.py` / `LLMUsageSpan` / `economic_spine` | `dharma_swarm/cost_tracker.py:59`; `llm_burn.py:39`; `economic_spine.py:74` | Cost/token tracking, budget enforcement, provider usage. | Bridge — do not replace |
| `CorrelationContext` | `dharma_swarm/correlation_context.py:53` | Cross-layer trace/proposal/session identity via contextvars. | Reuse as-is |
| `MerkleLog` | `dharma_swarm/merkle_log.py:18` | Tamper-evident hash chain for provenance. | Reuse for LineageRecord — do not create new chain |

**Binding constraint:** Every VEL concept listed in §3 must be expressed as reuse or extension of an existing owner listed above. No standalone new class until the reuse decision is accepted per the [Receipt & VEL Equivalence Matrix](RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md).

---

## 2. Why Spine Comes First

BetCards, experiments, evidence, and decisions are **side-effecting, auditable, cross-surface objects**. They are exactly the class of object the Spine was built to govern. Building the loop before the Spine stabilizes would re-invent identity, provenance, and idempotency badly — the same drift the spine-adoption saturation phase is closing.

| Loop concept | Spine primitive it requires | Where it lives today |
|---|---|---|
| BetCard identity | `ExecutionIdentity` (`task_id`/`run_id`/`trace_id`/`correlation_id`/`idempotency_key`) | `dharma_swarm/spine/identity.py` |
| EvidenceReceipt for experiment evidence | `EvidenceReceipt` (canonical dispatch artifact, OTel GenAI shape) | `dharma_swarm/spine/receipt.py` |
| trace/correlation context → SwarmRun provenance | `trace_id` + `correlation_id` continuity invariant | `spine/__init__.py` correlation-spine doctrine |
| cost/token tracker → equal-budget comparisons | `EvidenceReceipt.input_tokens` / `output_tokens` / `cost_usd` | `spine/receipt.py` |
| tamper-evident history → auditability | `runtime_state` receipt ledger + `merkle_log.py` chaining | `runtime_state.py`, `merkle_log.py` |
| tollbooth/gates → promotion control | `require_execution_tollbooth(...)` fail-closed gate | `spine/tollbooth.py` |

Until the Spine's joined-or-adapter-ready ratio hits its floor (currently **75%**, target **≥95%**) and the legacy ledger bypass is closed, any "equal-budget improvement" claim is structurally dishonest because writes can still land without traversing the spine.

---

## 3. Proposed Core Objects

All schemas below are **proposal-level pseudocode** (Pydantic-style), consistent with existing repo conventions (`archive.py`, `experiment_log.py`, `decision_ontology.py`). No object introduces a new identity scheme — every object derives identity from `ExecutionIdentity` and persists via the existing `runtime_state` ledger or existing append-only stores.

### 3.1 BetCard
- **Existing owner:** `self_research.Hypothesis` / `_RESEARCH_THREAD` ontology type (`self_research.py:24`; `ontology.py:1190`).
- **Implementation rule:** Extend/wrap `Hypothesis` with `success_criteria` / `kill_criteria` / budget ref; register the extension as `TypeStatus.EXPERIMENTAL`.
- **Forbidden duplicate:** Do not create a standalone `BetCard` Pydantic class or table.
- **Purpose:** A single falsifiable claim the swarm is willing to spend budget testing.
- **Required fields:** `bet_id` (← `ExecutionIdentity.task_id`), `claim` (str), `source_ref` (raw source/issue/idea), `hypothesis`, `success_criteria`, `kill_criteria`, `created_at`, `execution_identity`.
- **Optional fields:** `parent_bet_id`, `tags`, `priority_score`, `estimated_cost_usd`.
- **Source of identity:** Spine `ExecutionIdentity.new(task_id=...)`.
- **Relation to Spine:** Identity + an `EvidenceReceipt` on creation (`operation="bet_open"`).
- **Storage proposal:** Extend existing `Hypothesis` / experiment store; receipt in `runtime_state`.
- **Non-goals:** Not a roadmap item; not a feature flag; no auto-execution on creation.

### 3.2 Experiment
- **Existing owner:** `experiment_log.ExperimentRecord` / `ExperimentLog` (`experiment_log.py:16-88`).
- **Implementation rule:** Extend existing `ExperimentRecord` with `held_out_eval_ref` + spine `correlation_id`/`trace_id` link fields.
- **Forbidden duplicate:** Do not create a new `Experiment` class or experiment store.
- **Purpose:** The designed procedure that tests a BetCard at a declared budget.
- **Required fields:** `experiment_id`, `bet_id`, `design` (tasks/eval set ref), `budget` (model, max tokens, max tool calls, cost ceiling), `held_out_eval_ref`, `execution_identity`.
- **Optional fields:** `baseline_ref`, `shadow_only` (bool), `seed`.
- **Source of identity:** Child `ExecutionIdentity` via `with_updates(parent_run_id=bet.run_id)`.
- **Relation to Spine:** Each run emits `EvidenceReceipt`s carrying tokens/cost.
- **Storage proposal:** Extends `experiment_log.py::ExperimentRecord` (already has `proposal_id`, `evidence_tier`, `promotion_state`) rather than a new table.
- **Non-goals:** No new benchmark runtime; reuse `experiments/petri_dish/` and `benchmarks/gauntlet.py`.

### 3.3 EvidenceReceipt usage
- **Existing owner:** `spine.receipt.EvidenceReceipt` (`spine/receipt.py:37`).
- **Implementation rule:** `spine.EvidenceReceipt` is the canonical in-flight dispatch proof. Do not subclass or fork it; link via `attributes`.
- **Forbidden duplicate:** Do not create a fifth receipt class.
- **Purpose:** The canonical proof artifact for every step (claim extraction, each experiment run, decision).
- **Required fields:** existing `EvidenceReceipt` fields — `trace_id`, `task_id`, `status`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `attributes`.
- **Source of identity:** `ExecutionIdentity.trace_id` (= `correlation_id` cross-layer alias).
- **Relation to Spine:** This **is** the spine object; the loop only consumes it. Use `attributes["dharma.attr.bet_id"]`, `"...experiment_id"`, `"...decision_id"` to link.
- **Non-goals:** Do not subclass or fork `EvidenceReceipt`; link via `attributes`.

### 3.3a Persistence Rule

`spine.EvidenceReceipt` is the canonical in-flight dispatch proof. `runtime_state.RuntimeReceipt` plus `IdempotencyRecord` is the canonical persisted runtime receipt and exactly-once substrate. `delegation_runs.receipt_json` may be used as a projection/cache for query convenience, but it is not the source of truth.

**Anti-double-write rule (binding, see `RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md` §4):** for any path where an inner runtime layer already writes a `RuntimeReceipt`, the spine/VEL layer must **not** write a second `RuntimeReceipt`. It may only return the in-flight `EvidenceReceipt` and optionally write a projection/cache.

The Verified Experiment Loop consumes spine `EvidenceReceipt`s and persisted `RuntimeReceipt`s. It must not create a second persistence path. For dispatch paths that **already** persist a `RuntimeReceipt`, VEL links the `EvidenceReceipt` to that existing `RuntimeReceipt` (shared `run_id` / deterministic `receipt_id`); it does not mint a new one. For paths that do **not** yet persist, adoption must happen at the single runtime owner of that path, never through a parallel writer.

Concretely on the **A2A path**, the persisted `RuntimeReceipt` + `IdempotencyRecord` are **already** written by `A2AServer.submit()` (`a2a_server.py:369`), reached through `submit_via_spine()` → `invoke_agent()`. Therefore:
- Do **not** make `spine/persistence.py` mint a `RuntimeReceipt` via `build_runtime_receipt(..., receipt_type="dispatch_evidence")` / `record_runtime_receipt` on this path — that would be a second `RuntimeReceipt` per dispatch (the double-write trap). `record_runtime_receipt` is `INSERT OR REPLACE` (overwrite-idempotent), not exactly-once; exactly-once is owned by `IdempotencyRecord` (`INSERT OR IGNORE`).
- `spine/persistence.py:persist_receipt()` (0 production callers) is at most a **projection-only** helper that writes `delegation_runs.receipt_json` through the existing delegation-run writer; its `UPDATE delegation_runs SET receipt_json` behavior is **not** source of truth and must not be promoted to a canonical writer.
- Invariant to hold: `count(runtime_receipts WHERE run_id = R) == 1` per A2A dispatch.

### 3.4 SwarmRun
- **Existing owner:** `runtime_state.DelegationRun` (`runtime_state.py:510`).
- **Implementation rule:** Projection/aggregation over `DelegationRun` + child receipts; no materialized object.
- **Forbidden duplicate:** Do not create a new run table or run-ledger system.
- **Purpose:** One full execution of the swarm against an experiment (the unit fitness is measured on).
- **Required fields:** `run_id` (← `ExecutionIdentity.run_id`), `experiment_id`, `agent_set`, `start/finish`, `aggregate_cost`, `receipt_ids` (list), `execution_identity`.
- **Optional fields:** `parent_run_id`, `canary` (bool).
- **Source of identity:** Spine `run_id`; the existing FK owner for runtime runs.
- **Relation to Spine:** Aggregates child `EvidenceReceipt`s for equal-budget comparison.
- **Storage proposal:** Projection over `runtime_state` run ledger (`get_run_ledger`); no new persistence.
- **Non-goals:** Not a new orchestrator; it observes runs, it does not drive them.

### 3.5 EvolutionCandidate
- **Existing owner:** `archive.ArchiveEntry` / `EvolutionArchive` (+ `FitnessScore`) (`archive.py:135-289`).
- **Implementation rule:** Store winners **and** losers in the existing MAP-Elites archive; reuse `FitnessScore` (9-dim).
- **Forbidden duplicate:** Do not create a new candidate store or a 7th "candidate" notion.
- **Purpose:** A proposed swarm mutation under evaluation (prompt, router weight, agent config).
- **Required fields:** `candidate_id`, `bet_id`, `mutation_spec`, `parent_id`, `fitness` (`archive.py::FitnessScore`), `promotion_state` (`execution_profile.PromotionState`), `evidence_tier`.
- **Optional fields:** `map_elites_cell`, `shadow_result_ref`.
- **Source of identity:** Spine identity via `proposal_id` field already on `ExecutionIdentity`.
- **Relation to Spine:** Reuses self-modification receipt chain (proposal→gate→apply→verify→promote/revert).
- **Storage proposal:** Existing `archive.py` EvolutionArchive (MAP-Elites + MerkleLog). No new store.
- **Non-goals:** No autonomous apply; candidates stay in shadow until the promotion gate.

### 3.6 BenchmarkResult
- **Existing owner:** `auto_grade.GradeCard` + `benchmark_registry` + petri-dish result models (`auto_grade/models.py:14`; `experiments/petri_dish/models.py:106`; `quality_gates.py`).
- **Implementation rule:** Cost-normalize an existing scorecard; record held-out-set hash on the result.
- **Forbidden duplicate:** Do not create a new scoring framework.
- **Purpose:** Scored, ground-truth-comparable output of a SwarmRun on the held-out eval.
- **Required fields:** `result_id`, `run_id`, `experiment_id`, `scores` (per-dimension), `cost_normalized_score`, `unsupported_claim_rate`, `receipt_ids`.
- **Optional fields:** `judge_model`, `raw_traces_ref`.
- **Source of identity:** Inherits `run_id`.
- **Relation to Spine:** Each scoring call emits an `EvidenceReceipt`; LLM-as-judge runs are receipts too.
- **Storage proposal:** Reuse `experiments/petri_dish/` result models + `quality_gates.py`.
- **Non-goals:** No new scoring framework; cost-normalize existing 9-dim fitness.

### 3.7 LineageRecord
- **Existing owner:** `MerkleLog` / `EvolutionArchive` Merkle chain / `sakshi/provenance_log.py` (`merkle_log.py:18`; `archive.py:300`; `sakshi/provenance_log.py:74`).
- **Implementation rule:** Chain VEL records through the existing Merkle log; carry `parent_id`/`prev_hash`.
- **Forbidden duplicate:** Do not create a new lineage chain or a 6th provenance system.
- **Purpose:** Tamper-evident parent→child ancestry across bets, candidates, and runs.
- **Required fields:** `record_id`, `subject_id`, `parent_id`, `prev_hash`, `hash`, `created_at`.
- **Optional fields:** `kind` (bet|candidate|run|decision).
- **Source of identity:** `causation_id` / `parent_run_id` from `ExecutionIdentity`.
- **Relation to Spine:** Chains via `merkle_log.py` (already used by `archive.py`).
- **Storage proposal:** Reuse `merkle_log.py` / `sakshi/provenance_log.py`. No new chain.
- **Non-goals:** Not a new blockchain; it extends existing Merkle chaining.

### 3.8 DecisionRecord
- **Existing owner:** `decision_ontology.DecisionRecord` / `DecisionLog` (`decision_ontology.py:161-485`).
- **Implementation rule:** Link a decision to its spine receipt ids + evidence; extend if a field is missing.
- **Forbidden duplicate:** Do not create a second `DecisionRecord` class (there are already ≥7 decision objects).
- **Purpose:** The kill / hold / mutate / scale / archive verdict for a bet, with evidence links.
- **Required fields:** `decision_id`, `bet_id`, `verdict` (enum), `evidence_receipt_ids`, `rationale`, `decided_by` (human/agent), `decided_at`, `execution_identity`.
- **Optional fields:** `objections`, `reviewer_ids`, `budget_record_ref`.
- **Source of identity:** Spine identity; decision is itself a tollbooth-gated side effect.
- **Relation to Spine:** Reuses `decision_ontology.py` (typed decisions, evidence, objections, deterministic scoring).
- **Storage proposal:** Extend `decision_ontology.py`; receipt in `runtime_state`.
- **Non-goals:** No decision that promotes runtime behavior without human approval.

### 3.9 AgentContribution
- **Existing owner:** `evaluator.AgentScore` / receipt projections (`evaluator.py:252`; per-agent `EvidenceReceipt`s + `cost_tracker.CostEntry`).
- **Implementation rule:** Pure projection over per-agent `EvidenceReceipt`s + cost entries.
- **Forbidden duplicate:** Do not create a payment/credit object (reciprocity ledger integration deferred).
- **Purpose:** Attribute a result's credit/cost to individual agents in a SwarmRun.
- **Required fields:** `contribution_id`, `run_id`, `agent_id`, `tokens`, `cost_usd`, `receipt_ids`.
- **Optional fields:** `quality_delta`, `role`.
- **Source of identity:** `agent_id` + `run_id` from `ExecutionIdentity`.
- **Relation to Spine:** Pure projection over per-agent `EvidenceReceipt`s.
- **Storage proposal:** Projection only; no new persistence.
- **Non-goals:** Not a payment system; reciprocity ledger integration deferred.

### 3.10 WikiUpdate
- **Existing owner:** `MemoryKernelReviewedCanonicalReceipt` / memory promotion pipeline (`memory_kernel/promotion_gate.py:80`; `knowledge_ops/memory_promotion_*.py`).
- **Implementation rule:** A proven learning = a memory-kernel reviewed canonical receipt, gated on evidence completeness. Reuse the existing memory promotion gate.
- **Forbidden duplicate:** Do not create a new wiki/atom object.
- **Purpose:** The memory/wiki write that records a *proven* learning so it is reusable.
- **Required fields:** `update_id`, `decision_id`, `summary`, `evidence_receipt_ids`, `created_at`.
- **Optional fields:** `tags`, `supersedes`.
- **Source of identity:** Inherits `decision_id` lineage.
- **Relation to Spine:** Only written for decisions backed by complete receipt chains.
- **Storage proposal:** Existing memory kernel / wiki path; gated by evidence completeness.
- **Non-goals:** No write for unverified or held bets; proven-only.

### 3.11 Cost / Token Budget
- **Existing owner:** `cost_tracker.CostEntry` / `LLMUsageSpan` (measure) + `economic_spine.AgentBudget` (enforce) + `model_registry` (price) (`cost_tracker.py:59`; `llm_burn.py:39`; `economic_spine.py:74`).
- **Implementation rule:** Populate receipt cost/token at the provider boundary; bind `Experiment.budget` to `economic_spine`. Bridge, do not replace.
- **Forbidden duplicate:** Do not create a new cost source at the A2A layer.

### 3.12 Promotion Gate
- **Existing owner:** `spine/tollbooth.py` + `CanaryDecision` + `PromotionState`/`EvidenceTier` enums (`canary.py:23`; `execution_profile.py:13-23`).
- **Implementation rule:** Extend existing `require_execution_tollbooth` + canary/quality gates. Reuse the enums.
- **Forbidden duplicate:** Do not create a new promotion state machine.

---

## 4. Lifecycle

Two state machines. Both are **observed and recorded** by the loop, gated by the Spine.

**Idea / experiment lifecycle:**

```
raw_idea
  → candidate_bet
  → active_bet
  → experiment_designed
  → experiment_running
  → result_logged
  → decision_pending
  → killed / held / mutated / scaled / archived
```

**Swarm evolution lifecycle:**

```
proposed
  → shadow_running
  → evaluated
  → promotion_pending
  → promoted / rejected / archived
```

These map onto the existing `execution_profile.PromotionState` enum (`CANDIDATE → PROBE_PASS → LOCAL_PASS → COMPONENT_PASS → SYSTEM_PASS → PROMOTED`) and `EvidenceTier` (`UNVALIDATED → PROBE → LOCAL → COMPONENT → SYSTEM`). The Verified Loop **reuses** these enums rather than inventing parallel states.

---

## 5. Promotion Gate

A swarm mutation may be promoted to runtime-affecting status only when **all** of the following hold. The gate is enforced through `spine/tollbooth.py::require_execution_tollbooth` (fail-closed) plus existing `quality_gates.py` / `canary.py`.

- [ ] All existing tests pass (no regression vs. recorded baseline).
- [ ] Held-out evals pass (eval set the candidate never trained/tuned on).
- [ ] Equal or explicitly-reported token/cost budget vs. baseline.
- [ ] Cost-normalized score must improve, or the regression must be explicitly justified.
- [ ] Unsupported-claim rate must not increase.
- [ ] Trace logs complete (every step has an `EvidenceReceipt`; no gaps in the run ledger).
- [ ] `EvidenceReceipt`s link claims ↔ results ↔ decisions (via `attributes` cross-refs).
- [ ] Losing candidates are still archived (MAP-Elites archive in `archive.py`).
- [ ] **Human approval required before any runtime-changing promotion.**

---

## 6. Held-Out Eval Strategy

Open question: human-curated vs. system-generated vs. hybrid.

**Recommended starting position: human-seeded, system-expanded, human-approved.**

- Humans seed an initial held-out set (anchored on `experiments/petri_dish/` ground-truth snippets and `benchmarks/gauntlet.py` tiers).
- The system proposes expansions (new tasks, perturbations) but they enter the held-out set only after human approval.
- The held-out set is versioned and its hash recorded in each `BenchmarkResult` so "held-out" is provable, not asserted.
- A candidate that has ever seen a held-out item is disqualified for that item.

### 6a. Content Sealing Policy

**Held-out eval payloads and exact expected answers must not live in agent-readable repo paths.** The embedded petri-dish answer key (`experiments/petri_dish/dataset.py`) is disqualified as "held-out" because agents being evaluated can read its full content.

Required separation:

| Category | May live in repo | Must remain sealed/private |
|---|---|---|
| Task IDs, metadata, schemas | Yes | — |
| Rubrics, expected artifact types | Yes | — |
| Full task payloads | — | Yes (outside repo or agent-inaccessible store) |
| Exact expected answers / answer keys | — | Yes |
| Development/training evals | Yes (agents may see these) | — |
| Promotion-gate held-out evals | — | Yes (sealed, versioned, hashed) |

- Results can be logged back into repo after evaluation, but future task payloads remain sealed.
- The hash of the sealed set is recorded on each `BenchmarkResult` so provenance is verifiable.
- Development agents may see training/dev evals. Promotion candidates are evaluated against sealed held-out tasks only.

---

## 7. Budget Source of Truth

Open question: estimated cost vs. actual billing vs. hybrid.

**Recommended starting position: hybrid.**

- Use **estimated cost** for local/dev comparisons (deterministic, fast).
- Use **actual billing** where available (provider usage APIs).
- **Always log** model, token count, latency, tool calls, and cost estimate on every `EvidenceReceipt` (fields already exist: `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`).
- **Never** claim an equal-budget improvement without an explicit budget record (`Experiment.budget` + the run's receipt totals). No budget record → no equal-budget claim.

---

## 8. Promotion Authority

Open question: automated vs. human-gated.

**Recommended starting position:**

- **Shadow-mode automatic evaluation** is allowed (no runtime effect).
- **Human-gated promotion** for any runtime behavior change.
- **Automatic archival** is always allowed (losing candidates → archive).
- **Automatic docs/report generation** is allowed.
- **No autonomous production modification.** The promotion tollbooth fails closed without a recorded human approval.

---

## 9. Relationship to Existing Systems

The Verified Loop is an **integration layer over assets that already exist** — it should add orchestration and evidence-linking, not new engines.

| Existing asset | Exact path | Role in Verified Loop |
|---|---|---|
| DarwinEngine / DGM loop | `dharma_swarm/dgm_loop.py`, `dharma_swarm/evolution.py` | Produces EvolutionCandidates |
| 9-dimensional fitness scoring | `dharma_swarm/archive.py` (`FITNESS_DIMENSIONS`, `FitnessScore`) | Scores BenchmarkResults |
| MAP-Elites archive | `dharma_swarm/archive.py` (`EvolutionArchive`) | Stores winners + losers |
| Merkle-chained history | `dharma_swarm/merkle_log.py`, `dharma_swarm/sakshi/provenance_log.py` | Backs LineageRecord |
| Cost/token tracker | `dharma_swarm/spine/receipt.py` (`input_tokens`/`output_tokens`/`cost_usd`); `auto_grade/efficiency.py` | Equal-budget comparison |
| Trace store | `dharma_swarm/trace_attractor/`, `runtime_state` run ledger | SwarmRun provenance |
| LLM-as-judge gates | `dharma_swarm/quality_gates.py`, `dharma_swarm/thinkodynamic_scorer.py` | Scoring + gate checks |
| Canary deployment | `dharma_swarm/canary.py` (`CanaryDecision`: PROMOTE/ROLLBACK/DEFER) | Promotion gate execution |
| SelfResearcher hypothesis pipeline | `dharma_swarm/self_research.py` (`Hypothesis`, `RESEARCH_QUESTIONS`) | Generates candidate bets |
| Experiment records | `dharma_swarm/experiment_log.py` (`ExperimentRecord`) | Experiment persistence |
| Decision ontology | `dharma_swarm/decision_ontology.py` | DecisionRecord backing |
| Petri dish harness | `experiments/petri_dish/` | Ground-truth eval substrate |
| Spine identity / receipts / tollbooth | `dharma_swarm/spine/{identity,receipt,tollbooth}.py` | Identity, evidence, gating |

---

## 9a. Recursive Discovery Reconciliation

`recursive_discovery.py` should be graduated/extended into the VEL path, not deprecated or ignored. Its receipt taxonomy and recorder pattern are prior art. The VEL should join it to Spine identity and reuse its shadow-mode discipline.

**Key findings:**
- `recursive_discovery.py` is **not orphaned shadow code** — it is a registered surface, wired through `evaluation_registry.record_recursive_discovery_receipt()` and observed in `operator_core/control_surface.py`.
- It already carries content-hash integrity, `parent_id`/`candidate_id` lineage, `cost_usd`, witness verdicts, and rollback pointers.
- Its receipt lifecycle (limitation → eval → candidate → experiment → witness → promotion) is the closest existing expression of the VEL lifecycle.

| recursive_discovery concept | VEL equivalent | Reuse / bridge / deprecate | Reason |
|---|---|---|---|
| `LimitationReceipt` | Bet rationale / problem statement (pre-BetCard) | Reuse | Already the "why we're spending budget" record |
| `GeneratedEvalReceipt` | Held-out / generated eval registration | Reuse + bridge | Maps to BenchmarkResult eval refs; bind to sealed-set hash |
| `CandidateDiffReceipt` | EvolutionCandidate (proposed mutation) | Bridge to `ArchiveEntry` | Candidate truth lives in `EvolutionArchive`; receipt references it |
| `ExperimentResultReceipt` | Experiment run outcome | Bridge to `ExperimentRecord` | Experiment persistence is `experiment_log` |
| `WitnessVerdictReceipt` | Gate / witness verdict | Reuse | Already models phased witness verdicts |
| `PromotionDecisionReceipt` | DecisionRecord | Bridge to `decision_ontology` | Decision truth lives in `decision_ontology`; receipt references it |
| `RecursiveReceipt.content_hash()` | LineageRecord hashing | Reuse / bridge to `merkle_log` | Avoid a second hashing scheme; chain via existing Merkle log |
| `RecursiveDiscoveryRecorder` (EventLog) | VEL recorder | Reuse + join to spine identity | Keep the recorder; add `ExecutionIdentity`/spine receipt linkage |

**When graduated:** each step must carry/reference a spine `ExecutionIdentity`/`EvidenceReceipt` so the chain joins the one correlation spine. Do not let it persist receipts to its own store *and* the VEL persist to another.

---

## 10. What Not To Build Yet

Explicitly deferred (out of scope for this RFC and for the parallel Spine-completion lane):

- Spark Ingestor expansion.
- Semantic Ontology refactor.
- Production Verified Loop runtime.
- Dashboard UI.
- Autonomous repo mutation.
- Automatic promotion.
- New model-routing system.
- Migrations / new dependencies / module renames.

---

## 11. Minimum Viable Integration (Later)

The smallest future implementation, **only after the Spine reaches its Definition of Done**:

```
Spark Ingestor produces BetCards
  → Spine assigns identity and evidence/provenance
  → Verified Loop evaluates BetCards (held-out eval, equal budget)
  → DarwinEngine archives candidates (winners and losers)
  → Runtime runs in shadow mode (no production effect)
  → Ontology stores only proven-useful objects
```

Each arrow is one `EvidenceReceipt`; the whole chain shares one `correlation_id`. This is additive and reversible: it reads existing assets, writes only new append-only records and shadow runs, and requires human approval before any runtime change.

---

## 12. Open Questions (with recommended defaults)

| # | Open question | Recommended default |
|---|---|---|
| 1 | Held-out eval curation | Human-seeded, system-expanded, human-approved (§6) |
| 2 | Budget source of truth | Hybrid: estimate for dev, billing where available, always log usage (§7) |
| 3 | Promotion authority | Shadow auto-eval; human-gated runtime promotion; auto-archive only (§8) |
| 4 | Where do BetCards persist? | Extend `Hypothesis` in existing experiment store; on paths that already persist a `RuntimeReceipt` (A2A via `A2AServer.submit()`), associate the `EvidenceReceipt` to that existing receipt and optionally project into `delegation_runs.receipt_json` — do not mint a second `RuntimeReceipt` (§3.3a) |
| 5 | Is EvolutionCandidate identity `proposal_id` or `run_id`? | `proposal_id` for the mutation; `run_id` for each shadow evaluation run |
| 6 | Does the loop own its own store? | No — reuse `archive.py`, `experiment_log.py`, `decision_ontology.py`, `merkle_log.py` |
| 7 | When can the loop start? | Only after Spine DoD: legacy bypass closed, adoption ≥ floor, mapping receipts landed |

---

*This RFC introduces no runtime code, no migrations, no dependencies, and no module renames. It is a reversible design artifact. The Runtime Truth Spine remains the substrate; the Verified Experiment Loop is the selection/evidence layer that consumes it.*
