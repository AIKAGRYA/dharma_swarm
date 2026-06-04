# Runtime Truth Spine — Completion Plan / Definition of Done

**Status:** ACTIVE TRACK (Spine saturation phase)
**Scope:** Stabilize the Runtime Truth Spine as the substrate. No ontology refactor, no ingestor rewrite, no runtime behavior change outside spine scope.
**Evidence basis:** Direct inspection of `dharma_swarm/spine/` (899 lines, 8 files), 26-site import surface, `tools/spine_adoption_metric.py` output, and the spine test suite (38 spine tests passing locally; v2 build report cites 159 passing).

> Doctrine: **one invariant, one invocation path, one receipt.** The spine is the canonical event substrate; projections and caches live above it. Treat the spine as the substrate and complete it before building the Verified Experiment Loop on top.

---

## 1. Current Spine Map

| Path | Role | Current status | Import sites / dependents | Risk |
|---|---|---|---|---|
| `dharma_swarm/spine/__init__.py` | Public surface + correlation-spine doctrine; exports identity, receipt, routing, invoke, adapters | Stable; `__all__` frozen | Import root for all 17 non-test sites | Med — any signature change ripples to all dependents |
| `dharma_swarm/spine/identity.py` | Canonical `ExecutionIdentity` (join-key set), `require_execution_identity`, `from_metadata` | Joined (metric: `identity_contract` joined) | `adapters`, `tollbooth`, `ontology`, `runtime_state`, `runtime_lifecycle`, A2A | High — the truth owner; bugs corrupt all lineage |
| `dharma_swarm/spine/receipt.py` | `EvidenceReceipt` canonical artifact; OTel GenAI export; token/cost fields | Stable; OTel is export adapter only | `invoke`, `persistence`, `artifact_store` | High — canonical proof object |
| `dharma_swarm/spine/adapters.py` | Carry identity across organs (no routing/dispatch/persist); per-surface field mapping | Largest file (327 lines); adapter-ready for 4 surfaces | `a2a_server`, `message_bus`, `task_board`, `artifact_store`, `ontology`, `tool_registry` | Med-High — implicit per-surface heuristics could mis-map identity |
| `dharma_swarm/spine/tollbooth.py` | Fail-closed gate: require identity + RuntimeStateStore before side effects | Joined; small + deterministic | `ontology` (`require_execution_tollbooth`), opportunity_dispatcher | High — the promotion/gating chokepoint |
| `dharma_swarm/spine/routing.py` | `RoutingDecision` canonical value object | Shape-only (7 routers not yet collapsed onto it) | `invoke` | Low-Med — adoption incomplete but non-blocking |
| `dharma_swarm/spine/invoke.py` | The one blessed `invoke_agent` path (pass-through + receipt) | PR-A pass-through stage; not yet default invoker | spine internal | Med — full collapse (PR C+) deferred, acceptable |
| `dharma_swarm/spine/persistence.py` | Projection-only helper targeting `delegation_runs.receipt_json`; idempotent column migration | Stable; 0 production callers; **not** a canonical runtime receipt writer | spine internal | Med — must not be promoted into a second `RuntimeReceipt` writer |

Adjacent (in-scope dependents, not part of the 8-file core): `dharma_swarm/runtime_state.py` (RuntimeStateStore ledger), `dharma_swarm/runtime_lifecycle.py`, `dharma_swarm/a2a/a2a_server.py`, `dharma_swarm/message_bus.py`, `dharma_swarm/task_board.py`, `dharma_swarm/tool_registry.py`, `dharma_swarm/artifact_store.py`, `dharma_swarm/ontology.py`, `dharma_swarm/opportunity_dispatcher.py`, `dharma_swarm/diff_applier.py`, `dharma_swarm/revenue/spine.py`.

**Adoption metric (current):** 16 mission surfaces — **8 joined, 4 adapter-ready (75% joined-or-adapter-ready), 1 missing, 1 quarantine, 2 legacy.** Goal floor: **≥95%.** Non-joined surfaces: `tool_registry_dispatch`, `ontology_action_tollbooth`, `self_modification_loop`, `workflow_checkpoint_replay`, `mcp_tool_access`, `nats_jetstream_transport`, `opportunity_refill_research_backend`, `legacy_no_identity_escape_hatch`.

---

## 2. Spine Invariants

| Invariant | Why required | Existing support | Missing support | Test needed |
|---|---|---|---|---|
| Canonical identity is the owner of truth | Every durable unit of work needs one join-key set; prevents silent renames | `ExecutionIdentity` frozen dataclass; `require_for_dispatch` | None critical; ensure no adapter generates identity at hard boundaries | Property test: identity round-trips through all adapter surfaces unchanged |
| EvidenceReceipt creation + validation | One canonical in-flight artifact per dispatch attempt; basis of all later evidence | `EvidenceReceipt`, `to_otel_span`, `to_dict` | Validation of required-field completeness before association/projection/export | Test: receipt with missing trace_id rejected by association/projection path |
| trace/correlation identity continuity | Cross-layer joins (A2A ↔ dispatch ↔ closure) must share one value | `correlation_id` = `trace_id` alias; doctrine in `__init__.py` | Enforcement that all 3 layers carry the same correlation value | Test: same correlation_id appears on receipts across layers a request traverses |
| Cost/token attachment | Equal-budget comparison (Verified Loop dependency) | `input_tokens`/`output_tokens`/`cost_usd`/`latency_ms` on receipt | Guarantee these are populated on real dispatch, not just constructible | Test: live invoke path populates usage fields |
| Tamper-evident history / Merkle interaction | Auditability of the run ledger | `runtime_state` receipt ledger; `merkle_log.py` | Confirm receipt ledger is (or chains to) tamper-evident store | Test: ledger tamper detection / hash continuity |
| Tollbooth / gating semantics | Fail-closed before side effects in required mode | `require_execution_tollbooth` (identity + RuntimeStateStore) | Apply tollbooth at remaining non-joined side-effecting surfaces | Test: side effect without identity raises in required mode (exists for ontology; extend) |
| Provenance source-artifact → result-artifact | Lineage from input to output artifact | `artifact_id`/`run_id`/`causation_id`/`parent_run_id` fields; artifact_store adapter | End-to-end provenance assertion across a full run | Test: provenance chain from source artifact to result artifact replayable |
| Stable import surface | 17 dependents must not break | Frozen `__all__`; dependency-light identity module | Lock the public surface against accidental change | Test/CI: import-surface snapshot test (assert exported names) |
| Backward compat with ontology + memory kernel | Ontology already imports `spine.identity` + `spine.tollbooth` | Confirmed imports at `ontology.py:42-43`; `spine_ref` properties | None require change — must remain unchanged | Existing ontology tests must stay green (no spine-driven regressions) |
| Test coverage expectations | DoD gate | 7 spine test files (38 tests pass locally) | Coverage on adapter per-surface mapping + correlation continuity | Targeted coverage pass on `adapters.py` surface branches |

---

## 3. Definition of Done

| Requirement | Status | Evidence | Remaining work |
|---|---|---|---|
| All existing spine tests passing | ✅ Met (local) | 38 passed across the 7 spine test files; v2 report cites 159 suite-wide | Re-run in CI on the integration branch |
| All import sites still valid | ✅ Met | 17 non-test import sites resolve; `__all__` exports intact | Add import-surface snapshot test to lock it |
| EvidenceReceipt lifecycle documented | ◑ Partial | `receipt.py` docstrings + `__init__.py` closure-layer doctrine | Add a short `docs/` lifecycle note (create→associate/project→export) |
| Identity semantics documented | ◑ Partial | `identity.py` docstrings; correlation-spine doctrine | Document trace_id vs correlation_id rule in one place |
| Provenance chain testable | ◑ Partial | fields exist; artifact adapter present | Add end-to-end provenance test (source→result) |
| trace/correlation context stable | ✅ Met | alias enforced in receipt + identity | Add cross-layer continuity test |
| Cost/token hooks identified | ✅ Met | `input_tokens`/`output_tokens`/`cost_usd`/`latency_ms` | Confirm population on live dispatch (test) |
| No ontology refactor required | ✅ Met | ontology imports spine read-only; unchanged | Hold the line — do not touch ontology |
| No ingestor rewrite required | ✅ Met | ingestor untouched | Hold the line |
| No runtime behavior change outside spine scope | ✅ Met | spine changes are additive (adapters/tollbooth/receipts) | Keep slices additive; quarantine, never delete |

**Net DoD position:** Spine is **substantively done and stable** (tests green, imports valid, identity/receipt/tollbooth joined). Remaining work is **saturation + documentation + targeted tests**, not new architecture. The two genuine blockers to "100% substrate" are: (a) closing the **legacy ledger bypass** (`runtime_state.py` sync helpers), and (b) landing **mapping receipts** for the parallel lineages (workflow_id, proposal_id, event_id, ontology_action, engine_artifact).

---

## 4. Minimal Code Work, If Any

| Possible patch | File(s) | Why needed | Risk | Should do now? |
|---|---|---|---|---|
| Import-surface snapshot test | `tests/` (new test only) | Locks the 17-dependent public surface against accidental break | Very low (test-only) | **Yes** — pure safety, reversible |
| Cross-layer correlation-continuity test | `tests/` (new test only) | Proves the core invariant the whole spine is built on | Low (test-only) | **Yes** — formalizes existing behavior |
| End-to-end provenance test (source→result artifact) | `tests/` (new test only) | DoD requires provenance be testable | Low (test-only) | **Yes** — additive |
| EvidenceReceipt lifecycle + identity doc note | `docs/` (new doc only) | DoD requires documented lifecycle/semantics | None (docs-only) | **Yes** — reversible |
| Close legacy ledger bypass (quarantine sync helpers) | `runtime_state.py` (`create_task_claim_sync`/`create_delegation_run_sync`) | Until closed, adoption metric is structurally dishonest | **Med** — touches runtime; this is Slice A of an existing tracked plan (PR #425/#430) | **Defer to the existing slice owner** — clearly within active track but not a same-name quick patch; coordinate, don't free-hand |
| Mapping receipts for 5 parallel lineages | per Slice C of PR #425 | Drives adoption toward ≥95% | Med | **Defer to existing slice** — already specced (#436 landed slice-c mapping receipts; remainder tracked) |

**Rule applied:** Only the test-only and docs-only patches are proposed for *now* (smallest safe, reversible). The runtime-touching items (legacy bypass, remaining mapping receipts) are already owned by the tracked spine-adoption slices (#425/#430/#435/#436/#446) — **do not free-hand them in this lane.** If a slice is unassigned, stop and ask before implementing.

---

## 5. Tests

| Test path | What it proves | Current status | Gap |
|---|---|---|---|
| `tests/test_runtime_truth_spine_v1.py` | Core v1 invariants (identity, receipt shape) | ✅ Passing | — |
| `tests/test_runtime_truth_spine_v2_adapters.py` | Adapter identity carry across surfaces | ✅ Passing | Per-surface branch coverage in `adapters.py` |
| `tests/test_runtime_truth_spine_v2_evidence.py` | EvidenceReceipt creation/serialization | ✅ Passing | Required-field completeness before association/projection/export |
| `tests/test_runtime_truth_spine_v2_tollbooth.py` | Fail-closed gating semantics | ✅ Passing | Extend to remaining non-joined surfaces |
| `tests/test_runtime_truth_spine_adoption.py` | Adoption invariants | ✅ Passing | — |
| `tests/test_spine_adoption_metric.py` | Metric script correctness | ✅ Passing | — |
| `tests/test_spine_mapping_receipts.py` | workflow_id↔run_id and other mapping receipts | ✅ Passing | Coverage for remaining lineages |
| (new) import-surface snapshot | Public surface stability | ❌ Missing | Add (test-only) |
| (new) cross-layer correlation continuity | The global identity invariant | ❌ Missing | Add (test-only) |
| (new) end-to-end provenance | source→result lineage | ❌ Missing | Add (test-only) |

**Run strategy:** Run the **targeted spine subset first** (the 7 files above + any new tests) — it is fast (~9s) and isolates spine regressions. Run the **full suite** only before merging the integration branch, to confirm no dependent (ontology, runtime_lifecycle, a2a) regressed. Targeted-first, full-before-merge.

---

## Adoption Definition Reconciliation

> **Updated for PR #469 (`spine(adoption-slice-1): A2A bridge dispatches through invoke_agent()`, branch `devin/1780548631-spine-a2a-adoption`, open).** The first real dispatch-ownership path now exists. The model below is revised to distinguish *where* on the surface adoption lands.

Two apparently different findings were on the table:

- **Devin report:** Spine types are shipped, but **zero production dispatches flow through `invoke_agent()`**.
- **This report:** Spine v2 is **75% joined-or-adapter-ready, 12/16 surfaces**.

**These were never contradictory — they measure different things.** The 75% figure measures **identity adoption** (does a surface import the spine and adapt/attach `ExecutionIdentity` + preserve correlation continuity?). The Devin finding measures **dispatch ownership** (does real execution flow through the one blessed `invoke_agent()` path and emit a canonical `EvidenceReceipt`?). Before #469 the second had not started; #469 starts it on exactly one opt-in path.

### What changed with #469

**Before #469:** no runtime caller of `invoke_agent()` anywhere; no runtime surface emitted a spine `EvidenceReceipt`.

**After #469 (verified against the branch):**
- `a2a/a2a_bridge.py` gains an **opt-in** `submit_via_spine()` that dispatches through `invoke_agent()` and returns **exactly one** `EvidenceReceipt` (one constructed per outcome branch: ok / failed / cancelled / dropped).
- Exactly-one-receipt behavior is **tested** (`tests/test_spine_adoption_dispatch.py`: `test_a2a_bridge_dispatch_emits_exactly_one_evidence_receipt`, plus identity-preservation and failure-source tests).
- The existing **default `A2AServer.submit()` / direct A2A paths still bypass the Spine** — `submit_via_spine()` is a new method, not the default route.
- The receipt is **returned to the caller, not persisted** — no `persist_receipt` / `ensure_receipt_column` call in the new code.
- Token/cost fields are deliberately left `None` (A2A dispatch does not yet carry provider token counts).
- `orchestrator.py`, `agent_runner.py`, and `swarm.py` remain **Level 0** (no spine import).
- **Verified Experiment Loop runtime remains blocked.**

### Adoption levels (explicit)

| Level | Definition |
|---:|---|
| 0 | No Spine awareness |
| 1 | Imports Spine types |
| 2 | Can adapt/attach `ExecutionIdentity` |
| 3 | Preserves cross-layer correlation identity |
| 4 | Real dispatch path flows through `invoke_agent()` |
| 5 | Exactly one `EvidenceReceipt` emitted per logical dispatch |
| 6 | EvidenceReceipt associated to persisted `RuntimeReceipt` / trace-linked / cost-token fields attached where available |
| 7 | Bypass guard active and allowlist shrinking to zero |

### Four axes of adoption (added post-#469)

A single per-module "level" hid an important distinction that #469 makes unavoidable: a module can reach Level 4–5 on *one method* while its *default path* still bypasses the Spine. Adoption must therefore be read on four axes:

1. **Method-level adoption** — at least one method on the surface reaches the level (e.g. `submit_via_spine()` reaches L4–L5).
2. **Module-level adoption** — the surface as a whole (its identity/correlation posture) reaches the level.
3. **Default-path adoption** — the path callers hit *by default* reaches the level (the honest "is real traffic covered?" axis).
4. **Persisted-runtime association adoption** — the emitted in-flight `EvidenceReceipt` is associated to the persisted runtime receipt, trace-linked, and cost/token attached where available (Level 6), not just constructed in memory.

The 75%/12-of-16 metric reflects **module-level** identity adoption (L2–L3). #469 is the first **method-level** L4–L5 datapoint, with **default-path** and **persisted-runtime association** adoption still at zero.

### Per-surface / per-method mapping

Evidence-based from inspection of `main` plus PR #469's branch. "Adoption level" is the **highest level reached by any path** on the surface; the four axis columns disambiguate where that level actually lands.

| Surface / method | Adoption level | Method-level? | Default path? | EvidenceReceipt emitted? | Runtime receipt associated? | Remaining gap |
|---|---:|---|---|---|---|---|
| `a2a/a2a_bridge.py` → `submit_via_spine()` *(new, #469)* | 5 | Yes (opt-in) | No | Yes — exactly one, tested | No | Make a default/blessed route; prove association with the existing runtime receipt/projection if needed; attach cost/token (L6) |
| `a2a/a2a_bridge.py` → `submit()` / default | 1 | n/a | Yes | No | No | Route default traffic through the spine path |
| `a2a/a2a_server.py` | 3 | Partial | No | No | No | Dispatch through `invoke_agent`; emit one receipt |
| `runtime_state.py` | 3 (+partial 7) | No | No | No (projection helper exists, unused) | No | Close legacy bypass (allowlist→0); keep `receipt_json` projection-only and prove single runtime owner |
| `runtime_lifecycle.py` | 3 | No | No | No | No | Emit receipt on lifecycle dispatch |
| `task_board.py` | 2 | No | No | No | No | Correlation continuity; receipt on claim dispatch |
| `message_bus.py` | 2 | No | No | No | No | Correlation on send/consume; receipt |
| `artifact_store.py` | 2 | No | No | No | No | Provenance receipt on artifact record |
| `tool_registry.py` | 2 | No | No | No | No | Tollbooth on side-effecting calls; receipt |
| `ontology.py` | 2 | No | No | No | No | Mapping receipt for ontology actions — **no refactor** |
| `diff_applier.py` | 2 | No | No | No | No | Receipt on self-mod apply (proposal→apply→verify) |
| `opportunity_dispatcher.py` | 2 | No | No | No | No | Correlation continuity; receipt on dispatch |
| `agent_runner.py` | 0 | No | No | No | No | Adopt identity; route real agent runs through `invoke_agent` — **primary L4 target for Verified Loop** |
| `orchestrator.py` | 0 (1 partial) | No | No | No | No | Adopt spine identity; dispatch through `invoke_agent`; emit `EvidenceReceipt` and associate to a single runtime receipt — **primary L4 target for Verified Loop** |
| `swarm.py` | 0 | No | No | No | No | Adopt identity at top-level swarm dispatch |

**Key reading:** #469 proves the dispatch-ownership pattern works (method-level L5 with exactly-one-receipt under test), but **default-path** and **persisted-runtime association** adoption are still zero across the fleet, and the surfaces the Verified Loop runs experiments through — `agent_runner.py`, `orchestrator.py`, `swarm.py` — remain **Level 0**.

### Explicit statement

> **Adapter-ready adoption does not yet prove dispatch-owned EvidenceReceipt emission. PR #469 demonstrates method-level dispatch ownership on one opt-in A2A path (exactly one EvidenceReceipt, tested), but default-path and persisted-runtime association adoption remain zero. Verified Experiment Loop runtime remains blocked until the dispatch surfaces used by experiments — at minimum `agent_runner.py`, `orchestrator.py`, and `swarm.py` — emit exactly one EvidenceReceipt per logical dispatch on their default path, and those in-flight receipts are associated to a single persisted RuntimeReceipt / trace-linked without minting a second runtime receipt.**

---

## Final Output

### 1. Exact files inspected
- `dharma_swarm/spine/__init__.py`, `identity.py`, `receipt.py`, `adapters.py`, `tollbooth.py`, `routing.py`, `invoke.py`, `persistence.py`
- `dharma_swarm/ontology.py` (confirmed spine imports at lines 42–43), `dharma_swarm/runtime_state.py`, `dharma_swarm/execution_profile.py`
- `tools/spine_adoption_metric.py`, `reports/governance/spine_adoption_metric.json`
- Spine tests: `tests/test_runtime_truth_spine_v1.py`, `..._v2_adapters.py`, `..._v2_evidence.py`, `..._v2_tollbooth.py`, `test_runtime_truth_spine_adoption.py`, `test_spine_adoption_metric.py`, `test_spine_mapping_receipts.py`
- Verified-Loop-adjacent assets: `archive.py`, `experiment_log.py`, `decision_ontology.py`, `canary.py`, `self_research.py`, `merkle_log.py`, `experiments/petri_dish/models.py`
- Agent prompts: `NEXT_SPRINT_PROMPT.md`, `CLAUDE_CODE_LIVE_FIRE_PROMPT.md`; open PRs #425, #426, #431; merged #427/#430/#435/#436/#446

### 2. Exact files created or modified
- **Created:** `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` (RFC, design-only)
- **Created:** `docs/research/RUNTIME_TRUTH_SPINE_COMPLETION_PLAN.md` (this document)
- **Modified:** none. No runtime code, migrations, dependencies, or renames.

### 3. Spine Definition of Done
Substantively met: spine tests green, 17 import sites valid, identity/receipt/tollbooth joined, cost/token hooks present, ontology/memory-kernel backward-compatible. Remaining to reach 100% substrate: close the legacy ledger bypass and land the remaining mapping receipts (both owned by existing tracked slices), plus add 3 test-only and 1 docs-only artifacts.

### 4. Verified Experiment Loop RFC summary
Design-only RFC at `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md` defining 10 core objects, two lifecycles (mapped onto existing `PromotionState`/`EvidenceTier`), a fail-closed promotion gate, and recommended defaults for held-out evals (human-seeded/system-expanded/human-approved), budget (hybrid), and authority (shadow-auto-eval, human-gated promotion). It reuses existing assets (DarwinEngine, MAP-Elites archive, Merkle log, canary, decision ontology, petri dish) and introduces no new identity, ledger, or transport.

### 5. Remaining blockers before implementation
- Legacy ledger bypass in `runtime_state.py` not yet closed → adoption metric not yet honest at 100%.
- Remaining mapping receipts (subset of the 5 parallel lineages) outstanding.
- Adoption at 75% joined-or-adapter-ready; floor target ≥95%.
- These are owned by existing spine-adoption slices — coordinate, do not free-hand.

### 6. Should Spark Ingestor remain deferred?
**Yes.** No ingestor work this lane. The Verified Loop's MVI consumes ingestor output only after Spine DoD.

### 7. Should Semantic Ontology remain deferred?
**Yes.** Ontology already imports the spine read-only and must remain unchanged. No refactor.

### 8. Next safest action
Add the three test-only artifacts (import-surface snapshot, cross-layer correlation continuity, end-to-end provenance) and the one docs-only lifecycle note in the Spine lane; in parallel, route the RFC for review. Both are reversible and touch no runtime behavior. Defer the legacy-bypass and remaining-mapping-receipt work to the existing tracked slices — stop and confirm ownership before implementing those.
