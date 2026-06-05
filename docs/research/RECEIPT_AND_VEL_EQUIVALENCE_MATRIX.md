# Receipt & Experiment Loop Concept Equivalence Matrix

> Canonical reconciliation doc (PR #471). Folds in the stronger content independently produced in PR #472 (Devin). All cited symbols verified against the codebase; the `benchmark_registry` reference was corrected from `BenchmarkEntry` to the actual `Benchmark` / `BenchmarkRegistry` (`benchmark_registry.py:27,37`).

**Date:** 2026-06-04
**Author:** Reconciliation audit (PR #471), folding in PR #472 (Devin), commissioned by @AmitabhainArunachala
**Status:** BINDING — this document constrains future implementation choices
**Doc type:** `ADR` — accepted decision record
**Subordinate to:** `docs/governance/CANONICAL_DOC_STACK.md`, `CLAUDE.md`
**Context:** Two independent audits (wheel-reinvention audit + Perplexity review)
confirmed that PRs #469/#470 add a real missing seam, but also identified
serious overlap between proposed VEL objects and existing repo systems.
This matrix resolves every overlap with a binding reuse decision.

---

## 1. Executive Decision

**Are #469/#470 real missing-seam work or reinvention?**

They are **real missing dispatch/evidence seam work**. Before PR #469, zero
production code emitted `spine.EvidenceReceipt`. Before PR #469, zero
production code called `invoke_agent()`. Before PR #470, zero bypass
detection existed.

However, **further persistence/object work must reuse existing systems**.
The RFC (PR #468) proposes 10 new data objects. Eight of them have direct
existing equivalents. Building them as new classes would reinvent
infrastructure. This matrix binds each concept to its existing owner.

**Facts established:**

| Fact | Evidence |
|---|---|
| `invoke_agent()` had 0 production callers before PR #469 | `grep invoke_agent dharma_swarm/` — only spine/invoke.py definition and tests |
| `persist_receipt()` has 0 production callers today | `grep persist_receipt dharma_swarm/` — only spine/persistence.py:50 definition |
| `delegation_runs.receipt_json` column is already migrated in runtime_state.py | `runtime_state.py:424,467` — added via `ALTER TABLE` migration |
| 5 distinct receipt families exist across 5 layers | See §3 Receipt Taxonomy |
| `recursive_discovery.py` is the closest existing VEL prototype | 6 receipt subtypes covering limitation→eval→candidate→experiment→witness→promote |

---

## 2. Canonical Object Map

| VEL / Spine concept | Existing owner | Path | Reuse strategy | Do not create |
|---|---|---|---|---|
| BetCard | `Hypothesis` | `self_research.py:24` | Extend `Hypothesis` with `lifecycle_state`, `kill_criteria`, `spine_trace_id`, `experiment_ids`. Register as EXPERIMENTAL ontology type. | Standalone `BetCard` class |
| Experiment | `ExperimentRecord` | `experiment_log.py:16` | Extend `ExperimentRecord` with `receipt_id`, `baseline_config`, `candidate_config`, `delta`, `confidence`, `budget_per_arm_tokens`. Write to existing `experiments.jsonl`. | New experiment store or class |
| EvidenceReceipt (dispatch) | `spine.EvidenceReceipt` | `spine/receipt.py:37` | Already exists. This IS the dispatch proof. No extension needed. | Any dispatch-layer receipt |
| EvidenceReceipt (closure) | `closure_v0.EvidenceReceipt` | `operator_core/closure_v0.py:63` | Keep as closure-layer receipt per correlation_spine doctrine. | Merging closure receipt into spine receipt |
| RuntimeReceipt | `RuntimeReceipt` | `runtime_state.py:632` | Keep as canonical persisted runtime receipt. **For the A2A path it is ALREADY written by `A2AServer.submit()` (`a2a_server.py:369`).** Associate the spine `EvidenceReceipt` with that existing receipt via `adapters.runtime_receipt_kwargs()` identity fields — do NOT mint a second one. | New runtime-level receipt; a second RuntimeReceipt on a path that already persists one |
| SwarmRun | `DelegationRun` | `runtime_state.py:510` | Use `DelegationRun`. Persist receipt via `delegation_runs.receipt_json` column (already migrated). | Standalone `SwarmRun` class |
| EvolutionCandidate | `ArchiveEntry` | `archive.py:135` | Use `ArchiveEntry`. Already has `fitness`, `parent_id`, `merkle_root`, `promotion_state`, `evidence_tier`. | Standalone `EvolutionCandidate` class |
| BenchmarkResult | `GradeCard` | `auto_grade/models.py:14` | Use `GradeCard` for per-task quality. Use `Benchmark` from `benchmark_registry.py:27` for regression tracking. | Standalone `BenchmarkResult` class |
| LineageRecord | `MerkleLog` + `ProvenanceChain` | `merkle_log.py:18`, `lineage.py:93` | Append receipt data to existing `MerkleLog`. Use `lineage.py` for DAG queries. | Standalone `LineageRecord` class |
| DecisionRecord | `DecisionRecord` | `decision_ontology.py:161` | Use existing `DecisionRecord` for high-stakes experiment decisions. Use `CanaryDecision` enum for simple promote/rollback/defer. | New `DecisionRecord` class (same name, different module — collision) |
| AgentContribution | `AgentScore` | `evaluator.py:252` | Use `AgentScore` (already has `runs`, `mean_quality`, `mean_efficiency`, `mean_latency`). | Standalone `AgentContribution` class |
| WikiUpdate | `MemoryKernelPromotionDecision` | `promotion_gate.py:60` | Reuse 6-gate promotion pattern. | New wiki update class or promotion pipeline |
| Cost/token budget | `CostEntry` / `log_cost()` | `cost_tracker.py:59,71` | Bridge `CostEntry` fields to `EvidenceReceipt` fields. `cost_tracker.py` remains budget source of truth. | New cost tracking system |
| Trace/correlation | `CorrelationContext` | `correlation_context.py:53` | Spine reads `trace_id`/`proposal_id` from `CorrelationContext`. Continue using contextvars propagation. | New correlation mechanism |
| Held-out eval | None exists | — | Must be built from scratch. Task IDs/metadata/rubrics in repo; full payloads + expected answers sealed outside agent-readable paths. | Agent-readable held-out task payloads |
| Promotion gate | `CanaryDeployer` + `MemoryKernelPromotionDecision` pattern | `canary.py:70`, `promotion_gate.py:60` | Extend canary with receipt-linked evidence. Apply 6-gate pattern from memory kernel. | New standalone promotion system |

---

## 3. Receipt Taxonomy

Every receipt-like object in the repo:

| Receipt type | Path | Layer | Purpose | Canonical? | Relationship to spine.EvidenceReceipt |
|---|---|---|---|---|---|
| `spine.EvidenceReceipt` | `spine/receipt.py:37` | Dispatch/invocation | One receipt per `invoke_agent()` call. Provider, model, tokens, cost, latency, status, routing. 20+ fields, frozen dataclass. | **Yes — canonical dispatch evidence** | Self |
| `closure_v0.EvidenceReceipt` | `operator_core/closure_v0.py:63` | Test/acceptance | One receipt per closure execution. Exit code, files changed, duration, replay command. 8 fields, frozen dataclass. | **Yes — canonical closure/test proof** | Peer. Same correlation_id, different layer. Correlation_spine doctrine: "Receipts may differ by closure layer. Correlation identity must not." |
| `RuntimeReceipt` | `runtime_state.py:632` | Runtime state | Generic receipt for any runtime event. receipt_type, status, run_id, trace_id, correlation_id, idempotency_key. 13 fields, frozen dataclass. | **Yes — canonical persisted runtime receipt** | Downstream. `adapters.runtime_receipt_kwargs()` maps spine identity to RuntimeReceipt fields (deterministic `receipt_id`). On the A2A path the RuntimeReceipt is written **once** by `A2AServer.submit()` (`a2a_server.py:369`); the spine EvidenceReceipt is associated to it, never re-minted. |
| `RecursiveReceipt` (6 subtypes) | `recursive_discovery.py:78` | Shadow self-improvement | limitation, generated_eval, candidate_diff, experiment_result, witness_verdict, promotion_decision. Pydantic BaseModel with content_hash. | **Yes — canonical shadow experiment proof** | Parallel. Different purpose (self-improvement loop). Could carry `spine_trace_id` in `metadata`. |
| `MemoryKernelReviewedCanonicalReceipt` | `promotion_gate.py:80` | Memory promotion | Proof that a knowledge atom passed 6 required gates and was human-approved. | **Yes — canonical memory promotion proof** | Independent. Different domain. |
| `MemoryKernelWriteReceipt` | `write_receipts.py:93` | Memory write | Proof that a memory write was policy-compliant. | Yes (memory write) | Independent |
| `MemoryKernelBurnInReceipt` | `burn_in.py:23` | Memory burn-in | Proof of bulk memory initialization. | Yes (burn-in) | Independent |
| `MemoryPromotionReceipt` | `memory_promotion_executor.py:93` | Memory promotion exec | Execution receipt for a completed promotion. | Yes (promotion exec) | Independent |
| `GoWorldReceipt` | `world_radar/receipt_bridge.py:41` | World radar (Go) | Go-emitted evidence for world observations. | Yes (world observation) | Independent. Cross-language bridge. |
| `GoEvidenceReceipt` | `go_evidence_bridge.py:26` | Go evidence (general) | Generic Go evidence parsed by Python bridge. | Yes (Go layer) | Independent |
| `GoGitHubReceipt` | `go_github_bridge.py:48` | Go GitHub ops | Go-emitted GitHub operation receipts. | Yes (Go GitHub) | Independent |
| `OnboardingReceipt` | `roaming_onboarding.py:101` | Onboarding | Agent onboarding proof. | Domain-specific | Independent |
| `ReceiptRef` | `board/models.py:108` | Task board | Reference pointer to a receipt (any type). | No — ref only | Points to any receipt via ID |
| `CommandReceipt` | `recursive_discovery.py:61` | Shadow self-improvement | One command execution within recursive discovery. | Sub-receipt | Child of RecursiveReceipt |

**Canonical receipt answers:**

| Question | Answer | Path |
|---|---|---|
| Which is canonical dispatch evidence? | `spine.EvidenceReceipt` | `spine/receipt.py:37` |
| Which is canonical persisted runtime receipt? | `RuntimeReceipt` | `runtime_state.py:632` |
| Which is closure/test proof? | `closure_v0.EvidenceReceipt` | `closure_v0.py:63` |
| Which is memory promotion proof? | `MemoryKernelReviewedCanonicalReceipt` | `promotion_gate.py:80` |
| Which is shadow experiment-loop proof? | `RecursiveReceipt` (6 subtypes) | `recursive_discovery.py:78` |

---

## 4. Persistence ADR

**Question:** Where should `spine.EvidenceReceipt` be persisted?

### Options evaluated

| Option | Description |
|---|---|
| **A** | Persist `spine.EvidenceReceipt` JSON into `delegation_runs.receipt_json` directly via `spine/persistence.py` |
| **B** | Convert the spine receipt into a *new* `RuntimeReceipt` and persist that as the canonical form |
| **C** | `delegation_runs.receipt_json` is a projection/cache; `RuntimeReceipt` remains the canonical persisted form; spine receipt is the canonical in-flight form |

> **Layering primitives (read before the table).** Three distinct guarantees must not be conflated:
> - `IdempotencyRecord` (`runtime_state.py:650`, DDL `:251`, PK `(idempotency_key, side_effect_key)`) is the **exactly-once substrate**. It is claimed via `try_begin_idempotent_side_effect[_sync]` (`runtime_state.py:3188/3247`) using **`INSERT OR IGNORE` + `rowcount == 1`** — only the first caller wins.
> - `RuntimeReceipt` (`runtime_state.py:632`) is the **canonical persisted runtime receipt**. It is written by `record_runtime_receipt[_sync]` (`runtime_state.py:2915/2944`) using **`INSERT OR REPLACE`**, which is **overwrite-idempotent, NOT exactly-once**. Exactly-once on a RuntimeReceipt write comes from gating it behind an `IdempotencyRecord` claim, not from the receipt write itself.
> - `delegation_runs.receipt_json` (`runtime_state.py:424,467`) is a **projection/cache column only** (currently zero callers).
>
> **Critical fact for the A2A path:** `A2AServer.submit()` (`a2a_server.py:313`) already runs the full canonical cycle per dispatch — `record_execution_identity_sync` (`:335`) → `try_begin_idempotent_side_effect_sync` (`:345`, the exactly-once claim) → `_dispatch` → `record_runtime_receipt_sync(RuntimeReceipt(receipt_type="a2a_task", receipt_id=f"rr_{run_id}_a2a_{status}"))` (`:369`) → `complete_idempotent_side_effect_sync`. Because `submit_via_spine()` → `invoke_agent()` invokes `self._server.submit(a2a_task)`, **a RuntimeReceipt + IdempotencyRecord are already persisted for every A2A call.** The persisted runtime receipt for A2A is not missing; it already exists.

### Evaluation

| Criterion | Option A | Option B | Option C |
|---|---|---|---|
| **Exactly-once support** | Weak — `UPDATE … SET receipt_json = ?` is idempotent (overwrites), not exactly-once. Would need `WHERE receipt_json IS NULL`. | Conditional — exactly-once comes from the `IdempotencyRecord` claim (`INSERT OR IGNORE`), NOT from `record_runtime_receipt` itself, which is `INSERT OR REPLACE` (overwrite-idempotent). On A2A this guarantee already exists inside `A2AServer.submit()`; minting a *second* RuntimeReceipt here adds nothing and risks a duplicate write. | Strong — exactly-once is provided by the `IdempotencyRecord` substrate that `A2AServer.submit()` already claims. The persisted `RuntimeReceipt` is written **once** on that path; `record_runtime_receipt`'s `INSERT OR REPLACE` is overwrite-idempotent, so re-association never creates a duplicate. The projection (`receipt_json`) inherits nothing — it is a cache. |
| **Append-only?** | No — UPDATE overwrites. | Mixed — `record_runtime_receipt` uses `INSERT OR REPLACE` (overwrite-idempotent), gated to once by the IdempotencyRecord claim. | Yes on the canonical path — the single RuntimeReceipt is written once under the idempotency claim. The cache column may be written/overwritten once as a projection. |
| **Risk of duplicate system** | Medium — creates a second persistence path alongside RuntimeReceipt. Two writers to `delegation_runs`. | **High for A2A** — `A2AServer.submit()` already writes the RuntimeReceipt; a spine-layer RuntimeReceipt write here is a *second* RuntimeReceipt for the same dispatch. This is the double-write trap. | **Lowest** — clear separation: spine owns the in-flight `EvidenceReceipt`, the inner runtime layer (`A2AServer.submit()` on A2A) owns the single persisted `RuntimeReceipt` + `IdempotencyRecord`, and `receipt_json` is an optional projection. No new writer is introduced. |
| **Query ergonomics** | Good — receipt_json is in the same row as run_id/task_id. | OK — RuntimeReceipt has payload dict but no typed fields for provider/model/tokens. | Good — the existing RuntimeReceipt provides persistence + identity; an optional `receipt_json` projection adds a rich query surface without a new persistence path. |
| **Implementation complexity** | Low — `spine/persistence.py` already written (6 lines). | Medium — and the work is *redundant* on A2A: it duplicates a write `A2AServer.submit()` already performs. | Low for A2A — the canonical persisted receipt already exists; nothing new must be written. An optional later projection step (receipt_json) is small and isolated. |

### Decision

**Option C — recommended, as a layering doctrine (not as a new writer).**

The three layers are canonical and distinct:
- `spine.EvidenceReceipt` (`spine/receipt.py:37`) — **canonical in-flight dispatch proof**. Rich (20+ typed fields), frozen. Returned from `invoke_agent()`. Not itself persisted by the spine layer.
- `runtime_state.RuntimeReceipt` (`runtime_state.py:632`) — **canonical persisted runtime receipt**.
- `runtime_state.IdempotencyRecord` (`runtime_state.py:650`) — **exactly-once substrate** (`INSERT OR IGNORE` + `rowcount == 1`).
- `delegation_runs.receipt_json` (`runtime_state.py:424,467`) — **projection/cache only**.

Rationale:
1. The spine `EvidenceReceipt` is the canonical in-flight dispatch proof; the persisted `RuntimeReceipt` and its exactly-once guarantee live in the runtime layer.
2. Exactly-once is owned by `IdempotencyRecord`, **not** by `record_runtime_receipt` (which is `INSERT OR REPLACE` = overwrite-idempotent).
3. **On the A2A path the persisted RuntimeReceipt already exists.** `A2AServer.submit()` (`a2a_server.py:313`) already claims the `IdempotencyRecord` (`:345`) and writes the single `RuntimeReceipt` (`:369`) for every dispatch reached through `submit_via_spine()` → `invoke_agent()` → `self._server.submit()`. There is nothing for the spine layer to mint.
4. “Bridge” here means **associate / join / project** — link the in-flight `EvidenceReceipt` to the RuntimeReceipt that already exists (shared `run_id` / deterministic `receipt_id=f"rr_{run_id}_a2a_{status}"` via `adapters.runtime_receipt_kwargs()` identity fields), and *optionally* project the rich receipt JSON into `receipt_json`. “Bridge” does **not** mean write a second `RuntimeReceipt`.
5. `adapters.runtime_receipt_kwargs()` (`spine/adapters.py:303`) is a clean identity map (deterministic `receipt_id`, does not import `RuntimeReceipt`, does not carry rich JSON). Keep it that way; it is for *association*, not for minting a parallel persisted receipt.

### Anti-double-write rule (binding)

> **For any path where an inner runtime layer already writes a RuntimeReceipt, the spine layer must not write a second RuntimeReceipt. It may only return the in-flight EvidenceReceipt and optionally write a projection/cache.**

Concretely for A2A: `submit_via_spine()` must keep returning the single in-flight `EvidenceReceipt`; the one persisted `RuntimeReceipt` + `IdempotencyRecord` come from `A2AServer.submit()`. Invariant to hold: **`count(runtime_receipts WHERE run_id = R) == 1` per A2A dispatch.**

For dispatch paths that do **not** yet persist a RuntimeReceipt, adoption must happen at the **single runtime owner of that path**, never through a parallel spine-layer writer.

**Association / projection flow (A2A, canonical):**

```
submit_via_spine() → invoke_agent() → EvidenceReceipt (in-flight, frozen, returned)
        │
        └─ self._server.submit(a2a_task)            # the ONE persistence owner on this path
               ├─ try_begin_idempotent_side_effect_sync   # exactly-once claim (IdempotencyRecord)
               └─ record_runtime_receipt_sync(RuntimeReceipt("a2a_task", rr_{run_id}_a2a_{status}))  # the ONE RuntimeReceipt
        │
        └─ (optional, later) project EvidenceReceipt JSON → delegation_runs.receipt_json  # cache only, no new RuntimeReceipt
```

**What not to do:**
- Do **not** add an `EvidenceReceipt → RuntimeReceipt` *writer* on the A2A path. The RuntimeReceipt already exists; associate, do not mint.
- Do **not** call `spine/persistence.py:persist_receipt()` (`spine/persistence.py:50`, 0 production callers) from production code, and do **not** promote it to a canonical writer. It is at most a projection-only helper or dead code.
- Do **not** create a second writer to `delegation_runs`. The existing async/sync delegation-run write methods (`runtime_state.py:1608,1897`) are the only writers; any future `receipt_json` write must go through them as a projection.
- Do **not** read `record_runtime_receipt`'s `INSERT OR REPLACE` as an exactly-once guarantee — exactly-once is the `IdempotencyRecord` claim.

---

## 5. Recursive Discovery Reconciliation

`recursive_discovery.py` (329 lines) is the closest existing prototype of the
Verified Experiment Loop. It defines a complete shadow-mode pipeline:

```
limitation → generated_eval → candidate_diff → experiment_result → witness_verdict → promotion_decision
```

### Concept mapping

| recursive_discovery concept | VEL equivalent | Reuse / bridge / deprecate | Reason |
|---|---|---|---|
| `LimitationReceipt` | BetCard source event | **Bridge** — limitation discovery should feed `Hypothesis` extension (BetCard). | Limitation = "the system has gap X" → Hypothesis = "closing gap X improves metric Y". Natural feeder, not duplicate. |
| `GeneratedEvalReceipt` | Experiment design step | **Bridge** — generated evals should become held-out eval task candidates (after human review). | VEL experiments need tasks. Recursive discovery generates tasks from limitations. Complementary. |
| `CandidateDiffReceipt` | EvolutionCandidate | **Bridge** — candidate diffs should become `ArchiveEntry` items (existing evolution archive). | Both represent a proposed code change. ArchiveEntry already has fitness, merkle chain, parent_id. |
| `ExperimentResultReceipt` | BenchmarkResult / Experiment result | **Bridge** — experiment results should be recorded as `ExperimentRecord` entries in existing `experiment_log.py`. | Same concept, different schema. ExperimentRecord already has `pass_rate`, `fitness`, `tokens_used`. |
| `WitnessVerdictReceipt` | Promotion gate check | **Bridge** — witness verdicts map to the `CanaryDecision` pattern (promote/rollback/defer). | Witnesses check safety before promotion — same as canary evaluation. |
| `PromotionDecisionReceipt` | DecisionRecord / CanaryDecision | **Bridge** — promotion decisions should use existing `CanaryDecision` enum + `DecisionRecord` structure. | Exact same concept: decide whether to promote, reject, or hold a candidate. |
| `RecursiveDiscoveryRecorder` | VEL execution engine | **Preserve** — the recorder pattern (append to EventLog via RuntimeEnvelope) is the right persistence mechanism. | VEL execution should use the same EventLog append pattern, not create a new log. |
| `shadow_fixture_receipts()` | VEL test fixtures | **Preserve** — useful as the prototype test fixture for VEL integration tests. | Already demonstrates the full pipeline in shadow mode. |

### Verdict on recursive_discovery.py

**It is a prototype to graduate, not a system to deprecate.**

- Its receipt types map cleanly to VEL lifecycle stages.
- Its `RecursiveDiscoveryRecorder` uses the existing `EventLog` + `RuntimeEnvelope` pattern — the correct persistence mechanism.
- Its shadow-only design is correct for the current phase (no production mutations).
- VEL should extend/wrap recursive_discovery, not supersede it.

**What to reuse:**
- `RecursiveReceipt` base schema (Pydantic, content_hash, stable_payload_hash)
- `RecursiveDiscoveryRecorder` EventLog integration pattern
- `WitnessVerdict` / `WitnessPhase` types
- Shadow-only doctrine (no production mutations until human promotion)

**What not to reuse:**
- Do not create new receipt subtypes when existing objects serve the same role (e.g., do not create a VEL `ExperimentResultReceipt` when `ExperimentRecord` exists).
- Do not create a second EventLog stream when the existing `recursive_discovery` stream works.

---

## 6. RFC #468 Required Changes

The following changes must be made to `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`
before further implementation work begins:

### 6.1 Add prior-art section for recursive_discovery.py

After §1 (Thesis), add:

```markdown
## 1.1 Prior Art: recursive_discovery.py

`dharma_swarm/recursive_discovery.py` (329 lines) implements a shadow-mode
prototype of the Verified Experiment Loop. It defines 6 receipt subtypes
covering the full limitation → eval → candidate → experiment → witness →
promotion pipeline. VEL should extend and graduate this existing system,
not replace it.

Key reuse points:
- `RecursiveReceipt` base schema (content_hash, Pydantic, EventLog integration)
- `RecursiveDiscoveryRecorder` (append-only EventLog via RuntimeEnvelope)
- `WitnessVerdict` / `WitnessPhase` types
- Shadow-only doctrine (no production mutations without human approval)
```

### 6.2 Add prior-art section for RuntimeReceipt / IdempotencyRecord

In §2 or §3, add:

```markdown
`runtime_state.RuntimeReceipt` (runtime_state.py:632) is the canonical
persisted runtime receipt. `IdempotencyRecord` (runtime_state.py:650)
provides the exactly-once guarantee (INSERT OR IGNORE). For the A2A
path, the persisted RuntimeReceipt + IdempotencyRecord are ALREADY
written by A2AServer.submit() (a2a_server.py:369). VEL and spine
adoption must ASSOCIATE the in-flight EvidenceReceipt with that
existing RuntimeReceipt (and optionally project rich JSON into
delegation_runs.receipt_json as cache) — they must NOT mint a second
RuntimeReceipt. See RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md §4 and its
binding anti-double-write rule.
```

### 6.3 Change §3 so every proposed object says "reuse/extend X"

For each object in §3:

| Object | Current §3 text | Required change |
|---|---|---|
| BetCard (§3.1) | Proposes standalone `BetCard` dataclass | Add: **"Implement as extension of `self_research.Hypothesis`. Do not create standalone `BetCard` class."** |
| Experiment (§3.2) | Proposes standalone `Experiment` dataclass | Add: **"Implement as extension of `experiment_log.ExperimentRecord`. Write to existing `experiments.jsonl`. Do not create new experiment store."** |
| SwarmRun (§3.4) | Proposes standalone `SwarmRun` dataclass | Add: **"Use existing `runtime_state.DelegationRun`. Persist spine receipt via `delegation_runs.receipt_json`. Do not create standalone `SwarmRun` class."** |
| EvolutionCandidate (§3.5) | Proposes standalone `EvolutionCandidate` | Add: **"Use existing `archive.ArchiveEntry`. Do not create standalone `EvolutionCandidate` class."** |
| BenchmarkResult (§3.6) | Proposes standalone `BenchmarkResult` | Add: **"Use existing `auto_grade.GradeCard` for per-task quality. Use `benchmark_registry.Benchmark` (`benchmark_registry.py:27`) for regression tracking. Do not create standalone `BenchmarkResult` class."** |
| LineageRecord (§3.7) | Proposes standalone `LineageRecord` | Add: **"Use existing `merkle_log.MerkleLog` for tamper-evident chain. Use `lineage.ProvenanceChain` for DAG queries. Do not create standalone `LineageRecord` class."** |
| DecisionRecord (§3.8) | Proposes standalone `DecisionRecord` | Add: **"Use existing `decision_ontology.DecisionRecord` (same name). Use `canary.CanaryDecision` for simple promote/rollback/defer. Do not create a second `DecisionRecord` class."** |
| AgentContribution (§3.9) | Proposes standalone `AgentContribution` | Add: **"Use existing `evaluator.AgentScore`. Do not create standalone `AgentContribution` class."** |
| WikiUpdate (§3.10) | Proposes standalone `WikiUpdate` | Add: **"Reuse `promotion_gate.MemoryKernelPromotionDecision` 6-gate pattern. Do not create standalone wiki update class."** |

### 6.4 Clarify held-out eval constraint

Update §6 to state explicitly:

```markdown
Held-out eval payloads MUST NOT live in agent-readable repo paths.
In-repo: task IDs, metadata, schemas, rubrics, expected artifact types.
Sealed/private: full task payloads and exact expected answers.
If agents can read the payload, it is not held-out.
```

### 6.5 Add no-new-store constraints

Add to §10 (What Not To Build Yet):

```markdown
- Do not create a standalone BetCard class (extend Hypothesis)
- Do not create a new experiment store (extend ExperimentRecord)
- Do not create a new decision log (use decision_ontology.DecisionRecord)
- Do not create a new lineage chain (use MerkleLog + lineage.py)
- Do not create a new persistence surface for EvidenceReceipt. On
  paths that already persist a RuntimeReceipt (A2A via
  A2AServer.submit()), associate/join the EvidenceReceipt to the
  existing RuntimeReceipt and optionally project into
  delegation_runs.receipt_json as cache. Do not mint a second
  RuntimeReceipt (see anti-double-write rule, §4).
```

---

## 7. PR Decision

> **Correction:** all four PRs (#468–#471) are currently **OPEN**, none are merged. #470 is a superset of #469 (same `submit_via_spine` +137, plus `scripts/governance/spine_bypass_report.py` + tests) and **supersedes #469**.

| PR | Decision | Why | Required before merge |
|---|---|---|---|
| **#468** (Spine plan + VEL RFC) | **Revise, then merge as canonical RFC** | RFC §3 proposes 10 standalone objects without binding them to existing equivalents. Must add reuse constraints per §6 of this matrix, and must not imply a second persistence path / EvidenceReceipt→RuntimeReceipt writer (see §4 anti-double-write rule). | Apply §6 changes; canonicalize `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` here. |
| **#469** (A2A submit_via_spine) | **Close as superseded by #470** | First production `invoke_agent()` caller — genuinely missing seam, but #470 is a strict superset of its diff. Keeping both creates a duplicate RFC + duplicate seam. | Close once #470 is queued. |
| **#470** (A2A seam + bypass report) | **Keep — merge after #471 and #468** | Superset of #469: same dispatch seam plus the first bypass classification report (warning-only, never fails CI). Must drop/rebase its duplicate VEL RFC onto #468 and carry no stale “bridge writer / next-PR = persistence” language. | Remove duplicate RFC (or rebase on #468); next code step is tests-only (#473), not the bridge. |

---

## 8. Next Safe Code PR, If Any

**No persistence code yet. The persisted RuntimeReceipt for A2A already exists — there is nothing new to write.**

Before any implementation PR:

1. **Required:** Revise RFC (PR #468) per §6 of this matrix — bind every proposed object to its existing equivalent, and align it with the §4 anti-double-write rule.
2. **Required:** This matrix document must be merged or committed so the reuse decisions are discoverable.
3. **Then:** The next safe code PR is **#473 — tests-only**, pinning the existing A2A single-RuntimeReceipt invariant. It writes no runtime code.

**#473 (tests-only) scope:**
- Assert that a single `submit_via_spine()` → `invoke_agent()` dispatch results in **exactly one** persisted `RuntimeReceipt` for that `run_id` (i.e. `count(runtime_receipts WHERE run_id = R) == 1`) and one `IdempotencyRecord` claim, both written by `A2AServer.submit()`.
- Assert the in-flight `EvidenceReceipt` is returned (not persisted by the spine layer) and shares identity (`run_id`, deterministic `receipt_id`) with that single RuntimeReceipt.
- This locks the invariant before any optional projection work.

**Later, optional code PR (only if a rich-receipt query surface is actually needed):**
- Project the rich `EvidenceReceipt` JSON into `delegation_runs.receipt_json` **through the existing delegation-run writer** (`runtime_state.py:1608,1897`) as cache only.
- Do NOT add a second writer to `delegation_runs`.
- Do NOT mint a second `RuntimeReceipt` (anti-double-write rule, §4).
- Do NOT call `spine/persistence.py:persist_receipt()` from production code — it remains dead code or a test utility unless deprecated.
- This is a projection PR, **not** an `EvidenceReceipt → RuntimeReceipt` bridge PR.

---

## 9. Files Inspected

| Path | Why inspected | Finding |
|---|---|---|
| `dharma_swarm/spine/receipt.py` | Spine EvidenceReceipt definition | 20+ field frozen dataclass; 1 production caller (a2a_bridge.submit_via_spine) |
| `dharma_swarm/spine/invoke.py` | invoke_agent() definition | Thin pass-through; 1 production caller (a2a_bridge.submit_via_spine) |
| `dharma_swarm/spine/persistence.py` | Receipt persistence | `persist_receipt()` defined, 0 callers; targets delegation_runs.receipt_json |
| `dharma_swarm/spine/identity.py` | ExecutionIdentity | 15-field frozen dataclass; 29 import sites |
| `dharma_swarm/spine/__init__.py` | Public API + correlation_spine doctrine | Documents 3-layer receipt architecture |
| `dharma_swarm/spine/adapters.py` | Runtime receipt bridge | `runtime_receipt_kwargs()` bridges spine identity to RuntimeReceipt |
| `dharma_swarm/operator_core/closure_v0.py` | Closure-layer EvidenceReceipt | Different class, 8 fields, test/acceptance layer |
| `dharma_swarm/runtime_state.py` | DelegationRun, RuntimeReceipt, IdempotencyRecord, delegation_runs DDL | Lines 510 (DelegationRun), 632 (RuntimeReceipt), 650 (IdempotencyRecord), 62 (DDL), 424/467 (receipt_json migration) |
| `dharma_swarm/recursive_discovery.py` | Shadow VEL prototype | 6 receipt subtypes, EventLog integration, shadow-only doctrine. 329 lines. |
| `dharma_swarm/self_research.py` | Hypothesis / Experiment / ExperimentResult | 3 dataclasses; natural BetCard extension point |
| `dharma_swarm/experiment_log.py` | ExperimentRecord + ExperimentLog | Pydantic model, append-only JSONL; natural experiment store |
| `dharma_swarm/archive.py` | ArchiveEntry + FitnessScore | 9-dimensional fitness, Merkle chain, parent_id; natural EvolutionCandidate |
| `dharma_swarm/decision_ontology.py` | DecisionRecord | Full typed model with evidence, challenges, reviews |
| `dharma_swarm/canary.py` | CanaryDecision + CanaryDeployer | promote/rollback/defer enum; fitness-delta decisions |
| `dharma_swarm/cost_tracker.py` | CostEntry + log_cost() | JSONL cost logging; model-based estimation |
| `dharma_swarm/correlation_context.py` | CorrelationContext | Immutable, contextvars, trace_id/proposal_id/session_id |
| `dharma_swarm/merkle_log.py` | MerkleLog | SHA-256 hash chain |
| `dharma_swarm/lineage.py` | ProvenanceChain | SQLite-backed DAG |
| `dharma_swarm/sakshi/provenance_log.py` | ProvenanceLog | Chain-integrity JSONL |
| `dharma_swarm/engine/provenance.py` | ProvenanceLogger | Append-only JSONL per session |
| `dharma_swarm/memory_kernel/promotion_gate.py` | MemoryKernelPromotionDecision + ReviewedCanonicalReceipt | 6 required gates, human-gated promotion |
| `dharma_swarm/memory_kernel/write_receipts.py` | MemoryKernelWriteReceipt | Write-policy compliance receipt |
| `dharma_swarm/memory_kernel/burn_in.py` | MemoryKernelBurnInReceipt | Bulk initialization receipt |
| `dharma_swarm/knowledge_ops/memory_promotion_executor.py` | MemoryPromotionReceipt | Promotion execution receipt |
| `dharma_swarm/knowledge_ops/memory_decision_ledger.py` | MemoryPromotionDecision + Ledger | Read-only decision validation |
| `dharma_swarm/operator_core/world_radar/receipt_bridge.py` | GoWorldReceipt | Go-emitted world observation evidence |
| `dharma_swarm/operator_core/go_evidence_bridge.py` | GoEvidenceReceipt | Generic Go evidence bridge |
| `dharma_swarm/operator_core/go_github_bridge.py` | GoGitHubReceipt | Go GitHub operation receipt |
| `dharma_swarm/roaming_onboarding.py` | OnboardingReceipt | Agent onboarding proof |
| `dharma_swarm/board/models.py` | ReceiptRef | Receipt reference pointer |
| `dharma_swarm/evaluator.py` | AgentScore / ModelScore | Quality evaluation with leaderboards |
| `dharma_swarm/auto_grade/models.py` | GradeCard | 12-dimension quality scoring |
| `dharma_swarm/benchmark_registry.py` | Benchmark + BenchmarkRegistry | Named benchmarks with regression detection |
| `dharma_swarm/traces.py` | TraceStore + TraceEntry | File-backed trace store |
| `dharma_swarm/a2a/a2a_bridge.py` | submit_via_spine() implementation | PR #469 code |
| `dharma_swarm/a2a/a2a_server.py` | A2A server dispatch | submit() + _ensure_execution_identity() |
| `dharma_swarm/yoga_node.py` | UsageTracker | In-memory daily token/dispatch counting |
| `dharma_swarm/telemetry_plane.py` | RoutingDecisionRecord + PolicyDecisionRecord | Telemetry decision records |
| `scripts/governance/spine_bypass_report.py` | PR #470 bypass report | Warning-only scan classifying server.submit() sites |
| `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` | Current RFC text | 678 lines, 12 sections, 10 proposed objects |

---

## 10. Final Recommendation

**Continue Spine adoption. The A2A persisted RuntimeReceipt already exists — pin the invariant first; do NOT build an EvidenceReceipt→RuntimeReceipt bridge.**

**Merge order (docs first, then tests-only code):**

1. **#471** — this corrected equivalence matrix (Persistence ADR + anti-double-write rule). Docs-only.
2. **#468** — canonical, revised RFC (`docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`) per §6 and the §4 anti-double-write rule. Docs-only.
3. **#470** — A2A seam + bypass report, after dropping/rebasing its duplicate VEL RFC onto #468 and stripping any stale “next PR = persistence / bridge writer” language.
4. **#473** — tests-only invariant proof: exactly one persisted `RuntimeReceipt` per A2A dispatch.
5. **Close #469** as superseded by #470.

**Do / Do-not:**

1. **Now:** Commit this matrix and the revised RFC. Both are docs-only.
2. **Then:** #473 tests-only — pin `count(runtime_receipts WHERE run_id = R) == 1` for the A2A path. No runtime code.
3. **Only if needed, later:** project rich `EvidenceReceipt` JSON into `delegation_runs.receipt_json` via the existing delegation-run writer as cache. This is a projection PR, not a bridge PR.
4. **Do not** add an `EvidenceReceipt → RuntimeReceipt` writer on any path that already persists a RuntimeReceipt (A2A already does, via `A2AServer.submit()`).
5. **Do not** enable an A2A default route or migrate `ingest_trishula_inbox()` until the single-persistence invariant is locked by #473.
6. **Do not** start orchestrator migration, build VEL runtime, or create standalone VEL objects (BetCard, SwarmRun, etc.) until the RFC revision is merged and the invariant is proven.

This is the minimum-reinvention, minimum-write path. Every existing system identified in the audit is preserved and reused. No parallel persistence systems are created, and no second RuntimeReceipt is minted.
