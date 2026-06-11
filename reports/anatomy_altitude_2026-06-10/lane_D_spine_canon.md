# Lane D — SPINE & CANON Dock-Map

**Date:** 2026-06-10 · **Reader:** Lane D (anatomy/altitude survey)
**Repos read:** `~/dharma_swarm` (branch `qwen/spine-adoption`, HEAD 2f45b121f) and `~/dharma_swarm_live` (branch `runtime/live`, HEAD dc72312f0, **2 commits behind origin/main** — missing c1124d2a7 #543 and a843eee9b #542; everything cited below as "main" was verified on runtime/live and both missing commits are governance/throttle + an ontology-tollbooth spine slice, neither alters the dock points).
**Grading legend:** RUNS (verified executing in production paths) · WIRED-BUT-DORMANT (code present and tested, no production caller or flag-off) · ASPIRATION (declared in docs/track, not in code).

---

## 1. Declared governance state and its forks

### 1.1 The canon stack (what owns what)

| Layer | Owner | Cite |
|---|---|---|
| Intent (what we're building) | `docs/governance/ACTIVE_TRACK.yaml` | CANONICAL_DOC_STACK.md:22 |
| Surface (what exists) | `ACTIVE_SURFACE_MANIFEST.yaml` | CANONICAL_DOC_STACK.md:23 |
| State (what's live) | `docs/state/LIVE_OPS_DASHBOARD.md` | CANONICAL_DOC_STACK.md:24 |
| Breakage | `docs/state/BROKEN_REGISTER.md` (next id **BR-020**, BROKEN_REGISTER.md:237) | CANONICAL_DOC_STACK.md:57 |
| Architecture/axioms | `docs/governance/SOVEREIGN_MANIFEST.md` | CANONICAL_DOC_STACK.md:61 |
| Cell index | `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` | CANONICAL_DOC_STACK.md:74 |

Max-5 first-read rule (CANONICAL_DOC_STACK.md:32-43): `make onboard` output, CLAUDE.md, SOVEREIGN_MANIFEST.md, ACTIVE_TRACK.yaml, ANTI_SLOP_RULES.md. Anything a cluster adds must NOT become a 6th first-read surface (rule at :96).

### 1.2 Governance state on main (v2 portfolio) — RUNS

`ACTIVE_TRACK.yaml` on main is **schema_version: 2** (live:49), a typed multi-track portfolio:

- **3 spine objectives** (live ACTIVE_TRACK.yaml:56-68): `substrate-nativeness`, `revenue-external-humans-served`, `research-depth`.
- **2 ACTIVE tracks**, both serving `substrate-nativeness`:
  - `runtime-truth-reconciliation-2026-06` (live:129-238) — owns `dharma_swarm/operator_core/**`, `scripts/governance/agent_onboard.py`, `dharma_swarm/runtime_state.py`.
  - `runtime-truth-nats-2026-06` (live:240-291, owner @codex) — owns NATS transport contact modules only.
- **Track policy** (live:77-86): min 1 / warn 5 / max 10 active tracks; conflicts ERROR; surface overlap WARN. "A new project is a NEW NODE, never a violation" (live:22-23).
- **Clean declared gap, first-class:** `revenue-external-humans-served` and `research-depth` have **no active track** (rendered in SOVEREIGN_MANIFEST.md:26-27 as "**no active track**"). The economic-engine cluster's first dock is therefore *governance*, not code: open a track under `active_tracks:` serving `revenue-external-humans-served`.

### 1.3 THE FORK — flag for the orchestrator

The two worktrees declare **different governance regimes for the same repo**:

| | `~/dharma_swarm` (qwen/spine-adoption) | `~/dharma_swarm_live` ≈ origin/main |
|---|---|---|
| Schema | v1, singular `active_track:` (ACTIVE_TRACK.yaml:32,37) | v2, `active_tracks:` portfolio (live:49,128) |
| Active track | `runtime-truth-spine-adoption-2026-06` (qwen:38) | reconciliation + NATS (live:129,240) |
| Reconciliation track | **CLOSED/SHIPPED 2026-06-06** (qwen:164-183) | **ACTIVE** (live:129-238) |

So the qwen branch declares the spine-ADOPTION track (god objects → invoke_agent, target nativeness 30%+, qwen:46-56) which **main has never opened**; main still holds reconciliation ACTIVE which qwen says shipped 11/11. Additionally `~/dharma_swarm/CLAUDE.md` currently contains **unresolved merge-conflict markers** (`<<<<<<< HEAD` … `>>>>>>> origin/main` in the ACTIVE_TRACK rendered block) — the v1 vs v2 fork is sitting literally un-merged in the primary worktree's first-read surface. Any cluster work that starts from `~/dharma_swarm` will read a different "current track" than work starting from main. **Resolution of this fork should precede or accompany any cluster track-opening.**

Other fork-adjacent facts: qwen ACTIVE_TRACK has `parallel_lane_policy` (qwen:146-158) which v2 replaced with the typed graph; the spine-adoption completion criteria (qwen:82-109) are the closest thing to an existing acceptance contract for finishing spine adoption — main's portfolio does not carry them.

### 1.4 ARJUNA doctrine state (cabinet, operator-owned)

`~/.claude/cabinet/ARJUNA.md` now has **three strata**: the 2026-05-07 lock (Palantir of good works, Arjuna Test :32-38), the 2026-05-30 amendment (contact-not-partnership is the pass condition :138-139; "narration outruns build" named as the live inward-pull variant :141-142), and the **2026-06-06 Krishna Inversion** (:149-165): inward self-evolution is now PRIMARY ("the flatlined self-evolution engine … is the organism's primary function failing, and therefore the five-alarm fire" :165), with the separating test at :163 — *does this inward work compound into capability that expresses outward?* This directly licenses the governed-self-evolution cluster and constrains the other two: economic engine must show external contact; truth fabric must serve either contact or compounding capability, not narration.

### 1.5 Known-breakage canon relevant to the clusters

- **BR-003** (BROKEN_REGISTER.md:30-39, BLOCKER, PARTIAL): live evolution apply env-locked closed by `DHARMA_EVOLUTION_SHADOW=1` default at `evolution.py:2156`-region; shadow-apply seam exercised once end-to-end; live apply intentionally gated.
- **BR-014** (:118-127, OPEN): `BHED_GNAN` gate is a literal hard-pass — verified on main at `telos_gates.py:538-539` ("Doer-witness distinction noted", always PASS). Closure must go through `GateRegistry.propose()`, not by editing telos_gates.py (:127).
- **BR-004** (:41-50, PARTIAL): cron split-brain repo vs `~/.dharma/cron/jobs.json`.
- **BR-005** (:52-61, PARTIAL): algedonic signals sensed but unevenly consumed.
- INTERFACE_MISMATCH_MAP.md:7 — 0 open BLOCKERs; remaining: NEW-05 GUARDED (task_board↔runtime_state lifecycle), NEW-07 PARTIAL (trace_id columns added to 7 stores but 54-store coverage incomplete, :31), NEW-08 PARTIAL+ (12 independent `record_outcome()`, TelicSeam signal fanout added, :32), module pair 12 `orchestrate_live → message_bus.receive()` DEGRADED (:149).
- SOVEREIGN_MANIFEST A7 (:137-143): 9 circular-dependency chains, worst is the **6-module evolution cycle** (evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness) — the self-evolution cluster works inside the highest-risk debt zone.
- Substrate-nativeness ~10–15% per SOVEREIGN_MANIFEST.md:11 (NOTE: project memory 2026-06-09 says 81.2% on a different spine definition — the manifest number is the in-repo canon one).

---

## 2. The spine as code actually defines it (main)

### 2.1 Package and doctrine — RUNS (as a library)

`dharma_swarm/spine/` = 8 modules, ~900 LOC total. Doctrine in `spine/__init__.py:5-29`: **"Receipts may differ by closure layer. Correlation identity must not."** Three closure layers, each with its own canonical receipt (mirrored in `ACTIVE_SURFACE_MANIFEST.yaml:706-764` `correlation_spine:` block):

| Layer | Receipt class | Identity field | Cite |
|---|---|---|---|
| Request/response (A2A) | `operator_core.a2a_task_lifecycle.A2ATaskReceipt` | `correlation_id` | manifest:719-729 |
| Dispatch/invocation | `spine.receipt.EvidenceReceipt` | `trace_id` (alias `dharma.correlation_id`) | manifest:731-742 |
| Test/acceptance | `operator_core.closure_v0.EvidenceReceipt` (intentional name collision, manifest:752-756) | `correlation_id` | manifest:744-756 |

Cross-layer join invariant: `A2ATaskReceipt.correlation_id == spine EvidenceReceipt.trace_id == closure_v0 correlation_id` (manifest:758-760). Guard: `scripts/uplift_guards/check_spine_ownership.py` (manifest:762; file exists).

### 2.2 Entry point — `invoke_agent` (spine/invoke.py:36-55)

```python
async def invoke_agent(task, agent_id, context_id, routing, *, invoker: AgentInvoker) -> EvidenceReceipt
```
The spine deliberately **does not own execution** — callers pass an `AgentInvoker` protocol (invoke.py:19-33); the spine is a receipt-emitting pass-through. Migration plan in the docstring: PR A thin wrapper → PR B A2A default invoker → PR C+ all routers collapse onto this signature (invoke.py:5-8). **Main is at PR A.**

### 2.3 Receipt types — three distinct objects; do not conflate

1. **`EvidenceReceipt`** (spine/receipt.py:36-135) — frozen dataclass, in-flight dispatch proof. Status literals at :18, 12 `ErrorSource` literals at :20-33, OTel export adapter `to_otel_span()` at :77 ("OTel is an EXPORT ADAPTER, not the truth surface", :5-6).
2. **`RuntimeReceipt`** (runtime_state.py:632-646) — persisted runtime proof; typed `record_*` family: `record_receipt_for_identity` :2398, `record_ontology_action_receipt` :2555, **`record_self_mod_receipt` :2605** (the self-evolution cluster's receipt sink already exists), `record_mapping_receipt` :2705, `record_runtime_receipt` :2915.
3. **`IdempotencyRecord`** (runtime_state.py:649-661) — exactly-once substrate.
`receipt_json` is **projection/cache only** (spine/persistence.py:50-57 writes it as a nullable column on the existing `delegation_runs` table — "No new persistence surface", persistence.py:8). The receipt doctrine sentence binding all three: ACTIVE_TRACK closed-track notes, live:314-317.

### 2.4 Identity model — `ExecutionIdentity` (spine/identity.py:28-172)

Frozen join-key set: `trace_id` (local dispatch identity) + `correlation_id` (cross-layer alias) + `task_id`/`run_id`/`claim_id`/`idempotency_key` mandatory for dispatch (`require_for_dispatch()` :146-156); optional lineage fields (`causation_id`, `parent_run_id`, `proposal_id`, `external_a2a_task_id`…). Constructed via `.new()` (:54) or `.from_metadata()` (:102, reads nested `execution_identity` metadata key). `spine/tollbooth.py:15-36` is the fail-closed side-effect gate: in `require_identity=True` mode it raises `MissingExecutionIdentity` before side effects without identity + RuntimeStateStore.

### 2.5 Adoption status — graded, per caller

**Identity adoption (the quiet success) — RUNS.** 14+ production modules import spine identity/adapters on main: `message_bus.py:31-32`, `task_board.py:18-22`, `runtime_state.py:28`, `ontology.py:42-43` (+tollbooth), `diff_applier.py:20-21` (+tollbooth), `tool_registry.py:27-28`, `artifact_store.py:15-16`, `durable_execution.py:29`, `runtime_lifecycle.py:18`, `opportunity_dispatcher.py:36`, `opportunity_refill.py:36`, `a2a/a2a_server.py:38`, `a2a/nats_transport.py:28`. The ExecutionIdentity lattice is genuinely woven through the runtime.

**Dispatch adoption (the declared seam) — WIRED-BUT-DORMANT, both call sites:**
- **orchestrator.py** — `_run_task_via_spine` :2164-2236, seam at **:2286** (`if os.environ.get("DHARMA_SPINE_DISPATCH") == "1"`), default OFF, byte-identical fallback at :2292-2296. Receipt is exposed only as `self._last_evidence_receipt` :2232 + `td.metadata["evidence_receipt_id"]` :2233. **Clean negatives:** (a) `DHARMA_SPINE_DISPATCH` is set nowhere — repo-wide grep finds only orchestrator.py:2172,:2286; not in any .sh/.yaml/Makefile/launchd plist/agent_keys.env. (b) `_last_evidence_receipt` is consumed only by `tests/test_orchestrator_spine_dispatch.py:45,68,88` — no production reader yet. Note: the orchestrator invoker does **not** call `spine/persistence.persist_receipt`; the durable record still comes from `_runtime_lifecycle.record_delegation_run` (:2281).
- **a2a/a2a_bridge.py** — `submit_via_spine` :78-207, full identity propagation (`_ensure_execution_identity` :97), correct A2A status→receipt mapping :154-164. **Clean negative:** zero production callers — only `tests/test_spine_adoption_dispatch.py` (:107,134,160,175,198-199) and a comment in `scripts/governance/spine_bypass_report.py:40`. The A2A server's live path is still `A2AServer.submit()` direct.
- **agent_runner.py** — **clean negative: no spine import at all** (absent from the repo-wide spine-importer grep). The third god-object migration (qwen ACTIVE_TRACK next_items id:3) is ASPIRATION on main.

**Verification harnesses around the spine — RUNS:** `scripts/governance/spine_bypass_report.py` and `scripts/uplift_guards/check_spine_ownership.py` exist; `tests/test_spine_adoption_dispatch.py` and `tests/test_orchestrator_spine_dispatch.py` are green-path evidence; WS2 archive single-writer flock is live on main at `dharma_swarm/archive.py:331-352` (fcntl LOCK_EX, PR #556 merged, HEAD dc72312f0 confirms #557 merged too).

---

## 3. Dock points for the three gold clusters

### Cluster A — ECONOMIC ENGINE

**Governance dock (do this first):** new node under `active_tracks:` in `docs/governance/ACTIVE_TRACK.yaml` (insert after live:238) with `serves: revenue-external-humans-served` (objective declared at live:61-64, currently uncovered per SOVEREIGN_MANIFEST.md:26). Checker `scripts/governance/check_track_status.py` enforces edges/WIP/spine-binding (ACTIVE_TRACK.yaml:37-41). Cell declaration: a row in `docs/governance/VENTURE_CELL_PORTFOLIO.yaml` (the cell index owner per CANONICAL_DOC_STACK.md:74; ONE LAW + Hobbling Guard in its header).

**Code docks (all already exist — extend, don't create):**
| Dock | File:line | Grade |
|---|---|---|
| Revenue ledger (full lifecycle: Target→Offer→Outreach→Engagement→ComputeReinvestment) | `dharma_swarm/revenue/spine.py` (RevenueSpine; models in `spine_models.py`; `EconomicSpine` back-compat alias :36) | WIRED-BUT-DORMANT (cell portfolio shows zero live cash; verify against `_SPINE_DIR` state before claiming throughput) |
| Telos↔revenue bridge | `dharma_swarm/revenue/telic_bridge.py` | WIRED-BUT-DORMANT |
| Opportunity intake → task flow | `opportunity_refill.py` → `orchestrate_live.py` queue drain → `TaskBoard` (BR-002 closure, BROKEN_REGISTER.md:197-199) | RUNS (closed via PR #187 with tests `tests/test_br_closures.py`) |
| Outcome feedback | `telic_seam.py` — `record_dispatch` :96, `record_gate_decision` :135, `record_outcome` :246 → `feedback_writer.py` marks addressed (BROKEN_REGISTER.md:198-199) | RUNS |
| Cost/usage on receipts | `EvidenceReceipt.input_tokens/output_tokens/cost_usd` (spine/receipt.py:66-69); explicitly "Future work: wire cost_tracker.py into the receipt" (a2a_bridge.py:89-92) | ASPIRATION — this is the named open slot for revenue-side cost truth |
| Opportunity dispatch identity | `opportunity_dispatcher.py:36` already on ExecutionIdentity | RUNS |

**ARJUNA constraint:** pass condition is *contact* — "one human outside this house is measurably better off" (ARJUNA.md:139). An economic-engine track whose acceptance criteria are all internal ledger rows repeats the narration-outruns-build pattern (:141-142).

### Cluster B — TRUTH FABRIC

The truth fabric **largely exists**; the cluster's work is joins and projections, not new stores.

| Dock | File:line | Grade |
|---|---|---|
| Read-only truth packet contract | `dharma_swarm/operator_core/contracts.py:125` `RuntimeTruthPacket`, `:24` `RuntimeTruthState` (StrEnum of truth axes) | RUNS |
| Operator rendering | `scripts/governance/agent_onboard.py:614` `render_runtime_truth()` (read-only by test `tests/test_agent_onboard.py::test_runtime_truth_render_is_read_only`, live ACTIVE_TRACK:186-189) | RUNS |
| Dispatch proof | `spine/receipt.py:36` EvidenceReceipt (+ OTel adapter :77) | RUNS as type; production emission dormant (§2.5) |
| Persisted proof | `runtime_state.py:632` RuntimeReceipt + `:2915 record_runtime_receipt`; exactly-once `:649 IdempotencyRecord` | RUNS |
| Correlation doctrine + joins | `ACTIVE_SURFACE_MANIFEST.yaml:706-764` (vocabulary :709-716: canonical-store / derived-view / plugin-sink / cache / legacy-mirror / migration-mirror / exempt) | RUNS (declared + guarded) |
| Bypass visibility | `scripts/governance/spine_bypass_report.py` | RUNS |
| Witness logs | `~/.dharma/witness/` JSONL (SOVEREIGN_MANIFEST.md:204,370) | RUNS |
| trace_id propagation across 54 stores | NEW-07, INTERFACE_MISMATCH_MAP.md:31 — 7 stores done, CorrelationContext auto-populates 3 more | PARTIAL — this is the truth fabric's largest real gap |
| Outcome-record unification | NEW-08, map:32 — 12 independent `record_outcome()`, SignalBus fanout added | PARTIAL |
| EvidenceReceipt → operator truth packet join | no production consumer of `_last_evidence_receipt` (clean negative §2.5) | ASPIRATION — exact dock: read `td.metadata["evidence_receipt_id"]` (orchestrator.py:2233) into RuntimeTruthPacket projection |

**Hard non-goals already in canon (live ACTIVE_TRACK:218-224):** no new daemon/database/event-log/truth-store/receipt-system; no second RuntimeReceipt for A2A; "Read models project truth from owners; they do not become authority" (live:160).

### Cluster C — GOVERNED SELF-EVOLUTION

The Krishna Inversion (ARJUNA.md:149-165) makes this the declared five-alarm priority; main's code state:

| Dock | File:line | Grade |
|---|---|---|
| Proposal gate (PDP) | `evolution.py:1396` `gate_check()` → `check_with_reflective_reroute` (telos_gates import at evolution.py:65); BLOCK→REJECTED :1460-1466, else GATED :1468 | RUNS |
| Gate variety expansion | `telos_gates.py:116` GateRegistry, `:130 propose()` (validates tier/patterns/justification, JSONL append :211-215), `:156 approve()` = S5/operator, `:164 load_approved()`, merged at TelosGatekeeper init :264-294 | RUNS (correct route per BR-014: never hand-edit telos_gates.py) |
| Core gates table | `telos_gates.py:250-262` — 11 gates, AHIMSA Tier A, SATYA/CONSENT Tier B, 8 Tier C | RUNS |
| **REVIEW→applied bypass (the WS4a target) — STILL OPEN ON MAIN** | `evolution.py:1771-1778`: archive entry gets `status="applied"` and `gates_passed=["ALL"]` for any `gate_decision != BLOCK` — REVIEW included. REVIEW only costs fitness weight (dharmic_alignment 0.5 vs 0.8, :1560-1565), it does not stop apply. **Clean negative:** `tests/test_telos_self_mod_enforcement.py` does NOT exist on main → PR #558 (WS4a) unmerged. | OPEN GAP — verified |
| BHED_GNAN inert gate | `telos_gates.py:538-539` always-PASS (BR-014) | OPEN GAP |
| Live apply lock | `DHARMA_EVOLUTION_SHADOW=1` default; `apply_diff_and_test` :2193, `apply_sealed_packet` :2262, `apply_in_sandbox` :2285 (BR-003 PARTIAL: shadow seam exercised once) | WIRED-BUT-DORMANT (by design) |
| Archive integrity | `archive.py:331-352` fcntl flock single-writer (WS2, merged) | RUNS |
| Self-mod receipt sink | `runtime_state.py:2605 record_self_mod_receipt` (+ sync :2626) | RUNS (type+store exist; wire proposals through it) |
| Lineage | `ArchiveEntry.parent_id` populated at evolution.py:1761 in this path; project memory holds dgm_loop.py:387 drops it — re-verify in the DGM lane, out of Lane D scope | PARTIAL |
| Diversity preservation (mandatory per CLAUDE.md Transcendence Principle) | `diversity_archive.py` MAP-Elites; "DarwinEngine MUST preserve diversity" | RUNS |

**Sequencing already encoded in canon + memory:** semantic risk classifier must land via `GateRegistry.propose()` (inert until operator `approve()`), the apply-side PEP belongs at the `gate_check`/apply junction (evolution.py:1460 region), and live self-mod stays HARD-BLOCKED until the ALLOW-path keyword evasion class is closed (WS4b, per project memory 2026-06-09 — consistent with what the code shows: `check_with_reflective_reroute` is the same keyword-heuristic gatekeeper, HARM_WORDS set at telos_gates.py:296-299).

---

## 4. The no-new-substrate map (what main already does well — do NOT duplicate)

1. **Receipts.** Three receipt types + idempotency already cover in-flight, persisted, and exactly-once (§2.3). Track non-goals literally forbid a new receipt system (live ACTIVE_TRACK:219). A cluster needing proof emits an existing type or adds a *projection*.
2. **Identity.** `ExecutionIdentity` + adapters + tollbooth are adopted by 14+ runtime modules (§2.5). Never mint a parallel correlation scheme; use `identity_from_carrier`/`identity_metadata` (spine/adapters.py exports, spine/__init__.py:40-46).
3. **Dispatch path.** `invoke_agent` is THE blessed path with two wired call sites; the work is **turning flags on and adding callers**, not writing new dispatchers. SOVEREIGN_MANIFEST A2 (:113-114): repo already has 24 bridges, 4 orchestrators, 14 routers — adding one more is an axiom violation.
4. **Persistence.** `spine/persistence.py:8` doctrine — "No new persistence surface"; receipts ride `delegation_runs.receipt_json`. State Mutation Discipline: everything under `~/.dharma/` (SOVEREIGN_MANIFEST:367-373).
5. **Truth projection.** `RuntimeTruthPacket` + `render_runtime_truth` + `make onboard` are the operator read-model; clusters add axes/rows there, never a second onboarding/status surface.
6. **Gate lifecycle.** `GateRegistry.propose/approve/load_approved` is the only sanctioned way to grow gate variety (telos_gates.py:116-166; BR-014 status note BROKEN_REGISTER.md:127).
7. **Outcome flow.** opportunity_refill → TaskBoard → telic_seam → feedback_writer loop is closed and tested (BR-002). Economic engine extends this loop's payloads, not its topology.
8. **Drift detection.** Guardian Crew auto-maintains INTERFACE_MISMATCH_MAP (map:5, :92-130) with a documented one-line extension recipe (`_METHOD_EXISTENCE_CHECKS`); new cluster contracts get registered there, not in a new watcher.
9. **Track governance.** check_track_status.py + render_active_track_includes.py + managed blocks in CLAUDE.md/SOVEREIGN_MANIFEST — never hand-write track names in prose (ACTIVE_TRACK.yaml:29-32).
10. **Verification scripts.** spine_bypass_report.py + check_spine_ownership.py + the two spine dispatch test files are the adoption verifiers; extend their allowlists/assertions rather than writing new checkers.

---

## 5. Summary judgement

Main's spine is a **well-built, doctrine-coherent library at PR-A maturity**: identity is genuinely adopted across the runtime (RUNS), but both blessed-dispatch call sites are dormant (flag-off orchestrator; caller-less A2A bridge) and the third god object (agent_runner) is untouched. The governance fork (v1 single-track w/ spine-adoption on qwen vs v2 portfolio on main, plus literal merge-conflict markers in the primary worktree's CLAUDE.md) is the single most confusing dock hazard for incoming cluster work. The three clusters dock almost entirely into **existing** surfaces: economic engine = new track + RevenueSpine/telic loop + receipt cost fields; truth fabric = NEW-07/NEW-08 closure + EvidenceReceipt→truth-packet projection; self-evolution = the evolution.py:1771 REVIEW-apply gap (WS4a unmerged on main), BHED_GNAN, and GateRegistry-routed semantic gating — all under the Krishna Inversion's compounding-capability test and the no-new-substrate axioms.
