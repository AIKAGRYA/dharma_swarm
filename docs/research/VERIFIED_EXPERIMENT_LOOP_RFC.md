# RFC: Verified Experiment Loop

**Date:** 2026-06-04
**Author:** Devin (assessment session), commissioned by @AmitabhainArunachala
**Status:** DRAFT — proposal-level only, no runtime authority
**Doc type:** `experiment` — explicitly bounded exploration with no runtime authority
**Subordinate to:** `docs/governance/CANONICAL_DOC_STACK.md` (authority), `CLAUDE.md` (behavior)
**Replaces:** Nothing. New RFC. Draws on prior research at:
- `docs/research/DARWIN_ENGINE_PERPETUAL_EVOLUTION_RESEARCH.md`
- `docs/research/VERIFICATION_RESEARCH_SUMMARY.md`
- `docs/research/FORMAL_VERIFICATION_PRODUCTION_RESEARCH.md`

---

## 1. Thesis

The Verified Experiment Loop exists to make swarm improvement verifiable rather than vibes-based.

**Problem:** Dharma Swarm has ~80% of the ingredients for self-evolution (DarwinEngine, fitness scoring, quality gates, canary deployment, experiment log, trace store, cost tracker), but no mechanism to **prove** that a proposed change actually improves the system under equal conditions. Changes can be proposed, evaluated, and archived — but there is no controlled comparison against a baseline with cost/token accounting.

**Core loop:**

```
Raw source / idea / repo issue
→ claim extraction
→ BetCard (hypothesis with falsifiable prediction)
→ experiment design (baseline + candidate on held-out tasks)
→ execution-grounded result (receipts, traces, fitness scores)
→ decision: kill / hold / mutate / scale / archive
→ wiki/memory update (proven insights only)
→ routing/evolution update (promoted or archived)
```

**Invariant:** No swarm improvement claim is valid unless compared to best single-agent and prior-swarm baselines under equal or explicitly reported token/cost budgets.

---

## 2. Why Spine Comes First

The Verified Experiment Loop depends on Runtime Truth Spine primitives. Every element of the loop requires grounded identity and provenance:

| Loop element | Spine dependency | Why |
|---|---|---|
| **BetCard identity** | `ExecutionIdentity.proposal_id` | Every BetCard is a proposal. The spine already carries `proposal_id` through all carrier surfaces (adapters.py line 111-114). BetCard identity inherits from spine identity — no new identity system needed. |
| **Experiment evidence** | `EvidenceReceipt` | Every dispatch within an experiment must produce a receipt. The receipt carries `task_id`, `trace_id`, `agent_id`, `provider`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `status`, `error_source`. This IS the experiment evidence — not a separate log. |
| **SwarmRun provenance** | `trace_id` / `correlation_id` cross-layer continuity | A SwarmRun spans multiple dispatches. The spine's correlation identity links all receipts within one run. `CorrelationContext` (contextvars) already bridges TelicSeam proposal_id chain and RuntimeEnvelope event_id/trace_id. |
| **Equal-budget comparison** | `EvidenceReceipt.input_tokens`, `.output_tokens`, `.cost_usd` | Budget accounting comes from receipt fields, not a separate cost tracker. `cost_tracker.py` can aggregate from receipts post-hoc. Without receipts on every dispatch, cost comparison is estimated, not proven. |
| **Tamper-evident audit** | `MerkleLog` (203 lines, existing) + receipt persistence | Receipt chain provides audit trail. `persistence.py` already writes receipts to `delegation_runs`. Merkle chaining receipts (future, P2) provides tamper-evidence. |
| **Promotion gate control** | `require_execution_tollbooth()` | The tollbooth pattern — "validate identity and runtime_state before side effects" — is exactly the pattern for a promotion gate. Promotion is a side effect that requires identity + evidence. |

**Consequence:** If the spine adoption track is incomplete (god objects still dispatching without `invoke_agent()`), then experiments running through those dispatch paths produce incomplete evidence. The experiment runner must only count dispatches that produce `EvidenceReceipt`s. This is why spine completion is P0.

---

## 3. Proposed Core Objects

### 3.1 BetCard

**Purpose:** A falsifiable hypothesis about a swarm improvement. Links an idea to a testable prediction.

```python
@dataclass
class BetCard:
    # Identity (from spine)
    bet_id: str                      # unique identifier
    proposal_id: str                 # spine ExecutionIdentity.proposal_id
    trace_id: str                    # spine trace

    # Hypothesis
    title: str                       # "Heterogeneous 3-agent swarm beats single claude-sonnet on GAIA tasks"
    claim: str                       # falsifiable statement
    predicted_outcome: str           # what we expect to see
    null_hypothesis: str             # what the default/no-change outcome looks like
    source: str                      # where the idea came from (issue URL, research doc, SelfResearcher)

    # Scope
    component: str                   # which part of the system is changed
    change_type: str                 # "prompt" | "routing" | "topology" | "agent_role" | "model" | "parameter"
    affected_surfaces: list[str]     # which modules/files are touched

    # Budget
    max_token_budget: int | None     # hard cap on tokens for experiment
    max_cost_usd: float | None       # hard cap on cost
    budget_source: str               # "estimated" | "actual" | "hybrid"

    # Lifecycle
    status: str                      # raw_idea → candidate → active → experiment_designed → ...
    created_at: datetime
    updated_at: datetime
    created_by: str                  # agent_id or human author
    decision: str | None             # kill | hold | mutate | scale | archive
    decision_reason: str | None
    decision_by: str | None          # agent_id or human

    # Lineage
    parent_bet_id: str | None        # if this mutated from a prior bet
    experiment_ids: list[str]        # experiments that tested this bet
    evidence_receipt_ids: list[str]  # spine receipts linked to this bet
```

**Source of identity:** `ExecutionIdentity.proposal_id` via spine adapters (surface="proposal").
**Relation to spine:** BetCard carries `proposal_id` from `ExecutionIdentity`. Every dispatch within a BetCard experiment produces an `EvidenceReceipt` with that `proposal_id` in the correlation chain.
**Storage location proposal:** `~/.dharma/evolution/bet_cards.jsonl` (append-only, consistent with `experiments.jsonl` convention).
**Non-goals:** BetCard does not execute anything. It is a hypothesis record only.

**Existing code that could produce BetCards:**
- `SelfResearcher.generate_hypotheses()` in `self_research.py` — already generates `Hypothesis` objects with `question`, `rationale`, `expected_winner`. Could be adapted to emit BetCards.
- `DarwinEngine` Proposal dataclass in `evolution.py` — carries `component`, `change_type`, `description`, `predicted_fitness`.

**Existing code that could consume BetCards:**
- `ExperimentLog.append()` in `experiment_log.py` — already appends ExperimentRecords. BetCard.bet_id would become ExperimentRecord.proposal_id.
- `ClaimGraph` in `claim_graph.py` — BetCard claims can be registered as nodes in the claim graph.

### 3.2 Experiment

**Purpose:** A controlled comparison between baseline and candidate on held-out tasks under budget constraints.

```python
@dataclass
class Experiment:
    experiment_id: str
    bet_id: str                      # which BetCard this tests
    trace_id: str                    # spine trace

    # Design
    baseline_config: dict            # model, topology, prompt version, agent roles
    candidate_config: dict           # the proposed change
    held_out_task_ids: list[str]     # which tasks to run
    methodology: str                 # "A/B" | "crossover" | "shadow"
    sample_size: int                 # how many tasks per arm

    # Budget
    budget_per_arm_tokens: int | None
    budget_per_arm_usd: float | None
    budget_source: str               # "estimated" | "actual" | "hybrid"

    # Execution
    status: str                      # designed → running → completed → analyzed
    baseline_run_id: str | None      # SwarmRun for baseline
    candidate_run_id: str | None     # SwarmRun for candidate
    started_at: datetime | None
    completed_at: datetime | None

    # Results
    baseline_result: "BenchmarkResult | None"
    candidate_result: "BenchmarkResult | None"
    delta: float | None              # candidate - baseline (cost-normalized)
    confidence: float | None         # statistical confidence
    outcome: str | None              # "candidate_wins" | "baseline_wins" | "inconclusive"
```

**Source of identity:** `ExecutionIdentity` via spine.
**Relation to spine:** Each arm of the experiment is a SwarmRun. Each SwarmRun produces EvidenceReceipts on every dispatch. Experiment aggregates receipts across both arms.
**Storage location proposal:** `~/.dharma/evolution/experiments.jsonl` (extend existing `ExperimentLog`).
**Non-goals:** The Experiment object doesn't execute tasks. It orchestrates two SwarmRuns and compares results.

**Existing code:**
- `ExperimentRecord` in `experiment_log.py` — already has `proposal_id`, `execution_profile`, `pass_rate`, `weighted_fitness`, `tokens_used`, `fitness`. Missing: `baseline_config`, `budget_per_arm`, `delta`, `confidence`.
- `PetriDishHarness` in `experiments/petri_dish/harness.py` — working prototype of baseline → mutation → evaluation cycle. Toy task, but the pattern is right.

### 3.3 EvidenceReceipt Usage

**Purpose:** Spine `EvidenceReceipt` is the experiment evidence. No new receipt type needed.

```python
# Already exists at dharma_swarm/spine/receipt.py
# Key fields for experiment verification:
EvidenceReceipt.trace_id          # links to SwarmRun
EvidenceReceipt.task_id           # links to held-out task
EvidenceReceipt.agent_id          # which agent executed
EvidenceReceipt.provider          # which provider
EvidenceReceipt.model             # which model
EvidenceReceipt.input_tokens      # token count
EvidenceReceipt.output_tokens     # token count
EvidenceReceipt.cost_usd          # cost
EvidenceReceipt.latency_ms        # latency
EvidenceReceipt.status            # ok | failed | dropped | timeout | cancelled
EvidenceReceipt.routing_decision_id  # links to RoutingDecision
```

**Relation to spine:** This IS the spine. No extension needed.
**Non-goals:** No new receipt schema. Do not create a parallel evidence surface.

### 3.4 SwarmRun

**Purpose:** One complete execution of a configuration (baseline or candidate) across held-out tasks.

```python
@dataclass
class SwarmRun:
    run_id: str
    experiment_id: str
    trace_id: str                    # spine correlation
    config: dict                     # model, topology, prompt version, agent roles

    # Execution
    task_ids: list[str]              # held-out tasks executed
    receipt_ids: list[str]           # EvidenceReceipt IDs produced
    status: str                      # pending → running → completed → failed

    # Aggregated metrics
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    total_latency_ms: int
    pass_rate: float
    weighted_fitness: float          # from FitnessScore (9-dimensional)
    fitness_breakdown: dict          # per-dimension scores

    started_at: datetime
    completed_at: datetime | None
```

**Source of identity:** `ExecutionIdentity.run_id` from spine. All receipts in the run share the same `trace_id`.
**Relation to spine:** SwarmRun IS a set of EvidenceReceipts grouped by `trace_id`.
**Storage location proposal:** `~/.dharma/evolution/swarm_runs.jsonl`.
**Non-goals:** SwarmRun doesn't orchestrate execution. It records what happened.

**Existing code:** `correlation_context.py` already carries `trace_id` and `session_id` via contextvars. A SwarmRun would use this to collect all receipts within one experiment arm.

### 3.5 EvolutionCandidate

**Purpose:** A configuration variant being tested for promotion.

```python
@dataclass
class EvolutionCandidate:
    candidate_id: str
    bet_id: str
    config: dict                     # the proposed configuration
    parent_candidate_id: str | None  # if mutated from prior candidate
    generation: int                  # evolution generation number

    # Evaluation
    fitness: "FitnessScore | None"   # 9-dimensional fitness
    behavior_descriptor: list[float] # MAP-Elites grid coordinates
    cell_id: str | None              # diversity_archive cell

    # Status
    status: str                      # proposed → shadow → evaluated → promoted | rejected | archived
    swarm_run_ids: list[str]
    evidence_tier: str               # UNVALIDATED → PROBE → LOCAL → COMPONENT → SYSTEM
    promotion_state: str             # CANDIDATE → PROBE_PASS → LOCAL_PASS → ... → PROMOTED
```

**Source of identity:** `ExecutionIdentity.proposal_id`.
**Relation to spine:** Each candidate evaluation produces a SwarmRun with spine receipts.
**Storage location proposal:** `~/.dharma/evolution/archive.jsonl` (extend existing `EvolutionArchive`).
**Non-goals:** Does not replace `Proposal` in `evolution.py`. Wraps it with verification metadata.

**Existing code:**
- `Proposal` in `evolution.py` — carries `component`, `change_type`, `description`, `predicted_fitness`, `actual_fitness`, `gate_decision`.
- `ArchiveEntry` in `archive.py` — carries `fitness: FitnessScore`, `diff`, `lineage`, `parent_id`. Merkle-chained.
- `ArchiveCell` in `diversity_archive.py` — MAP-Elites cell with `behavior_descriptor`, `fitness`, `candidate`.

### 3.6 BenchmarkResult

**Purpose:** Structured result of one configuration on one held-out task.

```python
@dataclass
class BenchmarkResult:
    result_id: str
    task_id: str                     # held-out task
    run_id: str                      # SwarmRun
    experiment_id: str

    # Outcome
    passed: bool
    score: float                     # 0.0 - 1.0
    fitness: "FitnessScore | None"   # 9-dimensional

    # Cost
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int

    # Evidence
    receipt_ids: list[str]           # EvidenceReceipts for this task
    trace_id: str

    # Quality
    quality_verdict: str | None      # from quality_gates.py
    unsupported_claims: int          # from claim_graph.py
```

**Source of identity:** Derived from `EvidenceReceipt.task_id`.
**Relation to spine:** Aggregation of receipts per task within a SwarmRun.
**Storage location proposal:** `~/.dharma/evals/benchmark_results.jsonl` (consistent with `benchmark_registry.py`).

**Existing code:**
- `benchmark_registry.py` — `BenchmarkEntry` with `name`, `baseline`, `threshold`, `current`. Missing: per-task granularity.
- `GradeCard` in `auto_grade/models.py` — per-task quality grades.
- `gauntlet.py` — 5-tier pressure testing with per-task scores.

### 3.7 LineageRecord

**Purpose:** Parent-child relationship between evolution candidates and experiments.

```python
@dataclass
class LineageRecord:
    lineage_id: str
    parent_id: str                   # BetCard, EvolutionCandidate, or Experiment
    child_id: str
    relationship: str                # "bet_spawned_experiment" | "experiment_spawned_candidate" |
                                     # "candidate_mutated_to" | "candidate_merged_with"
    created_at: datetime
    metadata: dict
```

**Source of identity:** Spine `causation_id` and `parent_run_id`.
**Relation to spine:** `ExecutionIdentity` already carries `causation_id` and `parent_run_id`.
**Storage location proposal:** Extend `LineageGraph` in `lineage.py` (already used by `telic_seam.py`).

**Existing code:**
- `LineageEdge` / `LineageGraph` in `lineage.py` — already models parent-child relationships.
- `ArchiveEntry` in `archive.py` — carries `parent_id` for Merkle-chained lineage.

### 3.8 DecisionRecord

**Purpose:** Record of a kill / hold / mutate / scale / archive decision on a BetCard or EvolutionCandidate.

```python
@dataclass
class DecisionRecord:
    decision_id: str
    target_id: str                   # BetCard or EvolutionCandidate ID
    target_type: str                 # "bet_card" | "evolution_candidate"
    decision: str                    # "kill" | "hold" | "mutate" | "scale" | "archive"
    reason: str
    evidence_summary: str            # what the experiment showed
    decided_by: str                  # agent_id or "human:username"
    decided_at: datetime
    confidence: float                # 0.0 - 1.0
    human_approved: bool             # required for promotion
    promotion_gate_results: dict     # which gates passed/failed
```

**Source of identity:** Spine trace.
**Relation to spine:** The decision is a side effect — tollbooth applies.
**Storage location proposal:** `~/.dharma/evolution/decisions.jsonl`.

**Existing code:**
- `CanaryDecision` in `canary.py` — PROMOTE / ROLLBACK / DEFER based on fitness comparison.
- `MemoryKernelPromotionDecisionKind` in `memory_kernel/promotion_gate.py` — APPROVE / REJECT with 6 required gates.

### 3.9 AgentContribution

**Purpose:** Per-agent accounting within a SwarmRun.

```python
@dataclass
class AgentContribution:
    agent_id: str
    run_id: str
    tasks_handled: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    pass_rate: float
    quality_scores: dict             # per-dimension from GradeCard
    receipt_ids: list[str]
```

**Source of identity:** Aggregation of `EvidenceReceipt.agent_id` within a run.
**Storage location proposal:** Computed, not stored. Derived from receipts.

### 3.10 WikiUpdate

**Purpose:** Record of a wiki/memory update triggered by a verified experiment result.

```python
@dataclass
class WikiUpdate:
    update_id: str
    experiment_id: str
    decision_id: str                 # the decision that triggered this update

    # What changed
    update_type: str                 # "new_atom" | "revised_atom" | "deprecated_atom" | "new_link"
    atom_ids: list[str]              # wiki atoms affected
    summary: str                     # what was learned

    # Provenance
    evidence_receipt_ids: list[str]  # spine receipts backing this update
    bet_id: str
    trace_id: str

    # Governance
    human_approved: bool
    promotion_gate: str              # which gate authorized the update
```

**Source of identity:** Spine trace, linked to decision.
**Relation to spine:** Wiki updates are side effects — tollbooth applies. Memory kernel promotion gates (6 required: human_review, provenance_review, conflict_review, privacy_review, canon_policy_review, knowledgeops_linking) already enforce governance.
**Storage location proposal:** `reports/memory_kernel/reviewed_canonical_receipts.jsonl` (already exists as the memory kernel output).

**Existing code:**
- `MemoryKernelPromotionGate` in `memory_kernel/promotion_gate.py` — full human-gated promotion with 6 required gates. `REVIEWED_CANONICAL_RECEIPT_SCHEMA_VERSION = "memory_kernel_reviewed_canonical_receipt.v1"`.
- `wiki_atom_schema.md` in `docs/loomwork/` — Karpathy-style atoms with provenance fields.

---

## 4. Lifecycle

### 4.1 Idea / Experiment Lifecycle

```
raw_idea
  ↓ claim extraction (manual or SelfResearcher)
candidate_bet
  ↓ human or automated review → BetCard created
active_bet
  ↓ experiment designed (baseline + candidate + held-out tasks + budget)
experiment_designed
  ↓ execution starts (SwarmRun per arm)
experiment_running
  ↓ execution complete, receipts collected
result_logged
  ↓ analysis: delta, confidence, cost comparison
decision_pending
  ↓ gate checks (see §5)
killed        → BetCard archived with reason, receipts preserved
held          → BetCard stays active, awaiting more evidence or conditions
mutated       → new BetCard created with parent_bet_id = this BetCard
scaled        → candidate promoted to production (human-approved)
archived      → BetCard + all evidence archived, searchable
```

**Mapping to current repo:**
- `raw_idea` → `SelfResearcher.generate_hypotheses()` or manual issue
- `candidate_bet` → extend `Proposal` status or new BetCard object
- `active_bet` → `EvolutionStatus.PENDING` in `evolution.py`
- `experiment_designed` → `ExecutionProfile` in `execution_profile.py` + Experiment object
- `experiment_running` → `EvolutionStatus.TESTING` + SwarmRun
- `result_logged` → `ExperimentLog.append()` + `ExperimentRecord`
- `decision_pending` → `EvolutionStatus.EVALUATED`
- `killed/archived` → `EvolutionStatus.REJECTED` / `ARCHIVED`

### 4.2 Swarm Evolution Candidate Lifecycle

```
proposed
  ↓ EvolutionCandidate created from BetCard
shadow_running
  ↓ candidate runs in shadow mode (no production impact)
  ↓ canary comparison against baseline
evaluated
  ↓ fitness scored (9-dimensional), cost measured
promotion_pending
  ↓ promotion gate checks (see §5)
promoted     → candidate config becomes production config
rejected     → candidate archived with evidence, fitness preserved
archived     → candidate + evidence retained in diversity archive
```

**Mapping to current repo:**
- `proposed` → `Proposal` in `evolution.py`
- `shadow_running` → extend `EvolutionStatus` or use `canary.py` comparison
- `evaluated` → `EvolutionStatus.EVALUATED` + `FitnessScore`
- `promotion_pending` → `quality_gates.py` + `telos_gates.py` evaluation
- `promoted` → `EvolutionStatus.ARCHIVED` with `gate_decision = "accepted"`
- `rejected` → `EvolutionStatus.REJECTED`
- `archived` → `DiversityArchive.add()` preserves behavioral niche

---

## 5. Promotion Gate

For a swarm mutation to be promoted to production, ALL of the following must hold:

| Gate | What it checks | Existing support | Implementation needed |
|---|---|---|---|
| **G-1: Existing tests pass** | Full pytest suite on candidate config | CI runs `pytest tests/ -q --tb=short -x --timeout=30 -m "not slow and not docker and not network"`. `self_improve.py` already requires full pytest pass before any self-modification. | Wire Experiment → test suite execution. |
| **G-2: Held-out evals pass** | Candidate passes on tasks NOT used during development | `gauntlet.py` has 5-tier tasks. `benchmark_registry.py` tracks baselines. No held-out split exists. | **Create held-out task suite** (see §6). Wire Experiment → held-out evaluation. |
| **G-3: Equal or reported budget** | Candidate budget ≤ baseline budget, or difference explicitly reported | `EvidenceReceipt.input_tokens`, `.output_tokens`, `.cost_usd`. `cost_tracker.py` logs cost. | Aggregate receipt costs per arm. Compare. Require explicit budget field on Experiment. |
| **G-4: Cost-normalized improvement** | `(candidate_fitness - baseline_fitness) / cost_delta ≥ threshold` | `FitnessScore` (9 dimensions, weighted). `canary.py` compares fitness with promote/rollback thresholds. | Extend canary comparison with cost normalization. |
| **G-5: Unsupported claim rate stable** | `candidate_unsupported_claims ≤ baseline_unsupported_claims` | `ClaimGraph` tracks claims, citation edges, contradictions. `auto_grade` scores groundedness, citation_precision. | Wire Experiment → ClaimGraph comparison. |
| **G-6: Traces complete** | Every dispatch in both arms has an `EvidenceReceipt` | Spine `invoke_agent()` guarantees one receipt per dispatch. | Verify: `len(run.receipt_ids) == expected_dispatch_count`. Requires spine adoption (god objects migrated). |
| **G-7: Evidence chain linked** | Receipts → SwarmRun → Experiment → BetCard → Decision chain is complete | `CorrelationContext` carries `trace_id`, `proposal_id`. `LineageGraph` models parent-child. | Wire new objects into lineage graph. |
| **G-8: Losing candidate archived** | Rejected candidates preserved with full evidence | `EvolutionArchive` (Merkle-chained, append-only). `DiversityArchive` preserves behavioral niches. | Ensure archive.add() is called on rejection, not just promotion. |
| **G-9: Human approval for runtime changes** | Promotion of runtime-changing mutations requires human sign-off | `memory_kernel/promotion_gate.py` requires `human_review` gate. `self_improve.py` is gated behind `DHARMA_SELF_IMPROVE=1`. | Extend promotion gate to cover evolution candidates, not just memory. |
| **G-10: Telos gates pass** | 11 dharmic safety gates | `telos_gates.py` (971 lines), `TelosGatekeeper`. Already evaluated during evolution. | Ensure telos evaluation runs on candidate output, not just proposal. |

---

## 6. Held-Out Eval Strategy

### Starting Position: Human-seeded, system-expanded, human-approved

**Phase 1 (first 20 tasks):** Human-curated from existing gauntlet tiers 1-3.

Rationale: Gauntlet already defines 5 pressure tiers. Tier 1 (CORRECTNESS) and Tier 2 (RESEARCH) tasks are closest to production workloads. Select 20 representative tasks that:
- Cover at least 3 of 5 gauntlet tiers
- Include at least 5 tasks that have known-correct answers (deterministic verification)
- Include at least 5 open-ended tasks scored by quality_gates.py
- Are NOT used during DarwinEngine evolution cycles (held-out = never seen during training)
- Are version-controlled and immutable once released

**Phase 2 (expansion):** System-generated candidates from:
- `SelfResearcher.generate_hypotheses()` failure modes
- `experiment_memory.py` identified component weaknesses
- Production error patterns from `traces.py` and `witness.py` audit cycles
- Adversarial tasks from gauntlet Tier 4 (TELOS ADVERSARIAL)

**Phase 3 (rotation):** Human-approved quarterly rotation:
- Retire 25% of held-out tasks per quarter
- Replace with new tasks from Phase 2 pipeline
- Never reuse retired tasks for at least 2 quarters (prevents overfitting to "old" held-out set)

**Storage location proposal:** `benchmarks/held_out/` (tasks as JSON/YAML files, version-controlled, immutable per release).

**Gaming prevention:**
- Held-out tasks MUST NOT be visible to DarwinEngine during evolution
- Held-out task IDs are published; task content is sealed until evaluation
- Any agent that reads held-out content during non-evaluation is a telos violation

**Content sealing policy:**

Held-out evals are not truly held out if their full task content is
readable by agents in the repo.  The following separation applies:

| Lives in-repo (`benchmarks/held_out/`) | Sealed / private (outside repo) |
|---|---|
| Task IDs and filenames | Full task payloads (prompts, inputs) |
| Metadata (tier, category, expected artifact type) | Exact expected answers / golden outputs |
| Evaluation schemas and rubrics | Scorer reference implementations that embed answers |
| Expected artifact shapes (e.g. "produces a JSON plan") | |

- **Development agents** may see training/dev eval tasks freely.
- **Promotion candidates** are evaluated only against sealed held-out tasks.
- Evaluation results (scores, receipts, traces) may be logged back into the
  repo after evaluation completes, but future task payloads remain sealed.
- The sealed store location is an open question (Q-2 below) — candidates
  include `~/.dharma/held_out_sealed/`, a private S3 bucket, or a
  separate private git repo.  Whatever the location, agents must not have
  read access during non-evaluation runs.

---

## 7. Budget Source of Truth

### Starting Position: Estimated cost for dev, actual billing where available

| Context | Budget source | Why |
|---|---|---|
| Local / dev experiments | Estimated cost from `EvidenceReceipt.cost_usd` (populated from `cost_tracker.py` rate table) | Actual billing not available in real-time. Rate table in `cost_tracker.py` lines 23-41 covers major model families. |
| Production experiments | Actual billing where available, estimated otherwise | Billing APIs lag; receipt-level estimates are synchronous. |
| All experiments | Log: model, input_tokens, output_tokens, cost_usd (estimated), latency_ms, tool_calls | Every receipt already carries these fields. |
| Equal-budget claims | **Require explicit budget record on Experiment object.** Must state: target budget, actual spend per arm, delta, whether budget was equal or difference was reported. | Never claim equal-budget improvement without explicit budget record. |

**Non-goal:** Do not build a billing integration. Use receipt-level cost estimates. If actual billing becomes available, prefer it but don't block on it.

---

## 8. Promotion Authority

### Starting Position: Shadow-mode automatic evaluation, human-gated promotion

| Action | Authority | Rationale |
|---|---|---|
| **Experiment design and execution** | Automated (SelfResearcher or DarwinEngine) | Experiments are observation, not mutation. Safe to automate. |
| **Shadow-mode evaluation** | Automated | Running a candidate in shadow mode produces evidence without production impact. Safe to automate. |
| **Fitness scoring and comparison** | Automated | Math is deterministic. Quality gates and fitness scoring are algorithmic. |
| **Archive / reject decision** | Automated | Archiving a losing candidate is safe. Evidence is preserved. |
| **Docs / report generation** | Automated | Reports and wiki updates to non-canonical surfaces are safe. Memory kernel write receipts handle this already. |
| **Runtime behavior promotion** | **Human-gated** | Changing what runs in production (model routing, agent roles, topology, prompt versions) requires human approval. `self_improve.py` already gates self-modification behind `DHARMA_SELF_IMPROVE=1`. Extend this pattern to all runtime promotion. |
| **Ontology / schema changes** | **Human-gated** | Ontology changes cascade through `telic_seam.py`, `ontology_adapters.py`, `memory_kernel/`. Too high-risk for automation. |
| **Code mutation** | **Human-gated** | `diff_applier.py` uses tollbooth. Protected files list in `self_improve.py` (telos_gates.py, dharma_kernel.py, evolution.py, config.py). |
| **Autonomous production modification** | **Prohibited** | No autonomous production changes without human approval. |

---

## 9. Relationship to Existing Systems

| Existing system | Path | How it relates to Verified Experiment Loop | Integration point |
|---|---|---|---|
| **DarwinEngine** | `dharma_swarm/evolution.py` (3,465 lines) | Proposal → Testing → Evaluation lifecycle already exists. BetCard extends Proposal. Experiment wraps the Testing phase with controlled comparison. | Extend `EvolutionStatus` or add new lifecycle alongside. |
| **FitnessScore (9-dim)** | `dharma_swarm/archive.py` lines 30-70 | Correctness (0.18), dharmic_alignment (0.13), swabhaav (0.08), performance (0.11), utilization (0.11), economic_value (0.13), elegance (0.10), efficiency (0.10), safety (0.06). | Used as-is for candidate evaluation. Experiment compares FitnessScores between baseline and candidate. |
| **MAP-Elites archive** | `dharma_swarm/diversity_archive.py` (414 lines) | Preserves behavioral diversity. Losing candidates with unique behavior profiles are preserved, not discarded. | EvolutionCandidate.cell_id maps to DiversityArchive cell. |
| **Merkle-chained history** | `dharma_swarm/merkle_log.py` (203 lines) | Tamper-evident append-only log. Archive entries are hash-chained. | DecisionRecords and BenchmarkResults can be Merkle-chained for audit. |
| **Cost/token tracker** | `dharma_swarm/cost_tracker.py` (161 lines) | Logs cost per model family to `~/.dharma/cost_log.jsonl`. | Aggregation source for budget comparison. Receipts provide per-dispatch cost; cost_tracker provides per-session aggregation. |
| **Trace store** | `dharma_swarm/traces.py` (265 lines) | File-backed trace entries with history, archive, pattern directories. | SwarmRun traces map to TraceStore entries. |
| **LLM-as-judge gates** | `dharma_swarm/quality_gates.py` (1,003 lines) | QualityScore with per-dimension scoring. 4 domains: CODE, RESEARCH, CONTENT, PROPOSAL. | BenchmarkResult.quality_verdict from quality gates evaluation. |
| **Canary deployment** | `dharma_swarm/canary.py` (156 lines) | PROMOTE / ROLLBACK / DEFER based on fitness comparison. promote_threshold (0.05), rollback_threshold (-0.02). | Extend with cost normalization for equal-budget comparison. |
| **SelfResearcher** | `dharma_swarm/self_research.py` (250 lines) | Generates hypotheses from OutputEvaluation history. Tests them. Produces ExperimentResult. | BetCard producer. SelfResearcher.generate_hypotheses() → BetCard[] pipeline. |
| **Petri Dish** | `experiments/petri_dish/` (harness.py 288 lines, models.py 117 lines) | Working prototype: DNA → mutation → evaluation → archive. | Pattern reference. Upgrade from toy task to real held-out tasks via Experiment object. |
| **ExperimentLog** | `dharma_swarm/experiment_log.py` (87 lines) | JSONL append to `~/.dharma/evolution/experiments.jsonl`. ExperimentRecord with 25+ fields. | Extend ExperimentRecord with baseline_id, budget fields, delta. |
| **ExperimentMemory** | `dharma_swarm/experiment_memory.py` (297 lines) | Analyzes records into strategy signals. Parent scores, component scores, failure patterns. | Consumer of Experiment results. Informs next BetCard generation. |
| **ExecutionProfile** | `dharma_swarm/execution_profile.py` (236 lines) | EvidenceTier (UNVALIDATED→SYSTEM), PromotionState (CANDIDATE→PROMOTED). | Evidence tiering for EvolutionCandidate.evidence_tier. |
| **ClaimGraph** | `dharma_swarm/claim_graph.py` (169 lines) | Claims, citation edges, contradictions, prescriptions, audit findings. | Tracks unsupported claim rate. Gate G-5 compares claim quality between baseline/candidate. |
| **Memory kernel promotion** | `dharma_swarm/memory_kernel/promotion_gate.py` (479 lines) | 6 required gates: human_review, provenance_review, conflict_review, privacy_review, canon_policy_review, knowledgeops_linking. | Pattern for Gate G-9 (human approval for runtime changes). |
| **Witness/Auditor** | `dharma_swarm/witness.py` (428 lines) | Sporadic audit, 5 telos questions, severity-based findings. | Telos alignment check for candidates (Gate G-10). |
| **GinkoBrier** | `dharma_swarm/ginko_brier.py` (806 lines) | Brier-scored prediction tracking. All predictions published including misses. | BetCard.predicted_outcome can be Brier-scored against actual outcome. |

---

## 10. What Not To Build Yet

| Deferred item | Why deferred | When to revisit |
|---|---|---|
| Spark Ingestor expansion | Ingestion without verification creates unverified claim floods. Multiple ingestors already exist. | After Verified Loop is operational. |
| Semantic Ontology refactor | Cannot prove new ontology is better without experiment loop. High cascade risk. | After Verified Loop can evaluate schema changes. |
| Production Verified Loop runtime | Spine adoption must complete first. Loop needs receipts from god objects. | After spine adoption (D-12 through D-14). |
| Dashboard UI for experiments | UI without backend is cosmetic. | After first 3 experiments have run. |
| Autonomous repo mutation | Requires human-gated promotion. | Never without human approval gate. |
| Automatic promotion | Starting position is shadow-mode + human gate. | Only after trust is earned via 10+ verified experiments. |
| New model-routing system | Current routers work. Spine adoption wraps them, doesn't replace them. | Later track, if experiment evidence shows routing improvement. |
| Migrations / new dependencies | Assessment-only session. | Implementation phase. |

---

## 11. Minimum Viable Integration (Post-Spine)

```
1. SelfResearcher produces BetCards
     (extend generate_hypotheses() → BetCard[])
     
2. Spine assigns identity and evidence
     (ExecutionIdentity.proposal_id = bet_id)
     (Every dispatch → EvidenceReceipt via invoke_agent())
     
3. Experiment runner compares baseline vs candidate
     (Two SwarmRuns on held-out tasks)
     (Equal token budget enforced)
     
4. Fitness scoring and cost normalization
     (FitnessScore per arm)
     (cost_normalized_delta = (candidate_fitness - baseline_fitness) / cost_ratio)
     
5. Promotion gate evaluation
     (Gates G-1 through G-10)
     (Human approval for runtime changes)
     
6. DarwinEngine archives candidates
     (EvolutionArchive.add() for all candidates)
     (DiversityArchive.add() for behaviorally unique candidates)
     
7. Verified Loop runs in shadow mode
     (No production impact)
     (Evidence published to reports/)
     
8. Wiki/memory updated with proven insights only
     (Memory kernel promotion gate: 6 required checks)
     (Only experiment-backed claims become canonical)
```

**Smallest first experiment:** Compare a single prompt variant on 5 held-out correctness tasks. Baseline = current prompt. Candidate = proposed improvement. Equal token budget. Measure: pass_rate, weighted_fitness, cost_usd. Decision: promote if `delta > 0.05` AND `cost_ratio ≤ 1.1` AND human approves.

---

## 12. Open Questions

| # | Question | Recommended default | Urgency | Who decides |
|---|---|---|---|---|
| Q-1 | **Where do BetCards live — as Pydantic models or ontology ObjectTypes?** | Start as Pydantic models in `dharma_swarm/evolution.py` (or a new `bet_card.py`). Promote to ontology ObjectType (status=EXPERIMENTAL) after the first 5 BetCards are created and validated. The ontology's `TypeStatus` enum was designed for this progression. | Medium — needed before first BetCard implementation. | Architect (John) |
| Q-2 | **Should the held-out task suite live in-repo or in `~/.dharma/`?** | In-repo under `benchmarks/held_out/` (version-controlled, immutable per release, auditable). Content sealed until evaluation. | High — needed before first experiment. | Architect (John) |
| Q-3 | **How many held-out tasks for v1?** | 20 tasks from gauntlet tiers 1-3. 5 deterministic (known-correct), 5 quality-scored, 10 mixed. | Medium — can start with 5 and expand. | Architect + curator |
| Q-4 | **Should the Verified Loop share `ExperimentLog` or get its own log?** | Extend `ExperimentRecord` with new optional fields (baseline_id, budget_per_arm, delta, confidence, outcome). Single log at `~/.dharma/evolution/experiments.jsonl`. Avoid log proliferation. | Low — implementation detail. | Implementer |
| Q-5 | **What is the promote threshold for cost-normalized fitness?** | Start with canary.py defaults: `promote_threshold = 0.05`, `rollback_threshold = -0.02`. Adjust after 10 experiments. | Low — tunable parameter. | Empirical (data-driven after first experiments) |
| Q-6 | **Should baseline be "current production" or "best single-agent"?** | Both. Every experiment must report against both baselines. "Current production" for practical improvement. "Best single-agent" for the Transcendence Principle claim. | High — methodological. | Architect (John) |
| Q-7 | **What happens when spine adoption is partial?** | Experiments can only count dispatches that produce `EvidenceReceipt`s. If god objects aren't yet migrated, experiments must use spine-aware dispatch paths (A2A, task_board). Document coverage gap. | High — current blocker. | Resolved by spine adoption completion. |

---

## Appendix: Document Governance

This RFC is classified as `experiment` per `docs/AGENTS.md`. It has no runtime authority. It does not replace or subordinate any existing canonical document.

**Next steps if approved:**
1. Architect reviews open questions (§12)
2. Spine adoption track completes (D-12 through D-17 in Workstream A)
3. Implementation RFC promoted to `active_spec` for the build phase
4. First 20 held-out tasks curated
5. First BetCard created (manually)
6. First experiment run in shadow mode
