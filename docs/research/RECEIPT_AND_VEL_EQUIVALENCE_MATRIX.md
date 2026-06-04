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
| RuntimeReceipt | `RuntimeReceipt` | `runtime_state.py:632` | Keep as canonical persisted runtime receipt. Bridge from spine receipt via `adapters.runtime_receipt_kwargs()`. | New runtime-level receipt |
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
| `RuntimeReceipt` | `runtime_state.py:632` | Runtime state | Generic receipt for any runtime event. receipt_type, status, run_id, trace_id, correlation_id, idempotency_key. 13 fields, frozen dataclass. | **Yes — canonical persisted runtime receipt** | Downstream. `adapters.runtime_receipt_kwargs()` bridges spine identity to RuntimeReceipt fields. |
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
| **B** | Persist through `RuntimeReceipt` / `IdempotencyRecord` — spine receipt is converted to RuntimeReceipt, RuntimeReceipt is the persisted form |
| **C** | `delegation_runs.receipt_json` is a projection/cache; `RuntimeReceipt` remains the canonical persisted form; spine receipt is the canonical in-flight form |

### Evaluation

| Criterion | Option A | Option B | Option C |
|---|---|---|---|
| **Exactly-once support** | Weak — `UPDATE … SET receipt_json = ?` is idempotent (overwrites), not exactly-once. Would need `WHERE receipt_json IS NULL`. | Strong — `IdempotencyRecord` already tracks side-effect keys and prevents re-execution (`runtime_state.py:650`). | Strong — inherits from RuntimeReceipt's existing persistence guarantees. |
| **Append-only?** | No — UPDATE overwrites. | Yes — RuntimeReceipt is INSERT-based via `INSERT … ON CONFLICT DO UPDATE`. | Yes — RuntimeReceipt path is append-friendly. Cache can be written once. |
| **Risk of duplicate system** | Medium — creates a second persistence path alongside RuntimeReceipt. Two writers to `delegation_runs`. | Low — uses existing RuntimeReceipt path. Spine receipt is ephemeral/in-flight only. | **Lowest** — clear separation: spine owns in-flight evidence, RuntimeReceipt owns persistence, receipt_json is a convenience projection. |
| **Query ergonomics** | Good — receipt_json is in the same row as run_id/task_id. | OK — RuntimeReceipt has payload dict but no typed fields for provider/model/tokens. | Good — receipt_json provides rich query surface; RuntimeReceipt provides persistence guarantees. |
| **Implementation complexity** | Low — `spine/persistence.py` already written (6 lines). | Medium — need to extend `adapters.runtime_receipt_kwargs()` to carry full receipt JSON in payload. | Medium — need both RuntimeReceipt write + receipt_json projection, but each is simple. |

### Decision

**Option C — recommended.**

Rationale:
1. `spine.EvidenceReceipt` is the canonical in-flight dispatch proof. It is rich (20+ typed fields) and frozen.
2. `RuntimeReceipt` is the canonical persisted runtime receipt. It is generic (payload dict) and already has exactly-once guarantees via `IdempotencyRecord`.
3. `delegation_runs.receipt_json` is a projection/cache column (already migrated in `runtime_state.py:424,467`) that stores the full spine receipt JSON for query convenience.
4. The bridge already exists: `adapters.runtime_receipt_kwargs()` converts spine identity to RuntimeReceipt fields. Extend it to also carry `receipt_json` in the payload.
5. This avoids creating a second persistence writer — the existing `DurableRuntimeState` methods handle the actual SQLite write.

**Persistence flow:**

```
invoke_agent() → EvidenceReceipt (in-flight, frozen)
    ↓
adapters.runtime_receipt_kwargs(receipt) → RuntimeReceipt fields + payload.receipt_json
    ↓
DurableRuntimeState.record_delegation_run(..., receipt_json=...) → delegation_runs row
```

**What not to do:**
- Do not call `spine/persistence.py:persist_receipt()` directly from `submit_via_spine()`. Instead, let the existing `DurableRuntimeState` write flow handle it.
- Do not create a second writer to `delegation_runs`. The existing async/sync write methods in `runtime_state.py:1608,1897` are the only writers.

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
provides exactly-once guarantees. EvidenceReceipt persistence must flow
through RuntimeReceipt — see RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md §4.
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
- Do not create a new persistence surface for EvidenceReceipt (use
  RuntimeReceipt bridge + delegation_runs.receipt_json projection)
```

---

## 7. PR Decision

| PR | Decision | Why | Required before next code PR |
|---|---|---|---|
| **#468** (Spine plan + VEL RFC) | **Revise** | RFC §3 proposes 10 standalone objects without binding them to existing equivalents. Must add reuse constraints per §6 of this matrix before further implementation. | Apply changes from §6 above. |
| **#469** (A2A submit_via_spine) | **Keep — already merged** | First production `invoke_agent()` caller. Not redundant. Adds genuinely missing dispatch-layer receipt seam. | None — merged. |
| **#470** (Bypass report + adoption audit) | **Keep — already merged** | First bypass classification report. Not redundant. Warning-only, never fails CI. | None — merged. |

---

## 8. Next Safe Code PR, If Any

**No code yet.**

Before any implementation PR:

1. **Required:** Revise RFC (PR #468) per §6 of this matrix — bind every proposed object to its existing equivalent.
2. **Required:** This matrix document must be merged or committed so the reuse decisions are discoverable.
3. **Then:** The next safe code PR is **A2A Level 6 persistence** — but only because the Persistence ADR (§4) is now resolved: use RuntimeReceipt bridge + delegation_runs.receipt_json projection, not direct `spine/persistence.py` writes.

The persistence PR scope would be:
- Extend `adapters.runtime_receipt_kwargs()` to carry `receipt_json` in the payload dict.
- Extend the existing `DurableRuntimeState.record_delegation_run()` to write `receipt_json` from the payload.
- Add test: `test_delegation_run_persists_receipt_json`.
- Do NOT add a second writer to delegation_runs.
- Do NOT call `spine/persistence.py:persist_receipt()` from production code (it becomes dead code or a test utility).

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

**Continue Spine adoption. Pause persistence until RFC is revised.**

Specific sequence:

1. **Now:** Commit this equivalence matrix. Revise RFC §3 per §6 above. Both are docs-only.
2. **Then:** Implement A2A Level 6 persistence using Option C (RuntimeReceipt bridge + receipt_json projection). This is the next safe code PR because the persistence ADR is now resolved.
3. **After that:** A2A default route behind feature flag (migrate `ingest_trishula_inbox()` → `submit_via_spine()`).
4. **Do not** start orchestrator migration until A2A surface is fully adopted (all 4 bypass sites resolved).
5. **Do not** create any standalone VEL objects (BetCard, SwarmRun, etc.) until RFC revision is merged.
6. **Do not** build VEL runtime until spine adoption Level 6 is proven on at least the A2A surface.

This is the minimum-reinvention path. Every existing system identified in the audit is preserved and reused. No parallel systems are created.
