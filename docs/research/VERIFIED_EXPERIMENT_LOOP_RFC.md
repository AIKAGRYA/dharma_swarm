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
- **Purpose:** A single falsifiable claim the swarm is willing to spend budget testing.
- **Required fields:** `bet_id` (← `ExecutionIdentity.task_id`), `claim` (str), `source_ref` (raw source/issue/idea), `hypothesis`, `success_criteria`, `kill_criteria`, `created_at`, `execution_identity`.
- **Optional fields:** `parent_bet_id`, `tags`, `priority_score`, `estimated_cost_usd`.
- **Source of identity:** Spine `ExecutionIdentity.new(task_id=...)`.
- **Relation to Spine:** Identity + an `EvidenceReceipt` on creation (`operation="bet_open"`).
- **Storage proposal:** New append-only `bets.jsonl` under the experiment store; row keyed by `bet_id`; receipt in `runtime_state`.
- **Non-goals:** Not a roadmap item; not a feature flag; no auto-execution on creation.

### 3.2 Experiment
- **Purpose:** The designed procedure that tests a BetCard at a declared budget.
- **Required fields:** `experiment_id`, `bet_id`, `design` (tasks/eval set ref), `budget` (model, max tokens, max tool calls, cost ceiling), `held_out_eval_ref`, `execution_identity`.
- **Optional fields:** `baseline_ref`, `shadow_only` (bool), `seed`.
- **Source of identity:** Child `ExecutionIdentity` via `with_updates(parent_run_id=bet.run_id)`.
- **Relation to Spine:** Each run emits `EvidenceReceipt`s carrying tokens/cost.
- **Storage proposal:** Extends `experiment_log.py::ExperimentRecord` (already has `proposal_id`, `evidence_tier`, `promotion_state`) rather than a new table.
- **Non-goals:** No new benchmark runtime; reuse `experiments/petri_dish/` and `benchmarks/gauntlet.py`.

### 3.3 EvidenceReceipt usage
- **Purpose:** The canonical proof artifact for every step (claim extraction, each experiment run, decision).
- **Required fields:** existing `EvidenceReceipt` fields — `trace_id`, `task_id`, `status`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `attributes`.
- **Source of identity:** `ExecutionIdentity.trace_id` (= `correlation_id` cross-layer alias).
- **Relation to Spine:** This **is** the spine object; the loop only consumes it. Use `attributes["dharma.attr.bet_id"]`, `"...experiment_id"`, `"...decision_id"` to link.
- **Storage proposal:** Persisted by `spine/persistence.py` to the `runtime_state` ledger. No change.
- **Non-goals:** Do not subclass or fork `EvidenceReceipt`; link via `attributes`.

### 3.4 SwarmRun
- **Purpose:** One full execution of the swarm against an experiment (the unit fitness is measured on).
- **Required fields:** `run_id` (← `ExecutionIdentity.run_id`), `experiment_id`, `agent_set`, `start/finish`, `aggregate_cost`, `receipt_ids` (list), `execution_identity`.
- **Optional fields:** `parent_run_id`, `canary` (bool).
- **Source of identity:** Spine `run_id`; the existing FK owner for runtime runs.
- **Relation to Spine:** Aggregates child `EvidenceReceipt`s for equal-budget comparison.
- **Storage proposal:** Projection over `runtime_state` run ledger (`get_run_ledger`); no new persistence.
- **Non-goals:** Not a new orchestrator; it observes runs, it does not drive them.

### 3.5 EvolutionCandidate
- **Purpose:** A proposed swarm mutation under evaluation (prompt, router weight, agent config).
- **Required fields:** `candidate_id`, `bet_id`, `mutation_spec`, `parent_id`, `fitness` (`archive.py::FitnessScore`), `promotion_state` (`execution_profile.PromotionState`), `evidence_tier`.
- **Optional fields:** `map_elites_cell`, `shadow_result_ref`.
- **Source of identity:** Spine identity via `proposal_id` field already on `ExecutionIdentity`.
- **Relation to Spine:** Reuses self-modification receipt chain (proposal→gate→apply→verify→promote/revert).
- **Storage proposal:** Existing `archive.py` EvolutionArchive (MAP-Elites + MerkleLog). No new store.
- **Non-goals:** No autonomous apply; candidates stay in shadow until the promotion gate.

### 3.6 BenchmarkResult
- **Purpose:** Scored, ground-truth-comparable output of a SwarmRun on the held-out eval.
- **Required fields:** `result_id`, `run_id`, `experiment_id`, `scores` (per-dimension), `cost_normalized_score`, `unsupported_claim_rate`, `receipt_ids`.
- **Optional fields:** `judge_model`, `raw_traces_ref`.
- **Source of identity:** Inherits `run_id`.
- **Relation to Spine:** Each scoring call emits an `EvidenceReceipt`; LLM-as-judge runs are receipts too.
- **Storage proposal:** Reuse `experiments/petri_dish/` result models + `quality_gates.py`.
- **Non-goals:** No new scoring framework; cost-normalize existing 9-dim fitness.

### 3.7 LineageRecord
- **Purpose:** Tamper-evident parent→child ancestry across bets, candidates, and runs.
- **Required fields:** `record_id`, `subject_id`, `parent_id`, `prev_hash`, `hash`, `created_at`.
- **Optional fields:** `kind` (bet|candidate|run|decision).
- **Source of identity:** `causation_id` / `parent_run_id` from `ExecutionIdentity`.
- **Relation to Spine:** Chains via `merkle_log.py` (already used by `archive.py`).
- **Storage proposal:** Reuse `merkle_log.py` / `sakshi/provenance_log.py`. No new chain.
- **Non-goals:** Not a new blockchain; it extends existing Merkle chaining.

### 3.8 DecisionRecord
- **Purpose:** The kill / hold / mutate / scale / archive verdict for a bet, with evidence links.
- **Required fields:** `decision_id`, `bet_id`, `verdict` (enum), `evidence_receipt_ids`, `rationale`, `decided_by` (human/agent), `decided_at`, `execution_identity`.
- **Optional fields:** `objections`, `reviewer_ids`, `budget_record_ref`.
- **Source of identity:** Spine identity; decision is itself a tollbooth-gated side effect.
- **Relation to Spine:** Reuses `decision_ontology.py` (typed decisions, evidence, objections, deterministic scoring).
- **Storage proposal:** Extend `decision_ontology.py`; receipt in `runtime_state`.
- **Non-goals:** No decision that promotes runtime behavior without human approval.

### 3.9 AgentContribution
- **Purpose:** Attribute a result's credit/cost to individual agents in a SwarmRun.
- **Required fields:** `contribution_id`, `run_id`, `agent_id`, `tokens`, `cost_usd`, `receipt_ids`.
- **Optional fields:** `quality_delta`, `role`.
- **Source of identity:** `agent_id` + `run_id` from `ExecutionIdentity`.
- **Relation to Spine:** Pure projection over per-agent `EvidenceReceipt`s.
- **Storage proposal:** Projection only; no new persistence.
- **Non-goals:** Not a payment system; reciprocity ledger integration deferred.

### 3.10 WikiUpdate
- **Purpose:** The memory/wiki write that records a *proven* learning so it is reusable.
- **Required fields:** `update_id`, `decision_id`, `summary`, `evidence_receipt_ids`, `created_at`.
- **Optional fields:** `tags`, `supersedes`.
- **Source of identity:** Inherits `decision_id` lineage.
- **Relation to Spine:** Only written for decisions backed by complete receipt chains.
- **Storage proposal:** Existing memory kernel / wiki path; gated by evidence completeness.
- **Non-goals:** No write for unverified or held bets; proven-only.

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
| 4 | Where do BetCards persist? | New append-only `bets.jsonl` keyed by `ExecutionIdentity.task_id`; receipts in `runtime_state` |
| 5 | Is EvolutionCandidate identity `proposal_id` or `run_id`? | `proposal_id` for the mutation; `run_id` for each shadow evaluation run |
| 6 | Does the loop own its own store? | No — reuse `archive.py`, `experiment_log.py`, `decision_ontology.py`, `merkle_log.py` |
| 7 | When can the loop start? | Only after Spine DoD: legacy bypass closed, adoption ≥ floor, mapping receipts landed |

---

*This RFC introduces no runtime code, no migrations, no dependencies, and no module renames. It is a reversible design artifact. The Runtime Truth Spine remains the substrate; the Verified Experiment Loop is the selection/evidence layer that consumes it.*
