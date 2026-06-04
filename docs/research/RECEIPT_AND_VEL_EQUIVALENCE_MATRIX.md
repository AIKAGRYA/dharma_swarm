# Receipt & Experiment Loop Concept Equivalence Matrix

> **Binding, docs-only reconciliation.** This document decides which existing repo object *owns* each Spine / Verified Experiment Loop (VEL) concept, so that no parallel systems are created. It implements no code, no persistence, no migrations, and changes no runtime behavior. It is the precondition gate for any further Spine-adoption or VEL code work.
>
> Scope locks: no runtime code, no persistence implementation, no A2A default routing, no changes to `orchestrator.py` / `agent_runner.py` / `swarm.py`, no Spark Ingestor expansion, no Ontology refactor, no VEL runtime, no migrations, no dependencies.
>
> Evidence base: `main` @ HEAD `3e46109` (PR #449 merge) + open PR branches `devin/1780548631-spine-a2a-adoption` (#469), `devin/1780551922-spine-a2a-hardening` (#470), `docs/runtime-truth-spine-plan-and-vel-rfc` (#468). Companion audit: `REPO_WIDE_WHEEL_REINVENTION_AUDIT.md`.

---

## 1. Executive Decision

**#469/#470 are real missing dispatch/evidence-seam work — but all further persistence and object work must reuse existing systems.**

Verified on `main`: `spine.invoke_agent()` has zero non-test runtime callers, `persist_receipt()` / `ensure_receipt_column()` have zero callers, and the only runtime `EvidenceReceipt(...)` constructor is a *different* class in `operator_core/closure_v0.py`. So the spine dispatch+evidence layer was type-complete but unwired, and PR #469's opt-in `a2a_bridge.submit_via_spine()` is the first real `invoke_agent()` dispatch path that emits exactly one spine `EvidenceReceipt` (tested). PR #470's `spine_bypass_report.py` is likewise genuinely new (no pre-existing spine bypass guard). **That seam is not reinvention — keep it.**

However, the repo already contains the *persistence* and *object* substrate the VEL would otherwise re-derive: an append-only `runtime_state.RuntimeReceipt` ledger with an `IdempotencyRecord` exactly-once primitive and identity-derived writers; an append-only `experiment_log.ExperimentRecord`; a Merkle-chained `EvolutionArchive`; a full `decision_ontology.DecisionRecord`/`DecisionLog`; a memory-kernel promotion pipeline ending in `MemoryKernelReviewedCanonicalReceipt`; and — closest of all — `recursive_discovery.py`, a registered shadow Verified Experiment Loop. **Therefore: the dispatch seam continues; new persistence and new objects are frozen until they are expressed as reuse/extension of these owners (decided below).**

---

## 2. Canonical Object Map

| VEL / Spine concept | Existing owner | Path | Reuse strategy | Do not create |
|---|---|---|---|---|
| **BetCard** | `Hypothesis` (+ `_RESEARCH_THREAD` ontology type) | `dharma_swarm/self_research.py:24`; `dharma_swarm/ontology.py:1190` | Extend `Hypothesis` with `success_criteria` / `kill_criteria` / budget ref; register the extension as `TypeStatus.EXPERIMENTAL` | A standalone `BetCard` Pydantic class or table |
| **Experiment** | `ExperimentRecord` / `ExperimentLog` (append-only JSONL) | `dharma_swarm/experiment_log.py:16-88` | Add `held_out_eval_ref` + spine `correlation_id`/`trace_id` link fields to `ExperimentRecord` | A 4th `Experiment` class or a new experiment store |
| **EvidenceReceipt** (dispatch proof) | `spine.receipt.EvidenceReceipt` | `dharma_swarm/spine/receipt.py:37` | This **is** the canonical dispatch-attempt artifact; VEL consumes it, links via `attributes["dharma.attr.*"]` | A subclass/fork of it; a fifth receipt class |
| **RuntimeReceipt** (persisted runtime proof) | `runtime_state.RuntimeReceipt` + writers | `dharma_swarm/runtime_state.py:632`, `record_runtime_receipt` `:2915`, `record_receipt_for_identity` `:2398` | This **is** the canonical *persisted* receipt; spine receipts bridge into it (see §4) | A second persisted-receipt table/path |
| **SwarmRun** | `DelegationRun` (run ledger) | `dharma_swarm/runtime_state.py:510` | Projection/aggregation over `DelegationRun` + child receipts; no materialized object | A new run table or run-ledger system |
| **EvolutionCandidate** | `ArchiveEntry` / `EvolutionArchive` (+ `FitnessScore`) | `dharma_swarm/archive.py:135-289` | Store winners **and** losers in the existing MAP-Elites archive; reuse `FitnessScore` (9-dim) | A 7th "candidate" notion or a new candidate store |
| **BenchmarkResult** | `GradeCard` / `auto_grade` + petri-dish result models | `dharma_swarm/auto_grade/models.py:14`; `experiments/petri_dish/models.py:106`; `dharma_swarm/quality_gates.py` | Cost-normalize an existing scorecard; record held-out-set hash on the result | A new scoring framework |
| **LineageRecord** | `MerkleLog` (+ `EvolutionArchive` Merkle chain; `sakshi/provenance_log.py`) | `dharma_swarm/merkle_log.py:18`; `archive.py:300`; `sakshi/provenance_log.py:74` | Chain VEL records through the existing Merkle log; carry `parent_id`/`prev_hash` | A 6th provenance/lineage chain |
| **DecisionRecord** | `decision_ontology.DecisionRecord` / `DecisionLog` | `dharma_swarm/decision_ontology.py:161-485` | Link a decision to its spine receipt ids + evidence; extend if a field is missing | A new decision log (there are already ≥7 decision objects) |
| **AgentContribution** | `cost_tracker.CostEntry` / `llm_burn.LLMUsageSpan` / per-agent receipts | `dharma_swarm/cost_tracker.py:59`; `dharma_swarm/llm_burn.py:39` | Pure projection over per-agent `EvidenceReceipt`s + cost entries | A payment/credit object (reciprocity ledger integration deferred) |
| **WikiUpdate** | `MemoryKernelReviewedCanonicalReceipt` (memory promotion pipeline) | `dharma_swarm/memory_kernel/promotion_gate.py:80`; `knowledge_ops/memory_promotion_*.py` | A proven learning = a memory-kernel reviewed canonical receipt, gated on evidence completeness | A new wiki/atom object |
| **Cost / token budget** | `LLMUsageSpan` (measure) + `economic_spine.AgentBudget` (enforce) + `model_registry` (price) | `dharma_swarm/llm_burn.py:39`; `economic_spine.py:74`; `model_registry.py` | Populate receipt cost/token at the provider boundary; bind `Experiment.budget` to `economic_spine` | A new cost source at the A2A layer |
| **Trace / correlation** | Spine `trace_id` = cross-layer `correlation_id` (correlation-spine doctrine) | `dharma_swarm/spine/__init__.py`; `spine/receipt.py:90-96` | One continuous `ExecutionIdentity`; reuse one trace store | A 4th trace store |
| **Held-out eval** | petri-dish harness + `auto_grade`/`quality_gates` scoring | `experiments/petri_dish/harness.py`; `dharma_swarm/auto_grade/`; `quality_gates.py` | Reuse harness + scorers; **new** human-seeded sealed set stored **outside agent-readable repo paths**, versioned + hashed | Use of the embedded petri answer-key as "held-out" (it is in source) |
| **Promotion gate** | `tollbooth` + `CanaryDecision` + `PromotionState`/`EvidenceTier` enums | `dharma_swarm/spine/tollbooth.py`; `canary.py:23`; `execution_profile.py:13-23` | Fail-closed `require_execution_tollbooth` + existing canary/quality gates; reuse the enums | A new promotion state machine |

---

## 3. Receipt Taxonomy

| Receipt type | Path | Layer | Purpose | Canonical? | Relationship to `spine.EvidenceReceipt` |
|---|---|---|---|---|---|
| `spine.receipt.EvidenceReceipt` | `dharma_swarm/spine/receipt.py:37` | Dispatch | One artifact per `invoke_agent()` dispatch attempt; OTel GenAI export | **Yes — canonical dispatch evidence** | Itself |
| `operator_core/closure_v0.py` `EvidenceReceipt` | `dharma_swarm/operator_core/closure_v0.py:63` | Closure / proof | Test-exit proof: `success == (test_exit_code == 0)`, replay command | **Yes — canonical closure/test proof** (different concept) | **Name collision only.** Different class, different fields. Joined to spine by shared `correlation_id`, not by type |
| `runtime_state.RuntimeReceipt` | `dharma_swarm/runtime_state.py:632` | Persistence / ledger | Append-only persisted side-effect record; carries `idempotency_key`, `side_effect_key`, `correlation_id`/`causation_id`/`parent_run_id` | **Yes — canonical persisted runtime receipt** | **Persistence target.** Spine `EvidenceReceipt` should be bridged into a `RuntimeReceipt` row (§4) |
| `recursive_discovery.py` receipt family (`RecursiveReceipt`, `LimitationReceipt`, `GeneratedEvalReceipt`, `CandidateDiffReceipt`, `ExperimentResultReceipt`, `WitnessVerdictReceipt`, `PromotionDecisionReceipt`) | `dharma_swarm/recursive_discovery.py:78-160` | Shadow experiment loop | Records the full bet→eval→candidate→experiment→witness→promotion chain; content-hashed; recorded to EventLog + `evaluation_registry` artifact/fact stores | **Yes — canonical shadow experiment-loop proof** | **Closest VEL twin.** Its lifecycle should be the VEL lifecycle; each step should carry/reference a spine `EvidenceReceipt` once joined (§5) |
| `MemoryKernelReviewedCanonicalReceipt` | `dharma_swarm/memory_kernel/promotion_gate.py:80` | Memory promotion | Proof that a learning passed multi-gate review and was promoted to canonical memory; digest + rollback ref + `human_approved` | **Yes — canonical memory-promotion proof** | The "WikiUpdate" terminal. Written only for decisions with complete receipt chains |
| `operator_core/go_evidence_bridge.py` `GoEvidenceReceipt` | `dharma_swarm/operator_core/go_evidence_bridge.py:26` | Go-bridge | Evidence crossing the Go/Python operator boundary | No (bridge-local) | Adapter; not a competing canonical |

**Answers:**
- **Canonical dispatch evidence:** `spine.receipt.EvidenceReceipt`.
- **Canonical persisted runtime receipt:** `runtime_state.RuntimeReceipt` (with `IdempotencyRecord` for exactly-once).
- **Canonical closure / test proof:** `operator_core/closure_v0.py` `EvidenceReceipt` (distinct concept; resolve the name collision in docs).
- **Canonical memory-promotion proof:** `MemoryKernelReviewedCanonicalReceipt`.
- **Canonical shadow experiment-loop proof:** the `recursive_discovery.py` `RecursiveReceipt` family.

---

## 4. Persistence ADR

**Status: Accepted (docs-only decision). Recommendation = Option C, implemented as a B-style bridge.** No code is written here.

| Option | Pros | Cons | Exactly-once support | Append-only? | Risk of duplicate system | Recommendation |
|---|---|---|---|---|---|---|
| **A** — Persist `EvidenceReceipt` into `delegation_runs.receipt_json` as source of truth | Minimal change; one column; co-located with the run | `UPDATE … WHERE task_id` is last-write-wins; one receipt per task; no per-attempt history; no idempotency | **No** (overwrites) | **No** | **High** — creates a second, weaker receipt store parallel to `RuntimeReceipt` | **Reject** as source of truth |
| **B** — Persist `EvidenceReceipt` *through* `runtime_state.RuntimeReceipt` / `IdempotencyRecord` | Reuses the canonical append-only ledger; inherits exactly-once via `idempotency_key`; identity-derived (`build_runtime_receipt` takes `ExecutionIdentity`) | Requires a field mapping (dispatch fields → `RuntimeReceipt.payload`); slightly more wiring (future) | **Yes** (`IdempotencyRecord` + `record_idempotency_consumed`) | **Yes** | **Low** | **Accept as the mechanism** |
| **C** — `RuntimeReceipt` canonical; `delegation_runs.receipt_json` is a projection/cache only | All of B's correctness; keeps a convenient denormalized read on the run row; clear source-of-truth boundary | Two representations to keep consistent (cache invalidation discipline) | **Yes** (truth lives in `RuntimeReceipt`) | **Yes** (truth side) | **Low** (as long as the blob is documented as non-authoritative) | **Accept as the architecture** |

**Decided architecture (matches the stated default preference; repo evidence supports it):**
- `spine.EvidenceReceipt` is the **canonical dispatch proof** (in-memory artifact of one dispatch attempt).
- `runtime_state.RuntimeReceipt` is the **canonical persisted runtime receipt** (append-only, idempotency-keyed source of truth).
- `spine/persistence.py` should **bridge** `EvidenceReceipt → RuntimeReceipt` (map dispatch fields into a `RuntimeReceipt` via `build_runtime_receipt(identity, receipt_type="dispatch_evidence", payload=receipt.to_dict())` and persist through `record_runtime_receipt` / identity-derived writers). Its current `UPDATE delegation_runs SET receipt_json` behavior must **not** be treated as source of truth.
- `delegation_runs.receipt_json` may remain a **projection/cache** for convenient run-row reads, explicitly documented as non-authoritative.

Supporting evidence: `runtime_state.build_runtime_receipt(...)` already accepts an `ExecutionIdentity` and auto-fills `idempotency_key=identity.idempotency_key` (`runtime_state.py:~2369-2393`); the spine `EvidenceReceipt` is identity-derived too — so the bridge is natural, not a fork.

---

## 5. Recursive Discovery Reconciliation

**Decision: `recursive_discovery.py` is a *registered shadow prototype to graduate (extend), not deprecate*. The VEL should extend it; it should not be superseded by a parallel loop.**

Findings (fact): it is not orphaned. It is recorded through `evaluation_registry.record_recursive_discovery_receipt()` (persists to artifact + memory-fact stores, `evaluation_registry.py:590-726`) and is a registered control surface observed in `operator_core/control_surface.py` (`:277-560`). It is explicitly shadow-only by design (records evidence + recommendations, never applies diffs). It already carries content-hash integrity, `parent_id`/`candidate_id` lineage, `cost_usd`, witness verdicts, and rollback pointers.

- **Is it a prototype to graduate?** **Yes.** It is the most complete existing expression of the VEL lifecycle.
- **Is it a shadow-only parallel loop to deprecate?** **No** — it is wired into evaluation_registry + control_surface; deprecating it would discard working, registered evidence plumbing.
- **Should VEL extend it?** **Yes** — adopt its receipt taxonomy and recorder as the VEL's lifecycle backbone.
- **Should VEL supersede it?** **No** — superseding would re-derive the same chain under new names.
- **What to reuse:** the `RecursiveReceipt` family + `content_hash()` + `RecursiveDiscoveryRecorder` + the `evaluation_registry` recording path; the shadow-only/human-promotion discipline.
- **What not to reuse:** do not keep it as a *separate* identity/correlation scheme — when graduated, each step must carry/reference a spine `ExecutionIdentity`/`EvidenceReceipt` so the chain joins the one correlation spine. Do not let it persist receipts to its own store *and* the VEL persist to another.

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

---

## 6. RFC #468 Required Changes

The VEL RFC (`docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`) is already reuse-disciplined but has gaps. Required docs-only edits before any VEL code PR:

1. **Add a "Prior art in this repo" subsection for `recursive_discovery.py`** — state that it is the existing registered shadow VEL, that the VEL **extends** it (per §5), and list which receipts are reused/bridged.
2. **Add a "Prior art" subsection for `runtime_state.RuntimeReceipt` / `IdempotencyRecord`** — state that this is the canonical persisted receipt and that spine `EvidenceReceipt` bridges into it (per §4), correcting the RFC's current implication that receipts persist via `spine/persistence.py` to `delegation_runs`.
3. **Rewrite §3 object specs so every object reads "reuse/extend `X`"** rather than "new object." Specifically: BetCard → extend `Hypothesis`; Experiment → extend `ExperimentRecord`; EvolutionCandidate → reuse `ArchiveEntry`; DecisionRecord → reuse `decision_ontology.DecisionRecord`; LineageRecord → reuse `merkle_log`; WikiUpdate → reuse `MemoryKernelReviewedCanonicalReceipt`; SwarmRun → projection over `DelegationRun`.
4. **State explicitly: no standalone `BetCard` class is to be implemented** until the reuse decision in §2 is accepted.
5. **State explicitly: no new experiment store** is to be created (`ExperimentLog` is the store).
6. **State explicitly: no new decision log** is to be created (`decision_ontology.DecisionLog` is the log).
7. **State explicitly: no new lineage chain** is to be created (`merkle_log` / `EvolutionArchive` Merkle chain is the chain).
8. **State explicitly: held-out eval payloads must not live in agent-readable repo paths** — the embedded petri-dish answer key (`experiments/petri_dish/dataset.py`) is disqualified as "held-out"; the sealed set lives outside the repo (or in an agent-inaccessible store), versioned + hashed, with the hash recorded on each `BenchmarkResult`.

These edits are additive and reversible; they do not change the RFC's design intent, only bind its objects to existing owners.

---

## 7. PR Decision

| PR | Decision | Why | Required before next code PR |
|---|---|---|---|
| **#468** (docs: plan + RFC) | **Revise → merge** | Reuse-disciplined docs; the seam analysis is correct; only missing prior-art bindings | Apply §6 edits; reference this matrix |
| **#469** (`submit_via_spine()` + exactly-one-receipt tests) | **Merge as opt-in** | First real `invoke_agent()` dispatch path; correctly returns (not persists) the receipt; correct layer for cost (`None` at A2A); tested | None blocking. Flag: do not let any surface treat `delegation_runs.receipt_json` as truth |
| **#470** (bypass report + adoption audit + persistence proposal) | **Revise → merge** | `spine_bypass_report.py` is genuinely new and fits the `scripts/governance/` pattern; reversible CI check | Persistence *proposal* in the PR must adopt the §4 ADR (bridge to `RuntimeReceipt`), not propose a new sink |

---

## 8. Next Safe Code PR, If Any

**Recommended next code PR: none yet that touches persistence.** The only safe-to-start code work, once §6 edits and the §4 ADR are accepted, is the **persistence bridge** — and only then.

| Candidate | Verdict | Reason |
|---|---|---|
| A2A Level 6 persistence | **Allowed only after §4 ADR accepted** — then implement as the `EvidenceReceipt → RuntimeReceipt` bridge in `spine/persistence.py`, not a `delegation_runs` blob writer | The ADR resolves the disagreement; without it, this is the duplicate-system risk |
| A2A default route behind feature flag | **Hold** | Default routing is explicitly out of scope this round; also needs the persistence bridge first so default traffic produces append-only receipts |
| Orchestrator preflight seam map | **Allowed as docs-only** (read-only inspection → a map doc), not code | `orchestrator.py`/`agent_runner.py`/`swarm.py` are off-limits for code; a seam map is reversible and informs the next L4 target |
| No code yet | **Default until §6 + §4 accepted** | Safest; this matrix + RFC revision must be agreed first |

**Binding constraint:** do **not** choose A2A Level 6 persistence until the §4 ADR is accepted by the operator.

---

## 9. Files Inspected

| Path | Why |
|---|---|
| `dharma_swarm/spine/receipt.py` | Canonical dispatch receipt |
| `dharma_swarm/spine/invoke.py` | `invoke_agent()` definition + caller check |
| `dharma_swarm/spine/persistence.py` | Current persistence behavior (blob UPDATE) |
| `dharma_swarm/spine/tollbooth.py` (ref) | Promotion-gate primitive |
| `dharma_swarm/runtime_state.py` | `DelegationRun`, `RuntimeReceipt`, `IdempotencyRecord`, `build_runtime_receipt`, `record_runtime_receipt`, `record_receipt_for_identity`, `record_idempotency_consumed` |
| `dharma_swarm/operator_core/closure_v0.py` | Second `EvidenceReceipt` (closure proof), `DarwinProposalCandidate`, `NextDecision` |
| `dharma_swarm/recursive_discovery.py` | Shadow VEL receipt family + recorder |
| `dharma_swarm/evaluation_registry.py` | `record_recursive_discovery_receipt` wiring |
| `dharma_swarm/operator_core/control_surface.py` | recursive_discovery registered as control surface |
| `dharma_swarm/experiment_log.py` | `ExperimentRecord` / `ExperimentLog` |
| `dharma_swarm/archive.py` | `EvolutionArchive`, `ArchiveEntry`, `FitnessScore`, Merkle chain |
| `dharma_swarm/merkle_log.py` | Standalone Merkle log |
| `dharma_swarm/decision_ontology.py` | `DecisionRecord` / `DecisionLog` |
| `dharma_swarm/canary.py`, `execution_profile.py` | Promotion gate + state enums |
| `dharma_swarm/self_research.py` | `Hypothesis` / `Experiment` / `ExperimentResult` |
| `dharma_swarm/ontology.py` | `TypeStatus` + registered ObjectTypes |
| `dharma_swarm/memory_kernel/promotion_gate.py`, `knowledge_ops/memory_promotion_*.py`, `memory_decision_ledger.py` | Memory promotion → reviewed canonical receipt |
| `dharma_swarm/cost_tracker.py`, `economic_spine.py`, `llm_burn.py`, `yoga_node.py` | Cost / token / budget |
| `experiments/petri_dish/dataset.py`, `harness.py`, `models.py` | Held-out eval substrate + embedded answer-key finding |
| `benchmarks/gauntlet.py`, `dharma_swarm/auto_grade/*`, `quality_gates.py` | Benchmark + scoring |
| `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` (#468) | RFC reuse discipline + gaps |
| PR branches #468/#469/#470 (`gh pr view`) | PR state/scope (all OPEN/unmerged; #470 stacks on #469) |

---

## 10. Final Recommendation

**Pause persistence (and all new VEL object creation) only — continue the dispatch seam.**

Concretely: keep #469's `submit_via_spine()` and #470's bypass report (revise → merge per §7); freeze any new persisted-receipt store, any standalone VEL object, and any A2A default routing until (a) the §4 persistence ADR (`EvidenceReceipt → RuntimeReceipt` bridge; `delegation_runs.receipt_json` = cache only) is accepted, and (b) the §6 RFC edits binding every VEL object to an existing owner are merged. This is not "stop and redesign" (the seam is real and correct) and not "redirect into recursive_discovery" wholesale (the dispatch layer is genuinely new) — it is a targeted freeze on the one area where a second competing system would otherwise form: receipt persistence and object proliferation. The dispatch work proceeds; the duplication risk is contained by decision, not by halting progress.
