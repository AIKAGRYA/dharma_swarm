# DharmaGraph Backbone — Phased Architecture and Autonomous Campaign Spec

**Role:** proposed revision of the active implementation spec for the existing `dharmagraph-engine-2026-07` track. Original architecture: 2026-07-05. Autonomous backbone revision: 2026-07-12. Sections §9 onward become executable only after the spec-landing/ratification gate in §9.0 merges; once admitted, they supersede inconsistent estimates, completion language, and launch instructions in §§0-8. The earlier sections remain as design history and already-landed phase context.

**Authority:** subordinate to `docs/governance/SOVEREIGN_MANIFEST.md` for architecture and invariants, `docs/governance/ACTIVE_TRACK.yaml` for current intent and surface ownership, and code plus executable receipts for behavior. `docs/vision_maps/NORTH_STAR.md` supplies the why but owns no runtime rule or state (`docs/vision_maps/NORTH_STAR.md:3-6`; `docs/governance/CANONICAL_DOC_STACK.md:16-28,52-80`).

**Trust rule:** if this file disagrees with `make onboard`, the active-track owner, a receipt, or executable code, those owners win. Start implementation only from a freshly fetched `github/main` descendant containing audit commit `6965d38d`, the later durable-invoker fencing repair, and the merged §9.0 spec/track ratification. The checked-out July 11 WIP branch is a spec-authoring surface, not an admissible implementation base. Prove the base with the §10.1 commands and the pinned spec digest.

**Current measurement:** the frozen LangGraph 1.2.4 gauntlet graded 31.00/100 with 39/41 rows gapped; the July 12 harness council then confirmed fail-open scoring paths that can inflate that number. Reproduce rather than quote it: `bash scripts/governance/run_python_with_repo_env.sh scripts/governance/dharmagraph_parity_gauntlet.py --check`, then inspect `reports/governance/dharmagraph_parity/PARITY_MATRIX.md` and active-track cards 46-49. The number is a compatibility score inside that rubric, never “31% of Dharma capability.”

---

## §0 How to use this spec

- Each phase is independently shippable with its own acceptance criteria and kill criterion. Do NOT start phase N+1 until phase N's acceptance criteria have receipts (test output, commit hash, chaos-run log).
- Before any build work: run `make onboard`, read `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, check `INTERFACE_MISMATCH_MAP.md` for the module pairs you touch.
- **This campaign already has an active track:** `dharmagraph-engine-2026-07`. Extend that track; do not create a competing track or spec. Any newly required file surface must be admitted to the existing track before it is edited. Sibling-track surfaces (`coordination/**`, `archive.py`, `organism.py`, onboarding, merge authority) are reached only through their owners.
- Doctrine that binds every phase: extend existing owners, never weaken a gate, no new truth stores, runtime receipts never enter git, zero trained weights until the arena produces labels.

## §1 Original 2026-07-05 baseline (historical; §10 is current)

The one-sentence target — *"a cyclic, typed-state, crash-resumable graph runtime where every superstep emits a hash-chained receipt, every transition passes a telos gate, and the runtime's own topology is evolved under diversity-preserving selection with hermetic fitness"* — is the ROADMAP, not the current state. Devin's review caught the over-claim; verified clause by clause:

| Claim | Status today | Evidence |
|---|---|---|
| Per-dispatch evidence receipt | **TRUE** | spine dispatch default-on; one `EvidenceReceipt` per dispatch → `delegation_runs.receipt_json` (`spine/persistence.py:66-68`) |
| …hash-chained | **FALSE** | `EvidenceReceipt` is unchained (`spine/receipt.py:40-129`); the chain lives on `VerifiedMachineReceipt` (`receipt.py:217-288`), emitted by a governance check, not by dispatch; `dharma_swarm/merkle_log.py` exists separately for archive entries. Three receipt surfaces, not one. |
| Every transition passes a telos gate | **TRUE** | `TelosGatekeeper` CORE_GATES (`telos_gates.py:237-268`) invoked in-path (`agent_runner.py:2163`, blocks on BLOCK) |
| Crash-resumable dispatch | **FALSE** | in-flight `delegation_run` orphans on kill -9; dispatch lives only as a detached asyncio task (`orchestrator.py:2403-2407`); no boot reconciler for `delegation_runs` |
| Cyclic typed-state graph engine | **FALSE** | `CompiledWorkflow` is real BSP (waves + checkpoint, `workflow.py:234-338`) but acyclic-by-construction (`:252-255`), dict-state, static steps |
| Runtime evolves its own topology | **FALSE (by doctrine)** | `DarwinEngine` evolves code diffs, zero `topology_genome` references in `evolution.py`; the topology arena (`coordination/orchestrator_v1.py`) is deliberately walled off ("never mutates production routing") per arena-v1 zero-weight doctrine. Wiring it live is a capability DECISION (§ Phase 6), not a refactor. |

Accurate current-state sentence: *a telos-gated, per-dispatch-receipted runtime with a self-modification engine over code diffs and a walled-off hermetic topology arena.* Still unique in the field — but the six phases below are what earn the target sentence.

Fragmentation inventory (all verified):
- **Executors (5+):** SwarmManager+Orchestrator (hot path, ad-hoc asyncio, 3,225+3,221 LOC); CompiledWorkflow+topology_genome (good BSP, tested, NOT on hot path); workflow_graph+durable_execution (orphaned duplicate — zero production importers, still CI-tested); cascade LoopEngine (checkpointed, deletes checkpoints on convergence `cascade.py:259,303-304`); fs_substrate/stage_executor (untested); langgraph_parity (test-only clone).
- **Checkpoint mechanisms (3):** CompiledWorkflow inline non-fsync `write_text` (`workflow.py:391-392`); `checkpoint.CheckpointStore` atomic tmp+rename+fsync but loop-shaped schema (`checkpoint.py:212-288`); `durable_execution.DurableWorkflow` atomic + full-DAG restore + spine receipt hook (`durable_execution.py:218-345`) — the best one, orphaned.
- **Workflow compilers (3):** `WorkflowDefinition.compile()` (workflow.py); `OrchestrationGenome.compile()` (`topology_genome.py:87-133`); `compile_workflow_from_vision()` inside the 5,255-line `thinkodynamic_director.py:3542`.
- **Recovery (partial, wrong layer):** `operator_bridge.recover_stale_tasks` (`operator_bridge.py:748`) + `_mirror_runtime_recovered` (`:1359`, writes `status="recovered"` `:1372`) recover operator-bridge tasks and mirror to `task_claims`; `orchestrator.py:3196-3219` recovers claims that never started. **Nothing reconciles `delegation_runs` after process death.** No periodic heartbeat writer exists (`heartbeat_claim_sync`, `runtime_state.py:2062`, has zero production callers); `delegation_runs` has no heartbeat column (heartbeat hides in metadata as `last_heartbeat`, `operator_bridge.py:657`).
- **Quality floor:** no mypy; pyright basic; no coverage floor; mutmut scoped to ONE file (`pyproject.toml:76`); ratchet `silent_exception_swallows=244` baseline vs ~975 by conservative sweep (metric undercounts ~4x); `orchestrator.py` at 3,221 lines vs ~3,215 module-budget ceiling — **it cannot absorb new code; all new logic goes in new modules.**

## §2 Target architecture — DharmaGraph v1

**Package:** new `dharma_swarm/graph/` (NOT `spine/` — spine has a guarded narrow charter and its sqlite-declaration gate; `graph/` starts clean under the 1000-line new-module budget). Dependency direction: `graph/` imports `spine/` types; never the reverse. Library floor applies to `graph/` only from day one: mypy strict, coverage floor, 500-line module budget, `__all__`, semver as an extractable package.

**Original durability hypothesis (superseded by §§11-12 where inconsistent):** snapshot-per-superstep + the receipt log as side-effect journal. The design hypothesis was:

> One `BEGIN IMMEDIATE` transaction per superstep commits {checkpoint record, task claims, dispatch-intent rows}; `invoke_agent` memoizes on receipt under a deterministic idempotency key; a boot reconciler requeues or quarantines orphans; retry-exhausted rows are quarantined-and-reported, never hidden.

- Outbox = existing `delegation_runs` row (intent inserted in the superstep transaction — control state and dispatch intent can never disagree; kills torn supersteps).
- Memo = existing `receipt_json`: check-before-execute can suppress a bounded replay when the result is recoverable. It is not a general exactly-once guarantee. Retry identity, ambiguous world effects, missing persistence/identity, and unrepresentable results are corrected in §§11-15.
- SQLite: WAL + `synchronous=NORMAL`; `FULL` (or WAL checkpoint) on the superstep-commit transaction; single-writer discipline; Litestream v0.5 on the VPS.

**Engine primitives (each annotated with what it steals and where it lands):**

| Primitive | Steals from | Lands on |
|---|---|---|
| Versioned channels + reducers + per-node `versions_seen` scheduling | LangGraph core semantics (LastValue one-write-per-step conflict detection; node re-fires when a subscribed channel's version advances; halt when nothing advances) | `graph/channels.py`, `graph/scheduler.py`; replaces dict-state in the wave engine. **One mechanism = typed state + legal cycles + deterministic conflict detection** — the DAG-only limit is a scheduling-predicate change, not a rewrite |
| Pending-writes journal beside atomic checkpoints | LangGraph `checkpoint_writes` (succeeded siblings in a failed superstep never re-run) | `delegation_runs` rows with receipts ARE the pending writes |
| Cycles with telos-gated iteration budgets | LangGraph `recursion_limit`, upgraded: budget exhaustion routes through a telos gate decision | scheduler + `telos_gates.py` (in-path, the differentiator) |
| Send-style dynamic fan-out + deferred fan-in | LangGraph `Send` + `defer=True` | required by SWARM/SUPERVISOR/SUBAGENTS_AS_TOOLS; task board already does dynamic-N (`swarm.py:1147`) |
| Versioned checkpoint lineage → fork | LangGraph UUID6 ids + `parents` map + `source="fork"` | stop deleting checkpoints on convergence; `topology_states.checkpoint_id` (free text today, `runtime_state.py:88`) becomes a real reference |
| Interrupt-as-write (HITL) | Already own it, richer than LangGraph: `InterruptGate` APPROVE/REJECT/MODIFY + timeout (`checkpoint.py:78-181`) | graduate from cascade-only into `graph/` |
| Effect-handler seam | Composable effect handling for LLM scripts (ACM LMPL 2025) + anyio structured concurrency | nodes request effects; handler stack = gate→receipt→execute; same graph runs under live/record/replay/deny-all handlers — enables DST and hermetic fitness cheaply |
| Streaming = tailing the receipt log | Durable Streams / resumable-stream pattern | receipts get monotonic offsets; AG-UI, A2A task states, token streams become thin renderers |

**The narrowest integration seam (verified):** `_orch_invoker` inside `orchestrator._run_task_via_spine` (`orchestrator.py:2471-2524`), around the `runner.run_task` await at `:2477`. The `AgentInvoker` protocol (`spine/invoke.py:19-33`) explicitly permits wrapper invokers doing arbitrary work before/after — zero signature changes, A2A invoker untouched.

## §3 Phases

Effort: S = days, M = 1–2 weeks, L = multi-week. Owner suggestions assume Devin and a fresh Claude instance working in parallel lanes; anything touching hot-path files needs `[impact-checked]` / `DHARMA_UPLIFT_ACK` (list in `scripts/uplift_guards/hotpath_guard.py:16-42` — includes orchestrator.py, swarm.py, evolution.py, cascade.py, telos_gates.py).

### Phase 0a — Delete the dead engines (S; free win; good Devin starter)
- Delete `dharma_swarm/workflow_graph.py`, `tests/test_workflow_graph.py`. Before deleting `dharma_swarm/durable_execution.py` + its tests, ABSORB into `dharma_swarm/graph/checkpoint.py`: the fsync'd full-DAG `checkpoint()/restore()` (`durable_execution.py:218-308`) and the `_record_runtime_receipt` spine hook (`:324-345`). Reuse the atomic-write PATTERN, not the loop-shaped `LoopCheckpoint` schema (Devin's correction — `checkpoint.py`'s type is fitness-shaped, wrong for dispatch).
- Update `tests/test_runtime_truth_spine_recovery.py` (imports durable_execution) to the new home.
- **Acceptance:** grep shows zero imports of deleted modules; absorbed checkpoint/restore covered by ported tests; full suite green.
- **Kill criterion:** any non-test importer discovered → stop, map it first.

### Phase 0b — Run-level reconciliation + memoized dispatch prototype (S/M; historical phase)
- New module `dharma_swarm/graph/durable_invoker.py` (new module because orchestrator.py is at its module-budget ceiling): wraps `_orch_invoker`; applies `try_begin_idempotent_side_effect`/`complete_idempotent_side_effect` around the provider call using the existing `side_effect_key`; checks `receipt_json` before executing (memo hit → return prior receipt, no provider call).
- Reconciler: GENERALIZE the existing pattern (Devin verified: `operator_bridge.recover_stale_tasks` + `_mirror_runtime_recovered` already do this for bridge tasks/claims) down to `delegation_runs`. Owner: `SwarmManager` — once at end of `init()` (`swarm.py:551`) + periodically in `tick()` beside `reap_orphaned_tasks` (`swarm.py:2289`, same idiom, wrong database). NOT the API lifespan (best-effort/cancellable, `api/main.py:157-166`); NOT a cron (second process fighting the single writer).
- Boot scan (single host ⇒ anything in-flight at boot is orphaned by definition): `delegation_runs.status IN ('claimed','running') AND quarantined_at IS NULL`; `task_claims.status IN ('claimed','running') AND recovered_at IS NULL AND stale_after < now`. Classify with EXISTING vocabulary: never-ran → `failure_code='claim_timeout'` requeue path; ran-and-died → terminal fail or requeue mirroring `_handle_task_failure` (`orchestrator.py:1987-2055`); retry-exhausted → quarantine stamp per `loop_closure_quarantine.py` convention (never hidden, always tallied). Write `recovered_at` (its first writer on this path). Timestamps compared tz-aware in Python (the `parse_ts` convention, `loop_closure_quarantine.py:48-59`).
- Add the heartbeat: promote `last_heartbeat` out of metadata; executing tasks heartbeat at cadence ≤ stale_after/3 (wire the orphaned `heartbeat_claim_sync`, `runtime_state.py:2062`).
- Triage exception swallows on THIS path only (dispatch/persist/reconcile) — resume is meaningless on a path that swallows; the global ~975-swallow cleanup is Phase 5's problem.
- **Acceptance (historical bounded gate):** simulated kill window → reconcile → orphan requeued-or-quarantined, `recovered_at` stamped, and zero duplicate calls for the memoizable fake-provider case. This did not prove arbitrary effect safety or a real OS-process restart; the replacement gauntlet is §15.
- **Kill criterion:** chaos test shows double-execution or silent loss → do not proceed to any later phase.

### Phase 1 — Differential oracle + DST harness (M; guard rails BEFORE migration; parallel-friendly)
- Devin's correction, adopted: the "parity harness" is a self-graded clone (own docstrings: "intentionally avoids importing LangGraph"); langgraph 1.2.4 is locked but not installed; NO oracle exists. This phase is net-new work and must precede the god-class migration so it can guard it.
- Build: `[test-oracle]` extra installing langgraph 1.2.4; dual-run harness executing the parity scenarios (swarm handoffs, supervisor output modes, isolation) through BOTH engines; diff semantic outcomes (active agent, message visibility, final state), not text. CI job, advisory first, blocking once stable.
- Seed the DST skeleton: virtualize time/randomness/dispatch-order behind the effect-handler seam (even a minimal handler injection point in `graph/` suffices at this stage); fault menu = task death mid-superstep, torn checkpoint, interrupt-during-retry; failing seeds replay exactly. (FoundationDB/Antithesis discipline; no agent framework ships this — a DST-proven recovery claim is one LangGraph cannot make.)
- **Acceptance:** oracle runs both engines on ≥12 scenarios in CI with a diff report artifact; ≥1 real divergence found-and-adjudicated (spec bug or clone bug — either is a win); DST reproduces Phase 0b's chaos findings from a seed.
- **Kill criterion:** none (pure guard-rail); but Phase 2 does not start until the oracle is in CI.

### Phase 2 — Crown the engine; strangle the god-classes (M/L)
- Route `_dispatch_topology_genome` (`orchestrator.py:225-264`) through the existing-but-orphaned bridge `execute_topology_genome_workflow` (`workflow.py:612-682`). Verified graduation order: FAN_OUT/BROADCAST/PIPELINE/FAN_IN migrate cleanly today; SWARM/SUPERVISOR/SUBAGENTS_AS_TOOLS are BLOCKED until Phase 3 (they need cycles/Send — that's the finding that justifies the engine).
- Consolidate the three compilers: `WorkflowDefinition.compile` stays; `OrchestrationGenome.compile` delegates into it; extract `compile_workflow_from_vision` out of `thinkodynamic_director.py:3542` into `graph/compile.py` (also carves the 5,255-line god-file).
- Consolidate the three checkpoint mechanisms onto the absorbed atomic store (Phase 0a) with a dispatch-shaped record; CompiledWorkflow's bare `write_text` checkpoint replaced.
- Graduate from `langgraph_parity/` into `graph/`: `SwarmState`, `TransferReceipt`, handoff policy, isolation policy, readiness gates (`langgraph_parity/state.py:17-216`, `isolation*.py`, `readiness*.py`). Benchmarks stay test-only.
- Tests pinning behavior: `tests/test_topology_execution.py` (:40, :64, :112, :158), `test_orchestrator*`, `test_workflow.py` — every migrated branch keeps them green under the oracle.
- **Acceptance:** ≥4 topology branches on the graph engine in production config; one checkpoint mechanism; one compiler entry point; oracle green; module budget green (orchestrator.py line count DOWN).
- **Kill criterion:** oracle divergence or behavior diff unexplainable as a bug fix → revert the branch slice.

### Phase 3 — The four primitives (L; the actual engine build)
- Channels/reducers + `versions_seen` scheduling in `graph/channels.py` + `graph/scheduler.py`; port waves onto the channel-activation predicate; cycles become legal with telos-gated iteration budgets; `Send` + deferred fan-in; versioned checkpoint lineage with fork (stop deleting on convergence — `cascade.py:259,303-304`).
- Then migrate SWARM/SUPERVISOR/SUBAGENTS_AS_TOOLS using the graduated state schemas.
- Library floor enforced on `graph/` in CI from the first module: mypy strict, `--cov-fail-under` (start 85%), widen mutmut to `graph/` (per pyproject's own "widen as the gate is adopted" note, `pyproject.toml:72`).
- **Acceptance:** cyclic scenario (supervisor loop) runs, crashes mid-cycle, resumes from checkpoint, forks from a historical checkpoint; oracle parity on all scenario classes; token-level streaming demonstrated by tailing the receipt log.
- **Kill criterion:** DST finds unrecoverable states in the cyclic scheduler → freeze migration at DAG topologies until fixed.

### Phase 4 — Receipt unification + upgrade rungs (S/M; calendar-driven — EU AI Act Art. 12 applicable 2026-08-02; can run parallel to 2/3)
- Rung 0: UNIFY the three receipt surfaces (Devin's finding): every dispatch `EvidenceReceipt` also appends to the `VerifiedMachineReceipt` hash chain (or the merkle_log) — making "per-dispatch AND chained" true for the first time.
- Rung 1: wrap receipts as in-toto Statements in DSSE envelopes (the Acta IETF drafts define a predicate type for signed hash-chained agent decision receipts — the receipt becomes a standards-track artifact); SPIFFE-style per-seat identities when multi-seat matters.
- Rung 2: linear chain → Merkle log on C2SP tlog-tiles (extend `merkle_log.py`; O(log n) inclusion proofs). Rung 3: signed tree heads (tlog-checkpoint). Rung 4: witness cosigning (tlog-witness) — the cryptographic form of the One Wire quorum doctrine; no second trust model.
- **Acceptance:** a third party can verify one dispatch receipt offline (rung 1) and prove log inclusion (rung 2) from published artifacts.
- **Kill criterion:** if rung 0 adds >5ms p50 to dispatch, buffer the chain append off the hot path (async batch) before proceeding.

### Phase 5 — Ratchet the REAL floor (M; parallel-friendly; mostly mechanical)
- Re-baseline `silent_exception_swallows` to the honest count (~975 by conservative sweep vs 244 baseline) with the counter definition documented; then carve down top offenders (swallows are the phantom-generator).
- Widen mutation testing beyond one file (graph/ + spine/); coverage floor beyond graph/ where cheap; begin decomposition issues for the >500-line worst offenders that Phases 2–3 didn't already carve.
- **Acceptance:** ratchet counters re-baselined honestly and monotone thereafter; mutmut ≥ 2 packages.

### Phase 6 — Evolution closes the loop (M; LAST; capability decision, operator-gated)
- Fork-from-checkpoint registers as a mutation operator in `ZeroWeightOrchestratorV1.mutate` (`coordination/orchestrator_v1.py:131-158`, new op in the choice list at `:133-135`, lineage already plumbed via `Lineage.mutation_op`, `coordination/genome.py:85-87`). Forked-run fitness enters `DarwinEngine.evaluate` (`evolution.py:1632`, sets `actual_fitness` `:1772`) → `archive_result` (`:1876`) → MAP-Elites archive. GEPA/DSPy-style program evolution lands as one more operator over the archive (intra-node gradient; MAP-Elites preserves the Krogh-Vedelsby diversity term; zero trained weights — Arena v1 doctrine holds).
- Every evolution admission emits an admission-certificate receipt (test statistic, error budget, decision) into the Phase 4 log (the SEA pattern).
- **The wall stays up by default.** Wiring arena elites into PRODUCTION routing lifts the zero-weight doctrine — that is an operator ratification (align with organism-rewire D4 sequencing: only after an ungameable external gradient exists). This spec explicitly does NOT authorize it. The permanent citation for why the order matters: DGM Appendix F — an evolved agent deleted the logging markers used to detect its hallucinations and scored perfect. Self-improving systems attack their own telemetry; externally-witnessed receipts (Phase 4) are the enabling condition for safe self-evolution, not decoration.
- **Acceptance:** fork operator produces arena-scored offspring with receipts; zero production-routing changes.

## §4 Division of labor (suggested)

| Lane | Phases | Why |
|---|---|---|
| Devin | 0a, 0b reconciler+tests, 5 | Self-contained, test-heavy, pattern-generalization work with crisp acceptance criteria; Devin's review already mapped the recovery pattern |
| Fresh Claude instance | 0b durable_invoker seam, 1 oracle+DST, 2, 3 | Requires holding the whole engine design + gate landscape; hot-path ack discipline |
| Either, parallel | 4 | Standards-implementation work, independent of the engine internals after rung 0 |
| Operator only | Phase 6 wall decision, track ratification, VPS host | Capability decisions and infrastructure |

Coordination rules: one PR per phase slice; every PR cites this spec section; BR-id collision pre-flight per CLAUDE.md; the oracle (Phase 1) gates every Phase 2/3 merge once it exists.

## §5 What we deliberately do NOT build

- Temporal-style replay (determinism tax, history caps, sovereignty loss; DBOS proves embedded-DB durability suffices).
- A LangGraph wrapper as the engine (parity contract's own non-goal; puts DarwinEngine outside its own mutation surface).
- Events-over-edges geometry (LlamaIndex-style; Send + typed graph covers it with better replay determinism and cleaner fitness attribution).
- Model-driven flow ("let the LLM pick the topology" — hostile to receipted, gated execution).
- Trained edge weights / RL orchestrators (GPTSwarm-style) — post-label territory, arena doctrine.
- A new truth store of any kind — every durability structure above is a column, a row-discipline, or a log that already exists.

## §6 Dovetail with the active portfolio (historical registration context)

- The proposed track was admitted as `dharmagraph-engine-2026-07`. Its live owned surfaces, blockers, non-goals, and closeout state come only from `docs/governance/ACTIVE_TRACK.yaml`; never recreate them from this historical paragraph.
- `loop-closure-2026-06`: Phase 0b IS the durable half of Loop-1 closure (dispatch dropoff becomes a recoverable state, not a corpse label); the reconciler's quarantine path reuses that track's tool and reporting doctrine.
- `orchestration-arena-v1-2026-06`: Phase 6 extends its surfaces through its own next-items; zero-weight doctrine preserved.
- `organism-rewire-2026-07`: D4 sequencing (no standing DarwinEngine unlock before external gradient) binds Phase 6; the VPS item is what makes Phase 0b's reconciler run against a live daemon.
- Receipts upgrade (Phase 4) feeds the `revenue-external-humans-served` gap: EU AI Act Art. 12 (applicable 2026-08-02, ≥6-month log retention, €15M/3% penalties) + AI-agent insurance (AIUC et al. pricing premiums off audit evidence) is the story that makes verifiable execution sellable.

## §7 Historical proposed track skeleton (already admitted; do not reuse)

```yaml
- id: dharmagraph-engine-2026-07
  name: DharmaGraph — sovereign durable graph runtime consolidation
  serves: substrate-nativeness
  status: PROPOSED
  owned_surfaces: [dharma_swarm/graph/**, dharma_swarm/workflow.py, dharma_swarm/topology_genome.py,
                   dharma_swarm/checkpoint.py, tests/test_workflow*.py, tests/test_topology_execution.py,
                   docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md]
  criteria:  # rigorous-only; existence checks are not closure
    - phase0b_chaos_receipt (test_passes: kill -9 → reconcile → zero double-execution)
    - oracle_in_ci (test_passes: dual-run diff job green on ≥12 scenarios)
    - crowning_line_count (commit_on_main: orchestrator.py LOC strictly decreases)
    - receipt_rung0 (test_passes: every dispatch receipt chained)
  non_goals:
    - No production topology-evolution unlock (Phase 6 wall stays; operator decision)
    - No new truth stores; no gate weakening; no trained weights
```

## §8 Key references (curated from ~150; full lists in the convoy lane reports)

**Durability:** DBOS architecture + SQLite default (docs.dbos.dev/architecture; dbos.dev/blog/new-in-dbos-june-2026) · Temporal Python sandbox + limits (docs.temporal.io/develop/python/python-sdk-sandbox; docs.temporal.io/workflow-execution/limits) · Restate journal design (restate.dev/blog/building-a-modern-durable-execution-engine-from-first-principles) · LangGraph durable-execution + persistence (docs.langchain.com/oss/python/langgraph/durable-execution) · Diagrid "checkpoints are not durable execution" (diagrid.io/blog/checkpoints-are-not-durable-execution-...) · ZenML no-journal-replay (zenml.io/blog/no-journal-replay) · Vanlightly, Demystifying Determinism (jack-vanlightly.com, 2025-11-24) · River/Oban/graphile-worker rescuers · sqlite.org/wal.html · fly.io/blog/litestream-v050-is-here · Cloudflare Project Think (blog.cloudflare.com/project-think).

**Engine anatomy:** LangGraph source at main — checkpoint base, checkpoint-postgres DDL (pending writes), channels/{last_value,topic,binop}.py, types.py (Send/Command/interrupt/Durability/StreamMode) · deferred nodes + node caching changelogs · pydantic-graph · Microsoft Agent Framework workflows · LlamaIndex Workflows (the events-vs-graphs argument) · Antithesis DST (antithesis.com/docs/resources/deterministic_simulation_testing) · Composable Effect Handling for LLM scripts (dl.acm.org/doi/10.1145/3759425.3763396; arXiv:2507.22048) · anyio/Trio structured concurrency · Durable Streams (electric-sql.com, 2025-12-09) · GEPA (github.com/gepa-ai/gepa; dspy.ai).

**Moat/verification:** Darwin Gödel Machine (arXiv:2505.22954 — Appendix F) · AlphaEvolve (deepmind.google/blog/alphaevolve) · ADAS (arXiv:2408.08435) · AFlow (arXiv:2410.10762) · MASS (arXiv:2502.02533) · SEA anytime-valid admission certificates (arXiv:2607.00871) · Acta signed receipts IETF drafts (datatracker.ietf.org/doc/draft-farley-acta-signed-receipts) · in-toto/DSSE/SLSA · C2SP tlog-tiles / tlog-checkpoint / tlog-witness (github.com/C2SP/C2SP) · transparency-dev/tessera; litetlog · Sigstore/Rekor · SPIFFE-for-agents (WIMSE) · Microsoft Agent Governance Toolkit (github.com/microsoft/agent-governance-toolkit) · PunkGo (arXiv:2602.20214) · EU AI Act Art. 12/19 (artificialintelligenceact.eu/article/12) · FINRA 2026 oversight report · AIUC (aiuc.com) · OTel GenAI semconv (Development status — telemetry, not evidence).

---

## §9 July 12 revision: the locked autonomous campaign

### 9.0 Pre-campaign landing and ratification gate

This revision is currently authored on a divergent WIP worktree. An autonomous
implementation run cannot both start from clean `github/main` and discover
unmerged instructions from that worktree. Therefore the first action is a
**governance-only spec-landing change**, not DG-00 implementation:

1. review and merge this revised spec into canonical main;
2. amend the existing `dharmagraph-engine-2026-07` active-track entry—never
   create another track—to admit the revised packet DAG, new named tests,
   campaign-evidence validator, and any coordinated surfaces; update its claim
   boundary, phase/next-item order, completion criteria, and obsolete
   “exactly-once” language rather than leaving two binding campaigns;
3. explicitly ratify or reject the changed phase order: versioned IR and an
   authoritative journal before a new durable native engine, then effects/HITL,
   shadow integration, and the VentureCell slice;
4. resolve `DGB-D2` up front: either approve the minimum graph execution-journal
   role/schema inside the configured isolated `runtime.db`, or constrain the
   campaign to IR/design work and accept that DG-03 onward is blocked;
   record the accepted architecture in the proper architecture/ADR owner as
   well as the active-track intent owner;
5. explicitly admit the non-effecting shadow seam or keep DG-06 blocked;
6. resolve `DGB-D8` by naming the canonical authority-evaluator composition,
   operator-authentication path, lease expiry/revocation owner, decision CAS,
   and receipt owner before DG-05 can launch;
7. pre-land active-track card 49 through the `onboard-one-door` owner, because
   its interpreter/CI changes are outside DharmaGraph ownership;
8. record the merged spec commit and SHA-256 digest in the active-track decision
   text and launch packet.

No runtime code, schema migration, fault injection, or autonomous campaign may
start before this gate is merged and re-derived by `make onboard`. The current
user request authorizes writing the proposal; it is not silently treated as the
specific persistence, phase-order, cross-track, or production-shadow
ratifications above. If the operator rejects any choice, revise the DAG before
launch rather than letting a builder improvise around it.

### 9.1 Mission

Run a phase-gated sequence of autonomous multi-hour epochs that turns the
neutral graph candidate into a **Dharma Backbone v0 candidate** without
changing live routing. The whole-campaign finish line is one versioned,
ontology-bound VentureCell that compiles into a
portable DharmaGraph definition, executes through the native durable engine in
shadow mode, survives a real process death, journals every effect, pauses and
resumes through a durable authority decision, emits a causally complete receipt
chain, imports a provenance-bearing historical outcome, and demonstrably
changes the next shadow WorkPacket/routing/budget decision.

No single 12-18 hour epoch is expected to deliver that entire stack. Each epoch
has its own terminal evidence tier in §13, begins from the last admitted main
commit, and may advance into the next epoch only when time/budget and independent
evidence remain healthy. This corrects the original multi-week engine estimate
instead of hiding it behind a bigger prompt (§3 Phase 3).

This is deliberately higher than a LangGraph clone. The target is:

```text
DharmaGraph
  = durable graph execution
  + ontology/VentureCell compilation
  + constitutional authority and effect control
  + causal receipts and external outcomes
  + safe, operator-gated adaptation
```

The operating-company loop says closure exists only when an outcome changes
the next packet, allocation, route, playbook, or evolution proposal; merely
rendering the outcome is not closure
(`docs/vision_maps/2026-05-07_operating_company_kernel.md:45-70`). The North
Star requires heterogeneous loops, diversity preservation, and real gated
outcomes rather than one homogenized loop
(`docs/vision_maps/NORTH_STAR.md:30-60`). Those are acceptance constraints,
not decorative vision language.

### 9.2 Terminal claim boundary

The strongest autonomous terminal verdict is
`BACKBONE_V0_CANDIDATE_CLOSED_NOT_PROD`. It means the named local,
multi-process, failure-injected, shadow-mode evidence passed. It does **not**
mean:

- production routing was cut over;
- arbitrary world effects are exactly-once;
- the active track reached 100/100 LangGraph compatibility;
- an external execution backend was adopted;
- topology evolution or Darwin apply was enabled;
- a live customer/world outcome closed the organismic loop;
- the trust gate opened.

The six anti-mythology conditions remain binding: a real organ needs a
producer, schema, durable output, consumer, executable check, and non-toy run
(`docs/vision_maps/2026-05-07_operating_company_kernel.md:344-368`). A missing
real input or provider is `NEEDS_HOST` or `BLOCKED_WITH_EVIDENCE`, never a
fixture-backed promotion.

### 9.3 Campaign duration and autonomy

Design each controller epoch for a 12-18 hour uninterrupted window with a
24-hour hard wall-clock ceiling unless the operator supplies a smaller cap.
Time is a resource cap, not a completion condition. The controller may finish
an epoch early only on a valid tier/verdict, and time expiry produces
`INCOMPLETE_WITH_EVIDENCE`, never “best effort complete.” Starting another
epoch requires a clean admitted base and remaining authority; the controller
does not roll an unfinished mega-branch forward. No new model spend,
infrastructure spend, deployment authority, or external-write authority is
implied; the run inherits only already-approved provider routes and local write
permissions. Model/provider resolution must use the canonical routing door and
never introduce hardcoded model strings
(`docs/ops/MODEL_KEY_ROUTING.md:7-24,72-88`).

## §10 Fresh verified baseline

### 10.1 Admission base

The controller must begin from a clean isolated worktree based on freshly
fetched `github/main`, not the July 11 WIP checkout and not a stale
`origin/main` bundle:

```bash
git fetch github main
git merge-base --is-ancestor 6965d38d github/main
git log -1 --format='%H %cI %s' github/main
git show github/main:docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md | sha256sum
git show github/main:docs/governance/ACTIVE_TRACK.yaml | rg -n 'dharmagraph-engine-2026-07|DGB-D2|DG-00'
git status --short
```

Expected: the ancestry check exits 0, the exact base SHA is recorded, and the
new worktree is clean. The printed spec digest must equal the ratified digest
recorded by §9.0, and the active-track projection must contain the admitted DAG
and decisions. The base must include the post-audit durable-invoker
ownership-token/fencing repair. Re-derive that with
`git log -- dharma_swarm/graph/durable_invoker.py dharma_swarm/runtime_state.py`;
do not copy code from the current WIP branch over the newer implementation.

Install the declared development and oracle extras in the campaign environment
before grading anything:

```bash
make onboard
command -v uv
uv sync --frozen --extra dev --extra test-oracle
make agent-build-preflight
```

All commands must exit 0. Missing tooling/dependencies are a failed admission,
not skipped parity evidence. The oracle extra is explicitly test-only in
`pyproject.toml:50-56`.

### 10.2 Mandatory state and fault isolation

No campaign process may open the operator's live runtime, ontology, task-board,
or receipt database for writes. Create a unique external campaign root under
`~/.dharma/experiments/dharmagraph/<mission-id>/` with:

```bash
export DHARMA_CAMPAIGN_ROOT="$HOME/.dharma/experiments/dharmagraph/<mission-id>"
```

```text
state/runtime.db              # writable synthetic/campaign execution state
inputs/runtime-history.db     # sanitized real snapshot, mounted/read as read-only
receipts/                     # derived campaign evidence, never committed
faults/                       # subprocess logs and deterministic fault traces
artifacts/                    # candidate outputs and rollback evidence
```

Every store, worker, subprocess, and test receives the explicit campaign path;
no default constructor or inherited live-state environment is allowed. DG-00
must add a preflight that resolves the configured live runtime path and campaign
path, checks they are different paths/inodes, opens the historical snapshot
read-only, and refuses symlinks escaping the campaign root. Fault tests use
throwaway copies beneath this root. `SIGKILL`, disk-full, corruption, lock, and
migration tests never target the snapshot or live state. Raw/sanitized runtime
data and receipts never enter Git.

Any unexpected mtime, row-count, or digest change on a live state owner is a
hard red gate and immediate quarantine. A sanitized snapshot is an input
projection only; it cannot become a second writable truth owner.

### 10.3 Current behavioral baseline to re-prove

| Area | Current fact | Executable/source evidence |
|---|---|---|
| Neutral kernel | `GraphBuilder`/`CompiledGraph` are candidate/test-only and are not the production dispatch engine. | `dharma_swarm/graph/__init__.py:1-10`; `dharma_swarm/graph/types.py:1-12` |
| Scheduler | Ready tasks are awaited one by one; no true parallel overlap or structured sibling cancellation is implemented. | `dharma_swarm/graph/scheduler.py:234-319` |
| In-memory resume | `RunCheckpoint` carries channels and `versions_seen`, and resume checks a state digest. | `dharma_swarm/graph/types.py:110-139`; `dharma_swarm/graph/scheduler.py:179-205` |
| Persistent checkpoint | `GraphCheckpointStore` claims full-state durability but writes only a list of run/superstep/node/state-ref records. | `dharma_swarm/graph/checkpoint.py:41-71,90-147` |
| Production graph use | Production imports the graph package for the durable invoker and reconciler, not for neutral graph execution. | `dharma_swarm/orchestrator.py:2526-2553`; `dharma_swarm/swarm.py:1794-1809` |
| Effect safety | Missing store/identity can pass through; memo probe, unrepresentable result, and completion persistence paths can re-execute or fail open. | `dharma_swarm/graph/durable_invoker.py:615-703,705-725`; targeted tests must exercise every branch |
| Receipt targeting | Spine receipt persistence updates by `task_id`, which can touch more than one delegation run for a multi-run task. | `dharma_swarm/spine/persistence.py:50-75` |
| Heartbeat ownership | The reconciler refreshes every non-recovered in-flight claim rather than only leases fenced to the current worker. | `dharma_swarm/graph/reconciler.py:445-489` |
| Fork proof | One existing assertion is tautological and cannot support a fork claim. | `tests/test_graph_neutral_cycles_resume.py:140-148` |
| Ontology | `Outcome`, `ValueEvent`, and `VentureCell` objects exist, but the cell schema does not compile into a versioned graph runtime. | `dharma_swarm/ontology.py:1715-1799,1839-1879`; `rg -n 'VentureCell.*Graph|compile.*VentureCell' dharma_swarm tests` |
| WorkPacket vocabulary | Three separate `WorkPacket` classes already exist; this campaign must not add a fourth. | `rg -n '^class WorkPacket' dharma_swarm` |
| Compatibility audit | The frozen 1.2.4 gauntlet reports 31.00/100 and 39 gap rows; hardening cards show the headline can fall. | parity command in §0; `reports/governance/dharmagraph_parity/PARITY_MATRIX.md`; active-track cards 46-49 |

Before implementation, run the focused current suites and save raw exits and
environment metadata outside Git under the mission receipt root:

```bash
.venv/bin/python -m pytest -q \
  tests/test_graph_neutral_core.py \
  tests/test_graph_neutral_routing.py \
  tests/test_graph_neutral_cycles_resume.py \
  tests/test_graph_checkpoint.py \
  tests/test_graph_durable_invoker.py \
  tests/test_graph_reconciler.py \
  tests/test_graph_chaos_receipt.py
DHARMA_PYTHON="$PWD/.venv/bin/python" \
  bash scripts/governance/run_python_with_repo_env.sh \
  scripts/governance/dharmagraph_parity_gauntlet.py --check
```

No baseline failure may be erased with a skip, `xfail`, weaker assertion,
changed expected output, or hardcoded success.

## §11 Operator decision register and invariants

The campaign continues under the conservative default in this table. A
different choice requires a dated operator ratification in the active-track
owner; an implementation agent cannot infer it from this plan.

| ID | Decision | Default for this campaign | Pause condition |
|---|---|---|---|
| `DGB-D1` | Compatibility closeout | Keep the current 100/100-or-ratified-exclusion active-track blocker. Add a separate backbone-readiness scoreboard; never average them. | Any request to close/demote/rescope the parity blocker. |
| `DGB-D2` | Authoritative execution journal | **Must be resolved at §9.0. Recommended:** a graph-owned closure layer inside the configured isolated `runtime.db`, with one public unit-of-work API and explicit projections to legacy views. Alternative: extend existing tables plus that same atomic API. | No DG-03+ launch until the active-track/architecture owner ratifies one design, its closure role, schema, migration, and rollback. A second DB or second ontology/task/outcome owner remains forbidden. |
| `DGB-D3` | External engines | LangGraph and other systems are differential or bakeoff backends only. Native is the sole production candidate in this run. | Any production dependency, licensed server, persistent external journal, or permanent substrate choice. |
| `DGB-D4` | Production traffic | `off` and non-effecting `shadow` modes only. | Canary or cutover. |
| `DGB-D5` | Effects | Pure/local reversible effects only; world-changing effects run against fakes or deny-all handlers. | Posting, outreach, trading, payments, deployment, customer writes, destructive tools, or other irreversible action. |
| `DGB-D6` | Evolution | Generate shadow proposals only; zero archive-fitness or production-routing mutation. | Any Darwin apply, topology-elite promotion, or standing self-modification. |
| `DGB-D7` | Non-toy input | Use a sanitized real runtime-history snapshot supplied through an approved path. | If no real snapshot is available, finish code slices but mark the vertical proof `NEEDS_HOST`; fixtures cannot substitute. |
| `DGB-D8` | Canonical authority evaluator | **Must be resolved at §9.0. Recommended:** one graph `AuthorityEvaluator` adapter that composes existing TelosGatekeeper, authenticated operator decision, and `operator_core.execution_lease` expiry/revocation owners; it creates no new authority. | DG-05+ blocks until operator authentication, decision CAS, lease expiry/revocation, gate version, and audit receipt have one named evaluator contract. |
| `DGB-D9` | Offline model-call budget | Default shadow is replay-only with egress denied. A separately declared matched budget may authorize offline diagnosis calls on the sanitized snapshot. | No new model call when provider health, max calls/tokens/cost, data policy, and best-single control are absent from the launch receipt. |

The no-new-store question must be resolved precisely, not rhetorically. The
desired invariant is **one logical authority per fact**, global causal identity,
and explicit projection/reconciliation. A physical execution journal may be
architecturally necessary, but it may not become a second owner of ontology,
business outcomes, task truth, or receipts. The repo already permits distinct
canonical receipts by closure layer when correlation identity remains global
(`docs/governance/ANTI_SLOP_RULES.md:26-63`). That doctrine does not itself
override the stricter active-track non-goal; `DGB-D2` still requires
pre-launch ratification before a graph journal schema or unit-of-work lands.

Permanent invariants:

1. No effect executes without stable actor, authority, graph, thread, run,
   node-task, logical-effect, and attempt identities.
2. Persistence/identity/gate failure is fail-closed for effectful work.
3. An ambiguous irreversible effect is never blindly retried.
4. Current emergency revocations and expired warrants are re-evaluated before
   every resumed effect; an old checkpoint cannot carry stale authority.
5. A checkpoint cannot resume across incompatible versions without an explicit,
   deterministic, receipted migration.
6. A stale worker cannot commit after lease takeover.
7. A backend may schedule work but cannot redefine Dharma ontology, warrants,
   receipts, outcome truth, or promotion rules.
8. An outcome cannot influence learning if it was authored by the candidate
   adaptation or its scorer.
9. The shadow path never duplicates a production provider/tool call.
10. “Exactly once” is forbidden claim language. Describe the proven contract as
    at-least-once plus idempotency, reconciliation, and compensation unless a
    named effect class passes the full §15 matrix.

## §12 Dharma Backbone Contract v0

### 12.1 Layering

```text
Dharma semantic plane
  OntologyObj / VentureCell / WorkPacket refs / ExternalOutcome
           ↓ compile
Dharma constitutional plane
  telos / warrants / permissions / budgets / gates / operator authority
           ↓ bind
DharmaGraph IR
  GraphDefinition / RunManifest / NodeTask / EffectIntent / Checkpoint
           ↓ execute through capability contract
Execution backend
  native (candidate) | LangGraph oracle | future DBOS/Restate/Temporal probe
           ↓
Workers and transport
  local processes | A2A | NATS | future distributed workers
           ↓
Dharma evidence plane
  receipts / artifacts / checkpoints / outcomes / cost / lineage
           ↓ consume
review / allocation / routing / safe evolution proposal
```

Dharma owns every type above the execution-backend boundary. Backends are
replaceable machinery. The native scheduler earns default status through the
same receipts and failure tests, not through sovereignty rhetoric.

### 12.2 Serialized contracts

Public persisted contracts use strict Pydantic models (`extra='forbid'`) with
an explicit schema name and major version, canonical JSON, stable SHA-256
digest, UTC timestamps, and unknown-major refusal. Internal hot-path objects
may remain frozen dataclasses. Never serialize a Python callable or memory
address; persist a stable handler reference resolved through a versioned
registry.

Minimum types:

| Type | Required fields |
|---|---|
| `GraphDefinitionV1` | `graph_id`, semantic version, definition digest, input/state/output/context schemas, channels/reducers, nodes, edges/branches, entry/finish, default policy, migration policy |
| `NodeDefinitionV1` | stable handler ref/version, input/output schemas, destinations, retry/timeout/cancel policy, gate refs, effect class, cache declaration, metadata |
| `RunManifestV1` | thread/run IDs, graph definition/version/digest, parent/fork IDs, code commit/artifact digest, schema/prompt/model/tool/gate versions, operator, context digest, budgets, deterministic seed, virtual-clock policy |
| `AuthoritySnapshotV1` | actor/operator identity refs, warrant/lease refs, permission set, issue/expiry/revocation observations, gate-policy version/digest, evaluator version, observed time |
| `GateDecisionV1` | intent/effect ref, named gate/version, ALLOW/BLOCK/REVIEW, authenticated decider/evaluator, evidence/reason digest, decision CAS version, timestamp |
| `RunLeaseV1` | thread/run, worker owner, issued/expiry/heartbeat times, monotonic fencing token, revocation ref, CAS version |
| `NodeTaskV1` | task ID, run/node/superstep/task-index, input digest, policy ref, status |
| `TaskAttemptV1` | attempt ID, task ID, attempt number, worker/run lease refs, task fencing token, start/finish/error/cancel state |
| `PendingWriteV1` | run/task/attempt IDs, run and task fences, channel, value/artifact digest, source effect refs, status, barrier target |
| `EffectIntentV1` | stable `effect_id`, actor/authority/warrant, effect type/target, payload digest, provider idempotency key, gate decisions, compensation/reconcile policy |
| `EffectAttemptV1` | `attempt_id`, stable `effect_id`, attempt number, worker/fence, dispatch/ack/provider refs, result/error/ambiguity state |
| `InterruptRequestV1` | run/task/effect refs, requested authority, payload digest, allowed decisions, expiry, request receipt |
| `InterruptDecisionV1` | request ref/version, authenticated operator/evaluator, APPROVE/REJECT/MODIFY, replacement payload digest when modified, CAS version, decision receipt |
| `MigrationReceiptV1` | source/target graph, manifest, schema and checkpoint digests, migrator/version, preconditions, output digest, status/error, immutable source ref |
| `CheckpointV1` | full channels, channel versions, `versions_seen`, pending tasks/writes/effects, interrupt state, manifest and graph digests, parent checkpoint, state digest, run/task fences |
| `GraphEventV1` | thread-local monotonic offset, causal IDs, event type, before/after digests, receipt refs, timestamp |
| `ExternalOutcomeEnvelopeV1` | refs/digests to canonical ontology `Outcome`/`ValueEvent`/`Contribution`, source outside candidate path, observed time, witness, freshness, dedupe key, originating run/artifact links, decision-consumer link |
| `VentureCellCompileResultV1` | cell object/version/digest, linked policy refs, graph definition/digest, unresolved requirements, compiler version, receipt ref |

The graph digest includes node handler/version manifests, schemas, policies,
channel definitions, and topology. A prompt/model/tool/gate change may leave the
graph topology digest stable only if it changes the bound `RunManifest`; it may
never disappear from resume compatibility checks.

`CanonicalCodecV1` is part of the contract: normalize declared text inputs to
Unicode NFC, schema-normalize timestamps to UTC RFC 3339 `Z`, reject NaN and
infinities, represent binary/large values by typed content digest, and encode
the normalized object with RFC 8785 JSON Canonicalization Scheme. Digest fields
and explicitly declared observation timestamps are excluded from their own
digest; every other exclusion is a schema error. Unknown major or minor schema
versions fail unless a registered compatibility declaration/migrator names the
exact source and target. Tests use published canonicalization vectors plus
Unicode, float, timestamp, and key-order adversaries.

No checkpoint, task, handler argument, or outcome may deserialize through
pickle or import-by-payload. Enforce schema size/depth/item limits,
`max_inline_result_bytes`, content-addressed overflow through the existing
artifact owner, and fail closed rather than truncate or replace with null.
Secrets, raw prompts containing credentials, provider tokens, and PII are never
embedded in IDs/checkpoints/receipts; store governed references and redacted
digests. Cell/thread namespace plus authority checks apply to inspect, history,
stream, fork, resume, interrupt, and migration—not only start.

One `AuthorityEvaluator` protocol composes the ratified existing owners and
returns `AuthoritySnapshotV1` plus `GateDecisionV1` records. It authenticates
the operator, validates execution-lease expiry and revocation, evaluates current
telos/gate versions, uses CAS for one terminal interrupt decision, and emits an
audit receipt. A string field containing `APPROVED` is never authority.

### 12.3 Backend capability contract

Add a narrow protocol under `dharma_swarm/graph/backends/`:

```text
async capabilities() -> BackendCapabilities
async compile(GraphDefinitionV1) -> BackendPlan(plan_id, graph_digest)
async start(plan_id, RunManifestV1, input, request_key) -> RunHandle
async resume(run_id, checkpoint_id, request_key, migration=None) -> RunHandle
async inspect(thread_id, run_id) -> RunSnapshot
async history(thread_id, after_checkpoint=None) -> sequence[CheckpointSummary]
async fork(checkpoint_id, new_thread_id, new_run_id, request_key) -> RunHandle
async interrupt(run_id, InterruptDecisionV1, request_key) -> InterruptHandle
async stream(thread_id, after_offset) -> async events
async drain(run_id, deadline, request_key) -> DrainResult
async cancel(run_id, reason, request_key) -> CancelResult
```

Capabilities are explicit; unsupported operations fail with typed errors rather
than silently degrading. Mutating calls are idempotent on `request_key`; plan,
graph, thread, run, checkpoint, task, effect, and backend-native ID scopes are
declared and collision-tested. `thread_id` owns one linear mutable head;
same-head resume creates a new run attempt in that thread, while fork always
mints a new thread and run from an immutable parent checkpoint. Historical
checkpoints never resume in place over a newer thread head.

The native backend wraps the new durable run engine.
The LangGraph implementation is test-only and translates Dharma-owned IR into
frozen upstream semantics. DBOS, Restate, and Temporal remain comparison probes
until a separate ratified choice. Backend-specific IDs are metadata; Dharma IDs
and receipts remain canonical.

### 12.4 Effect state machine

```text
PROPOSED
  -> GATED | BLOCKED | REVIEW_PENDING
REVIEW_PENDING
  -> GATED(approved) | BLOCKED(rejected) | SUPERSEDED(modified)
GATED
  -> CLAIMED(fencing_token)
CLAIMED
  -> DISPATCHED | FAILED_SAFE
DISPATCHED
  -> ACKNOWLEDGED | FAILED_SAFE | UNKNOWN_RECONCILE
ACKNOWLEDGED
  -> RESULT_DURABLE -> CONSUMED
FAILED_SAFE
  -> RETRY_ELIGIBLE | TERMINAL_FAILURE
UNKNOWN_RECONCILE
  -> RECONCILED_SUCCESS | RECONCILED_FAILURE | COMPENSATED | QUARANTINED
RECONCILED_SUCCESS
  -> RESULT_DURABLE -> CONSUMED
RECONCILED_FAILURE
  -> COMPENSATION_PROPOSED | TERMINAL_FAILURE | QUARANTINED
COMPENSATION_PROPOSED
  -> new gated EffectIntentV1
```

`effect_id` is stable across retries and derives from semantic run/task/effect
index plus payload digest. `attempt_id` changes per try. Retry count must never
enter the logical idempotency identity for a world effect. Pure computation may
re-execute. An idempotent provider may retry with the stable provider key.
Non-idempotent or uncertain effects enter `UNKNOWN_RECONCILE`; they require
provider inquiry, operator resolution, or compensation before another attempt.
Recovery that finds a stranded `DISPATCHED` attempt without an authoritative
provider result always marks it ambiguous. `MODIFY` supersedes the original
intent, creates a new payload digest and logical effect identity, and reruns all
current gates; it never mutates an approved row in place. Compensation is a new
gated, journaled effect with its own ambiguity and receipt, not a cleanup
callback. Fork and migration reject checkpoints containing any nonterminal
effect or interrupt; reconciliation/quarantine must finish first.

Provider idempotency keys are adapter-normalized opaque digests: no raw payload,
PII, tenant name, prompt, or secret; allowed charset/maximum length come from the
provider adapter and are tested. Every pending write and barrier commit verifies
both current run fence and originating task-attempt fence.

The authoritative lifecycle is:

```text
EffectIntent
-> authority and gate record
-> durable claim plus fence
-> provider/tool invocation
-> provider acknowledgement/reference
-> durable result or UNKNOWN_RECONCILE
-> evidence receipt
-> checkpoint consumes result
-> downstream observation
```

Telemetry, machine chains, and UI streams are projections. Their failure is
visible but cannot alter authoritative effect state. Conversely, authoritative
intent/result persistence failure blocks the effect path.

The effect claim is scoped to handlers admitted through the trusted handler
registry. Such handlers receive an injected `NodeContext`/`EffectPort` and do
not receive provider clients or raw credentials. Egress-deny tests and static
guards reject direct provider/tool construction in registered graph handlers.
Unmigrated arbitrary Python callables are classified `unsafe_legacy`; they may
run only as pure compatibility handlers and cannot earn effect-safety credit.

### 12.5 Atomic barrier and persistence decision

A superstep barrier must atomically:

1. verify the current run lease/fencing token and every source task-attempt
   fence;
2. validate every pending write without mutating committed state;
3. commit channel values and versions;
4. mark consumed pending writes/effect results;
5. append a full checkpoint and immutable parent lineage;
6. advance the run cursor;
7. append monotonic graph events.

The §9.0 decision must choose the unit-of-work design before DG-03 launches.
Composing methods that each open and commit their own SQLite connection is not
atomic. The recommended ratification is the minimum graph-owned closure layer
inside the configured **isolated** `runtime.db` (`graph_definitions`,
`graph_threads`, `graph_runs`, `graph_tasks`, `graph_checkpoints`,
`graph_pending_writes`, `graph_effects`, `graph_interrupts`, `graph_events`),
with one transaction API, explicit projections to legacy runtime views, and no
authority over ontology/task/business outcome facts. The alternative is an
explicit extension of existing tables that proves the identical transaction.
No second database is proposed.

The admitted migration is additive, has schema-version metadata, runs only on
the isolated campaign database in this program, and includes forward/backward
compatibility tests: old binaries must continue to ignore the new additive
schema, while new binaries must read the last pre-migration state. Rollback is
reverse dependency order; never drop journal/effect evidence to make an old
binary happy. The JSON checkpoint directory becomes a compatibility projection
or is renamed, never a competing saver.

### 12.6 Native engine semantics

Keep `CompiledGraph.invoke()` as a compatibility facade. Move durable execution
into a `NativeRunEngine` that:

1. prepares and persists stable `NodeTaskV1` rows;
2. claims tasks with leases and fencing tokens;
3. executes ready tasks concurrently under a bounded structured task group;
4. persists each successful result as pending writes before acknowledging it;
5. cancels or drains siblings under explicit policy on failure;
6. retries only missing/failed tasks while preserving successful pending writes;
7. sorts/validates writes canonically and commits at the barrier;
8. checkpoints before scheduling the next superstep.

This is real bulk-synchronous parallelism: concurrent task execution with
deterministic, atomic barrier visibility. Sequential awaits cannot earn the
parallel facet. Retry, exponential backoff/jitter, max attempts, hard timeout,
idle timeout/heartbeat, cancellation, and cooperative drain are first-class
policies, not decorator conveniences.

### 12.7 Durable interrupt and resume

An interrupt is authoritative state, not a filesystem message:

```text
PENDING -> APPROVED | REJECTED | MODIFIED -> CONSUMED
```

The record binds run/node/effect, requested authority, payload digest, expiry,
operator, decision, and receipt. Resume wakes the durable run; it does not
restart from input. Same-version restart resumes from the exact checkpoint.
Version mismatch blocks. A deterministic migration records original and target
digests and leaves the original checkpoint immutable on failure. Fork mints a
new run identity with immutable parent lineage and cannot mutate the source
thread.

## §13 Work graph for the autonomous run

```text
DG-00 admission + immutable evidence freeze
   ├── DG-01 gauntlet integrity controls
   └── DG-02 versioned DharmaGraph IR
                    ↓
        DG-03 authoritative journal + full checkpoint
                    ↓
        DG-04 durable native run engine
                    ↓
        DG-05 effects + recovery + HITL
                    ↓
        DG-06 backend boundary + production shadow seam
                    ↓
        DG-07 VentureCell compiler + runtime-history cell
                    ↓
        DG-08 independent clean-checkout closeout
```

`DG-01` and `DG-02` may run in parallel on disjoint files after `DG-00`.
Everything else is dependency ordered. A later packet may be prepared, but no
later behavior may be claimed or merged before its prerequisite evidence is
valid. Each packet is an atomic commit/PR boundary. Once downstream nodes depend
on it, rollback proceeds in reverse dependency order rather than pretending
every commit can be reverted independently.

The campaign is divided into separately terminal controller epochs:

| Epoch | Nodes | Maximum honest tier |
|---|---|---|
| `A — admission/contract` | §9.0 landed, DG-00, DG-01 freeze, DG-02 | `CONTRACT_IR_ADMITTED` |
| `B — durable pure core` | DG-03, DG-04; trusted pure handlers only | `DURABLE_NATIVE_CORE_CANDIDATE` |
| `C — effect/HITL membrane` | DG-05 | `EFFECT_HITL_MEMBRANE_CANDIDATE` |
| `D — shadow organism seam` | DG-06, DG-07 | `SHADOW_BACKBONE_VERTICAL_CANDIDATE` |
| `E — sterile closeout` | DG-08 by a new independent verifier | `BACKBONE_V0_CANDIDATE_CLOSED_NOT_PROD` |

Each epoch closes, commits/merges, and starts the next from its admitted head.
The controller may advance within the same wall-clock allocation only when the
current epoch has independent evidence and sufficient remaining budget. It may
not carry an unfinished cross-epoch mega-branch. A terminal tier proves only
the rows named above; the aggregate verdict is reserved for Epoch E.

### 13.1 Surface admission before code

The existing track already owns `dharma_swarm/graph/**`, the narrow
orchestrator/swarm seams, the parity harness, and this spec. Before the first
implementation diff, extend that same track with the exact files listed in §14
and introduce no new wildcard. The already-owned `dharma_swarm/graph/**` and
generated `reports/governance/dharmagraph_parity/**` wildcards remain; every
implementation/test/script path in §14 is otherwise byte-exact. Any additional
file stops the packet for a new ownership decision. Do not create a twelfth
track or claim ownership by adding a file. `runtime_state.py`,
`spine/persistence.py`, runtime
control/API surfaces, ontology definitions, onboarding, merge authority, and
arena/evolution surfaces require explicit owner coordination if the chosen
packet needs them. Verify live ownership with `make onboard` and
`python3 scripts/governance/check_track_status.py`.

## §14 Work-packet contracts

Every packet begins with a failing behavioral/negative test, contains only its
declared files, and ends with raw commands/exits plus a machine-readable receipt
outside Git. Runtime receipts remain under `~/.dharma/`; only stable specs,
tests, code, and deliberately curated audit reports enter the repository.

### DG-00 — admission, branch truth, and harness freeze

**Objective:** establish a reproducible base and freeze the acceptance surface
before builders see results.

**Allowed files after §9.0 admission:** this spec;
`docs/governance/ACTIVE_TRACK.yaml` plus its generated managed blocks in
`CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, and
`docs/governance/BUILD_SESSION_ENTRYPOINT.md` (coordinate their owners; the
render targets are declared in
`scripts/governance/render_active_track_includes.py:43-45`);
`scripts/governance/dharmagraph_parity_gauntlet.py`;
`tests/oracle_support/dharmagraph_gauntlet.py`;
`tests/test_dharmagraph_parity_gauntlet.py`;
`docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V3.json`;
`reports/governance/dharmagraph_parity/**`;
`scripts/governance/dharmagraph_campaign_evidence.py` and
`tests/test_dharmagraph_campaign_evidence.py`; no runtime code. Card 49's
onboarding/workflow files are excluded and must already be landed by their
owner.

**Required work:**

- record base SHA, Python/OS/dependency lock, exact commands, seeds, current
  audit receipts, and ownership map;
- install the intended environment and make missing-oracle dependencies fail
  admission rather than skip;
- verify card 49's interpreter/CI repair is already merged through the
  `onboard-one-door` owner; implement hardening cards 46-48 as a new
  rubric/harness version when probe semantics change; preserve the frozen V2
  receipts unchanged;
- freeze builder-visible tests and expected outputs before DG-02 starts;
- land the §16.3 node-evidence manifest validator and bind it to the spec/base/
  harness digests before any implementation node can promote;
- create permanent controls: broken-but-importable engine scores 0.00; deleting
  the neutral engine zeros APP rows; no-op saver fails durability; fake restart
  from input fails resume; constant-output engine fails semantics; hardcoded
  completeness and unconditional performance cannot pass; wrong interpreter
  fails preflight.

**Acceptance:** independent builder/judge receipts match on the hardened run;
each counterfactual produces its expected failure; APP scenarios execute
through `dharma_swarm.graph`, not `langgraph_parity`; the old 31 receipt remains
verifiable and the new score is reported separately even if lower.

**Kill criterion:** any change to an expected result after seeing builder output,
or any control that can pass while its critical engine component is deleted.

### DG-01 — gauntlet integrity lane

**Objective:** maintain the frozen harness and two scoreboards while builders
work. This lane never edits implementation code.

**Allowed files:** the DG-00 parity script, oracle-support file, V3 rubric,
gauntlet test, and generated parity report paths listed immediately above. The
campaign-evidence validator, active track, spec, and runtime code are read-only
for this lane.

**Verification:** execute direct two-arm behavior for every scored facet; import
or `getattr` earns zero. Missing upstream dependency is a failed run. Preserve
frozen target and rolling-latest results separately. Emit normalized semantic
traces, environment, seed, command, and digest in both receipts.

After DG-01 freeze, its guardian becomes read-only for the rest of the campaign.
Any legitimate semantic correction mints a new harness version and restarts
verification for every affected candidate; it never edits expectations in
place. Public contract tests are visible, while the Epoch-E verifier generates
held-out property seeds and counterfactual mutations only after candidate
freeze and records their generator/version digest.

**Kill criterion:** builder and evaluator share mutable expected data or the
evaluator imports builder-only success constants.

### DG-02 — versioned DharmaGraph IR

**Objective:** land §12.2 contracts and a stable handler registry without
changing production behavior.

**Allowed files after §9.0 admission:** `dharma_swarm/graph/ir.py`,
`dharma_swarm/graph/versioning.py`,
`dharma_swarm/graph/handler_registry.py`, `dharma_swarm/graph/types.py`,
`dharma_swarm/graph/compiler.py`, `dharma_swarm/graph/routing.py`,
`dharma_swarm/graph/__init__.py`, `tests/test_graph_ir.py`, and
`tests/test_graph_versioning.py`. Any expansion is a new ownership decision.

**Failing-first tests:** canonical serialization is key-order invariant; the
same definition compiles to the same digest in a fresh process; a handler or
schema/policy version change changes the appropriate digest; callable objects
cannot serialize; unknown fields and unknown major versions fail; invalid
handler refs fail compilation; schema/graph mismatch blocks resume.

**Acceptance:** every §12.2 type round-trips; graph definitions contain no live
callables; existing candidate tests remain green; no production importer added.

**Kill criterion:** the IR leaks backend types into Dharma semantic/authority
contracts or requires importing provider SDKs.

### DG-03 — authoritative journal and full checkpoint

**Objective:** replace the digest-list/checkpoint mismatch with an authoritative,
versioned, full checkpoint and transaction boundary.

**Allowed files after §9.0 admission:** `dharma_swarm/graph/store.py`,
`dharma_swarm/graph/schema.py`, `dharma_swarm/graph/serde.py`,
`dharma_swarm/graph/checkpoint.py`, `dharma_swarm/graph/types.py`,
`tests/test_graph_store.py`, `tests/test_graph_process_resume.py`, and the exact
ratified transaction-owner file (either `dharma_swarm/runtime_state.py` or its
fully qualified owner-approved unit-of-work module). No other persistence file
is implied. The §9.0 decision must write the chosen byte-exact path into the
active track and DG-03 launch manifest; the evidence validator rejects the
unresolved either/or.

**Failing-first tests:** full state, versions, pending writes/effects, interrupt,
manifest, graph/code/schema/prompt/model/tool/gate versions, and lineage survive
a fresh interpreter; corrupted payload/digest fails closed; concurrent resume
admits one writer; stale fence cannot commit; fork retains immutable parent;
failed migration leaves source intact; simulated disk-full/torn write never
promotes partial state.

**Acceptance:** one real subprocess writes a checkpoint, exits, and a different
interpreter resumes the exact run boundary. The persistent artifact and in-memory
`RunCheckpoint` are the same contract. History/fork inspection is deterministic.

**Admission dependency:** `DGB-D2` must already name the transaction design and
schema. If it is absent, DG-03 does not start and Epoch A ends
`BLOCKED_OPERATOR_DECISION`; the builder does not rediscover or reinterpret it.

**Kill criterion:** resume recomputes from initial input, loses pending writes,
or silently accepts version drift.

### DG-04 — durable native run engine

**Objective:** implement §12.6 behind the existing `CompiledGraph.invoke()`
facade.

**Allowed files:** `dharma_swarm/graph/run_engine.py`,
`dharma_swarm/graph/executor.py`, `dharma_swarm/graph/policies.py`,
`dharma_swarm/graph/scheduler.py`, `dharma_swarm/graph/state.py`,
`dharma_swarm/graph/errors.py`,
`tests/test_graph_run_engine.py`, `tests/test_graph_concurrency.py`, and
`tests/test_graph_policies.py`.

**Failing-first tests:** two ready async nodes rendezvous on deterministic
barriers and emit overlapping start/finish trace intervals (wall-clock timing is
advisory only); committed output is invariant to completion order; one sibling failure commits
no barrier state but preserves successful pending writes for resume; cancellation
reaches children; backoff/jitter is seed-replayable; hard and idle timeouts differ;
retry clears only the failed attempt's writes; bounded max concurrency is
enforced; cooperative drain checkpoints continuation.

Async cancellation alone is not proof of a hard timeout for blocking code.
Untrusted/blocking handlers execute behind a killable subprocess boundary with
a PID handshake, bounded stdout/result channel, and fence-checked completion.
Epoch B admits trusted pure handlers only; effectful handlers wait for Epoch C.

**Acceptance:** actual concurrent task execution, deterministic atomic barrier,
pending-write recovery, retry/timeout/cancel/drain policies, and all neutral
kernel tests green. `scheduler.py` does not grow into another god object.

**Kill criterion:** any interleaving produces nondeterministic committed state,
a cancelled child can commit, or a succeeded sibling must rerun after restart.

### DG-05 — fail-closed effects, real recovery, and HITL

**Objective:** make §12.4 and §12.7 authoritative around every graph agent/tool
effect.

**Allowed files after owner admission:**
`dharma_swarm/graph/effect_journal.py`,
`dharma_swarm/graph/dispatch_port.py`, `dharma_swarm/graph/interrupts.py`,
`dharma_swarm/graph/recovery.py`, `dharma_swarm/graph/durable_invoker.py`,
`dharma_swarm/graph/reconciler.py`,
`dharma_swarm/runtime_control_actions.py`,
`dharma_swarm/spine/persistence.py`, `tests/test_graph_effect_journal.py`,
`tests/test_graph_recovery_process.py`, `tests/test_graph_interrupts.py`, and
`tests/test_runtime_control_actions.py`. The spine and runtime-control files
need their named owner in §9.0; no unnamed API/view edit is allowed.

**Failing-first tests:** missing store/identity blocks an effectful node; stable
`effect_id` survives retries while `attempt_id` changes; kill before dispatch,
during effect, after provider action/before persistence, after result/before
checkpoint, and after checkpoint; two workers race one task; lease expires and
late stale completion is rejected; provider response is lost; DB lock/commit
failure; queue duplicate/reorder; non-JSON and oversized result; partial
multi-effect failure; clock skew/warrant expiry; durable APPROVE/REJECT/MODIFY;
resumed effect rechecks current revocation; authenticated decision CAS admits
one terminal decision; MODIFY creates/re-gates a new intent; fork/migration
reject nonterminal effects; compensation traverses the same gated journal.

Use real PID-handshaken child processes and `SIGKILL` inside the isolated
campaign root. The harness verifies the handshake and target executable before
signaling; it never kills the controller or an unrelated PID. It may inject
faults and inspect campaign state but may not fabricate post-crash recovery
rows. An idempotent fake
provider must observe one logical action. A non-idempotent fake must land in
`UNKNOWN_RECONCILE` and never silently replay. Heartbeat only leases owned by
the current worker/fence. Receipt persistence targets exact run/effect identity,
not every row sharing a task ID.

**Acceptance:** no unjournaled effect in graph-required mode; every acknowledged
effect has intent, complete attempt history, provider correlation, result or
ambiguity state, gate/authority receipt, and consuming checkpoint. Real restart
and HITL resume pass across fresh interpreters. The `AuthorityEvaluator` is the
only effect/HITL admission door and proves authenticated operator identity,
execution-lease expiry/revocation, current gate version, and decision CAS.

**Kill criterion:** duplicate irreversible fake effect, lost acknowledged effect,
fail-open effect on persistence error, stale-fence commit, or blind retry from
ambiguous state.

### DG-06 — backend boundary and production shadow seam

**Objective:** prove substrate portability while keeping native execution the
only production candidate and live effects single-fired.

**Allowed files after §9.0 shadow-seam admission:**
`dharma_swarm/graph/backends/base.py`,
`dharma_swarm/graph/backends/native.py`,
`dharma_swarm/graph/backends/langgraph_oracle.py`,
`dharma_swarm/graph/orchestrator_adapter.py`,
`dharma_swarm/graph/worker.py`, the exact minimal
seam in `dharma_swarm/orchestrator.py` and `dharma_swarm/swarm.py`,
`tests/test_graph_backends.py`, and `tests/test_graph_shadow_adapter.py`.

**Required modes:**

- `off`: current path, no graph behavior;
- `shadow`: replay-only for effectful nodes. The legacy path performs the one
  already-authorized provider/tool call; its normalized input/result/receipt is
  injected through `ReplayEffectPort` while graph egress is denied. Trusted
  pure graph nodes may execute normally. Shadow never calls a provider/tool a
  second time and never claims live equivalence for an unsupported effect;
- `canary`: specified but not enabled in this campaign; requires `DGB-D4`.

**Failing-first tests:** backend capability mismatch is typed; native and oracle
produce normalized equivalent outcomes on supported graphs; Dharma receipt IDs
and causal fields are backend invariant; deleting the neutral engine fails the
application test; shadow mode makes exactly the same number of external calls as
off mode; replay refuses a mismatched input/result/receipt digest; egress-deny
control catches a direct provider attempt; flag-off rollback restores old
behavior.

**Acceptance:** one whitelisted topology is compiled and shadowed through the
real orchestration seam with an observable graph/run receipt and zero duplicated
effects. External backend packages remain test extras.

**Kill criterion:** shadow performs an effect, backend IDs become canonical
identity, or flag-off fails to restore the legacy path.

### DG-07 — VentureCell compiler and runtime-history learning cell

**Objective:** prove the higher Dharma layer that no borrowed workflow engine
supplies.

**Allowed files:** `dharma_swarm/graph/venture_cell_compiler.py`,
`dharma_swarm/graph/outcomes.py`, `dharma_swarm/graph/cells/__init__.py`,
`dharma_swarm/graph/cells/runtime_history.py`,
`tests/test_graph_venture_cell_compiler.py`, and
`tests/test_graph_runtime_history_cell.py`. Existing ontology, fractal,
OperatingFact, and WorkPacket owners are read through public APIs only. A needed
edit to any of them is a new owner decision and stops this packet.

The compiler consumes one real `VentureCell` ontology object plus explicit
linked policies and emits `VentureCellCompileResultV1`. It must inherit telos,
acceptance criteria, autonomy, permissions, budgets, KPI/outcome binding,
memory/context policy, roster/diversity requirements, transport/backend choice,
and operator authority. Missing required policy is a compile error, not a
default. Existing WorkPackets are referenced as `(namespace, packet_id,
digest)` through explicit adapters.

`ExternalOutcomeEnvelopeV1` is transport/causal binding only. It references the
canonical ontology `Outcome`, `ValueEvent`, and `Contribution` owners; it does
not become a fourth outcome or value store. Any write/promotion must traverse
the existing ontology action, gate decision, witness, artifact, and value-event
owners required by the ontology-native seam contract
(`docs/governance/BUILD_SESSION_ENTRYPOINT.md:90-102`).

The input dataset has a sealed manifest: explicit read-only snapshot path,
source schema/version, source digest, capture time within seven days of the
epoch, sanitizer code/version/digest, privacy/secret scan attestation, eligible
row definition, at least 50 eligible independent runs, stable dedupe key, and a
chronological 60/20/20 train/dev/held-out split with at least 10 held-out rows.
The candidate never reads held-out rows or split labels. The verifier seals the
split/selection digest and reveals held-out scoring only after candidate freeze.
If these constraints are not met, DG-07 is `NEEDS_HOST`, not downsampled into a
toy claim.

The first cell is:

```text
sanitized real delegation/runtime failures
-> provenance-bearing OperatingFact/ExternalOutcome import
-> compiled runtime-history VentureCell
-> replayed independent diagnosis traces, or budget-authorized offline
   decorrelated diagnosis seats
-> bounded WorkPacket reference
-> candidate patch or routing/playbook proposal
-> tests + adversarial held-out scorer
-> constitutional promotion decision
-> shadow-only update
-> next shadow cycle demonstrably consumes the update
```

**Failing-first tests:** same cell/policy versions compile to the same digest;
mutating a declared property changes the expected graph surface; incomplete
authority/budget/gate policy fails; unknown fields cannot disappear; two cells
remain isolated by state/memory/tool/budget; an execution trace proves the
compiled path through the real orchestration seam in replay-only shadow mode;
disabling the legacy bespoke executor does not break the compiled
scenario; candidate-authored/stale/duplicate/unwitnessed outcomes are rejected;
with-vs-without-outcome counterfactual changes the justified next decision.

**Acceptance:** real non-toy input, actual compiler/native/shadow seam, complete
WorkPacket/artifact/gate/receipt chain, held-out leakage check, matched-budget
best-single comparison, and proof that the next shadow cycle read the admitted
change. Historical imported outcomes can reach backbone evidence level 3; only
a later independently observed live outcome can reach level 4.

Without a ratified `DGB-D9` budget, only independently recorded traces may be
replayed and the result cannot claim live multi-agent lift. With a budget, all
offline model calls run outside production shadow, use canonical routing, carry
max call/token/cost limits, and compare against a matched-budget best-single
control. The with/without-outcome counterfactual proves **causal consumption**
only. “Improved learning” additionally requires a predeclared held-out metric,
uncertainty, and superiority to the named baseline; a changed decision alone is
not improvement.

**Kill criterion:** a fixture is relabeled real, the candidate/scorer authors its
own outcome, a dashboard row is mistaken for consumption, or a shadow proposal
mutates live routing/archive fitness.

### DG-08 — independent closeout

**Objective:** rederive every claim from a fresh checkout using an evaluator that
did not author the implementation or mutable expected data.

**Required work:** install from the declared lock, run both scoreboards, replay
all seeds, execute the real crash/effect matrix, verify receipt digests and
causal completeness, compare changed files to admitted surfaces, inspect all
skips/xfails/assertion changes, test flag-off rollback, and rerun from the merged
base when merge authority exists.

**Acceptance:** builder and independent verifier agree on raw observations and
terminal verdict. A disagreement is `REVISE` or `BLOCKED`, never averaged.

**Kill criterion:** evaluator requires implementation-author intervention after
sterile acquisition, or candidate changes after verification begins.

## §15 Falsification-first acceptance system

### 15.1 Scoreboard A — LangGraph compatibility

Keep the frozen 1.2.4 score and a rolling-latest score as separate reports.
Resolve and pin rolling latest at DG-00; never average versions.

Per facet:

- `0`: absent, skipped, import-only, mocked at the critical seam, or behavior
  differs;
- `1`: direct two-arm happy-path behavior matches deterministically;
- `2`: happy path, relevant negative/failure behavior, and independent
  clean-checkout rerun match.

Performance earns zero until semantic equivalence passes. APP rows must execute
through the neutral/compiled engine. Rubric changes mint a new version and full
rerun. Prioritize the backbone profile before convenience parity:
`LG01`, `LG04-LG10`, `LG12`, `LG14-LG20`, `LG24-LG26`, `LG30`,
`LG34-LG35`, and `APP01-APP04`. Streaming variants, cache, vector store,
prebuilt helpers, and low-level Pregel compatibility cannot outrank restart,
effects, interrupts, versioning, and production integration.

### 15.2 Scoreboard B — Dharma backbone readiness

Evidence levels:

- `0`: absent;
- `1`: unit proof;
- `2`: local integration proof;
- `3`: real multi-process/failure-injected proof;
- `4`: independently reproduced non-toy end-to-end evidence through the real
  shadow orchestration seam. For the outcomes/learning area specifically,
  level 4 additionally requires a later independently observed live-world
  outcome consumed by the next decision; witnessed historical import earns at
  most level 3 there.

| Area | Weight |
|---|---:|
| Durable execution and effect safety | 25 |
| External outcomes and causal learning closure | 20 |
| Constitutional authority, gates, and HITL | 15 |
| VentureCell compiler and ontology inheritance | 15 |
| Versioned resume, replay, fork, and migration | 15 |
| Operations, observability, and substrate portability | 10 |

Each area contains four critical facets and its category level is the **minimum**
evidence level among them, preventing a strong convenience feature from hiding
a missing safety boundary:

| Area | Critical facets |
|---|---|
| Durable/effects | full checkpoint/restart; pending-write recovery; effect ambiguity/idempotency; run/task fencing |
| Outcomes/learning | canonical provenance; leakage/dedupe control; with/without causal consumption; independently observed live outcome |
| Authority/HITL | authenticated authority; gates/current revocation; durable interrupt decision; resume revalidation |
| VentureCell | deterministic compile; policy inheritance; cell isolation; real shadow seam |
| Versioned control | version pin/refusal; migration; history/replay; immutable fork lineage |
| Operations/portability | bounded concurrency/backpressure; observability/receipts; flag-off/reverse rollback; backend-neutral conformance |

Calculate:

```text
backbone_readiness = sum(area_weight * area_level / 4)
```

Round only for display; retain the exact rational value. Tiers are descriptive:
`<50 prototype`, `50-69 integrated`, `70-84 chaos candidate`, `85-99 shadow
backbone candidate`, `100 live-outcome-complete`. Epoch-E closure requires at
least 85, every area at level 3 or higher, independently observed evidence, and
zero red gates. Historical outcomes cap the outcomes/learning area at level 3,
so this campaign cannot score 100.

Report both number and blocking status, for example `74/100 — BLOCKED:
ambiguous duplicate effect`. No aggregate overrides a red gate. This scoreboard
does not close the current LangGraph parity blocker unless `DGB-D1` is
operator-ratified in the intent owner.

### 15.3 Hard red gates

Any one makes the campaign non-shippable regardless of score:

- unauthorized, ungated, duplicate, or lost acknowledged effect;
- effect execution without stable causal/authority identities;
- fail-open effect when persistence or identity is missing;
- incompatible resume without a migration receipt;
- stale worker commit after lease takeover;
- candidate/scorer-authored “external” outcome;
- application proof that bypasses the neutral engine or VentureCell compiler;
- old checkpoint bypasses a current revocation or expired warrant;
- builder changes frozen acceptance/scoring after seeing results;
- independent clean-checkout observations disagree;
- destructive migration, secret exposure, unapproved egress, or external write;
- new skip/xfail, deleted test, weakened assertion, or hardcoded success used to
  obtain green.

### 15.4 Outcome truth gate

An admitted outcome needs an external-to-candidate source, timestamp, stable
reference/digest, independent witness or reproducible import, causal link to
the originating run/work/artifact, dedupe/replay protection, freshness policy,
and named downstream decision consumer. Reject stale, duplicate, candidate-made,
harness-written, leaked-held-out, or unreconciled-conflict outcomes.

Closure requires the counterfactual:

> Run next-decision logic with and without the outcome and show the justified
> difference in WorkPacket selection, routing, budget, playbook, or shadow
> evolution proposal.

Storage, display, summary, or a changed score alone is not causal closure.

## §16 Autonomous campaign controller

### 16.1 Roles and file isolation

Use at most four simultaneous lanes:

| Lane | Responsibility | May edit |
|---|---|---|
| Controller/integrator | admission, dependency state, narrow merges, receipts, stop decisions | spec/track only when declared; integration commits after lane handoff |
| Runtime builder | DG-03 through DG-05 | its admitted `graph/` runtime files and named tests |
| Semantic/backend builder | DG-02, DG-06, DG-07 | disjoint IR/backend/compiler files and named tests |
| Harness guardian | DG-01 freeze and ongoing read-only integrity checks | harness/reports only before freeze; read-only afterward; never implementation or DG-08 verdict |

No two modifying agents share a dirty worktree or file lease. A lane may use
subagents for read-only investigation, but one named owner writes each file.
Decorrelated review never means one model speaking under several names.
Epoch E replaces a released lane with a **new final-verifier identity** that
authored no implementation, harness, expected output, or prior node verdict.
The controller, harness guardian, and builders are ineligible for DG-08.

### 16.2 Per-node loop

For every DG node:

1. base the node on the previously admitted campaign head and record exact
   spec/base/parent/ownership/prerequisite digests;
2. create a clean isolated worktree and enforce the packet's exact allowed files;
3. add named failing-first tests and negative controls;
4. implement only the packet envelope;
5. run targeted tests, affected tests, preflight/closeout, and packet controls;
6. obtain independent review on the exact candidate diff;
7. treat every substantive finding as more work on the same node;
8. create one atomic commit/PR and prove the accepted head;
9. emit and validate the §16.3 node manifest; advance only after its evidence
   and accepted head are mechanically valid.

The controller may fetch newer canonical main for observation, but it does not
silently move the campaign base or frozen harness. Adopting unrelated upstream
changes is an explicit rebase gate: record old/new bases, collision/ownership
delta, rerun all accepted node evidence and controls, and mint a new base
manifest. Otherwise every node builds on the accepted predecessor.

If GitHub credentials/merge authority are unavailable, keep atomic local commits
and receipt them, but use `CANDIDATE_NOT_MERGED` language. Never fabricate PR or
merged evidence.

### 16.3 Durable resumption without another truth ledger

On restart, derive:

```text
next node = first DG node without mechanically valid evidence on the current base
```

DG-00 lands `dharma.dg_campaign_node_evidence.v1` as a **derived manifest**, not
a new authority store. One manifest per node lives under the isolated campaign
root and contains:

- campaign/epoch/node IDs, spec commit/digest, campaign base, accepted parent,
  candidate and merge SHAs;
- prerequisite-manifest digests, frozen harness/rubric digest, dependency-lock
  and environment/tool digests;
- exact allowed-file list/digest, changed files and diff digest;
- commands as argv arrays, expected/actual exits, stdout/stderr digests and
  duration (never shell prose alone);
- artifact paths/digests, fault seeds, provider-call/budget counts, red-gate
  vector, rollback observation;
- builder, reviewer and verifier identities/lanes, verdict, previous-manifest
  digest, and stable manifest digest.

Validate with the admitted command:

```bash
.venv/bin/python scripts/governance/dharmagraph_campaign_evidence.py verify \
  --manifest "$DHARMA_CAMPAIGN_ROOT/receipts/nodes/<node-id>.json" \
  --candidate-sha '<sha>' \
  --require-clean
```

The validator checks schema, digest chain, Git/file envelope, prerequisite
heads, harness/lock/environment binding, command exits, artifact digests, and
red gates. It cannot turn a self-authored row into proof: Git/CI/test artifacts
and the separately authored semantic review remain the underlying evidence.
DG-00 itself closes through its independent PR/CI review plus a manifest
bootstrap test; every later node requires the validator.

Use Git, the active-track owner, accepted commits/PR checks, the frozen harness,
validated node manifests, and standard external receipts. The mission scheduler
may retain queue/heartbeat state, but it cannot promote completion.
`scripts/runtime/autonomy_spine.py` is
only a bounded mission/task bridge (`scripts/runtime/autonomy_spine.py:1-8`);
its current CLI supports `init`, `status`, and bounded `run --duration-hours`
(`scripts/runtime/autonomy_spine.py:182-210`). It is not the campaign authority.

### 16.4 Persistence and monitoring

Run any unattended lane in a named tmux session or stronger supervisor; tmux is
execution persistence, not proof (`docs/ops/TMUX_AGENT_SUBSTRATE.md:17-29,49-71`).
Every lane writes an external heartbeat/receipt, and the controller reports a
short operator-readable checkpoint every 60-90 minutes containing current node,
newly passing evidence, spend/time, blocker, and next action.

Heartbeat location is
`$DHARMA_CAMPAIGN_ROOT/receipts/heartbeats/<lane-id>.json`; it contains lane,
node, accepted parent/candidate SHA, observed time, current command PID, latest
artifact digest, spend counters, blocker, and stable digest. It is liveness only,
never completion. Node manifests live at
`$DHARMA_CAMPAIGN_ROOT/receipts/nodes/<node-id>.json`. Operator monitoring uses:

```bash
.venv/bin/python scripts/governance/dharmagraph_campaign_evidence.py status \
  --campaign-root "$DHARMA_CAMPAIGN_ROOT"
tmux capture-pane -pt '<session>:<window>.<pane>' -S -120
```

The status command must distinguish stale heartbeat, running, blocked,
candidate, accepted, and invalid evidence. A visible tmux pane is not proof.

Stop and quarantine immediately on any §15.3 red gate. Stop a node after the
same blocking condition repeats in three repair cycles or the next cycle has no
new hypothesis/evidence. Continue disjoint permitted work when one node awaits
operator/access authority; do not widen the blocked packet.

### 16.5 Rollback

- Use additive/backward-compatible migrations and feature flags.
- Roll back in reverse dependency order from the newest dependent node; prove
  old-binary compatibility before retaining an upgraded additive schema.
- `off` remains the production default throughout the campaign.
- Roll back code/configuration but never erase adverse receipts, effect attempts,
  ambiguity, or checkpoint history.
- Quarantine ambiguous effects; reconcile or compensate them explicitly.
- After rollback, rerun the last known-green gauntlet from a clean checkout.

## §17 Launch contract

### 17.1 Operator preflight

Run from the canonical repository host:

```bash
git fetch github main
git merge-base --is-ancestor 6965d38d github/main
tmux -V
tmux list-sessions
```

The repository's tmux spec currently documents Make targets that are absent
from the Makefile (`rg -n 'tmux-(bootstrap|status)' Makefile`; a failing
`make -n tmux-bootstrap` must not be treated as a valid launch), so this campaign does
not call them. The operator must create
or select a named tmux/stronger-supervisor session using the host's verified
mechanism before leaving the lane unattended; `tmux list-sessions` exiting 1
because no server exists is a launch blocker until that session is created.

Create a clean worktree/branch from the recorded `github/main` SHA using the
host's normal worktree policy. In that worktree:

```bash
make onboard
command -v uv
uv sync --frozen --extra dev --extra test-oracle
make agent-build-preflight
```

All must pass before code. If dependency installation needs network or paid
access, obtain the normal operator approval; do not fall back to a degraded
interpreter and score it. `uv.lock` is the frozen environment owner for the
main/frozen-oracle lane. DG-00 resolves rolling-latest in a separate environment
and records its exact lock/digest; it never mutates the frozen 1.2.4 environment.
`autonomy_spine.py` may mirror bounded scheduling intent after preflight, but it
is not used as the executor or completion authority for this multi-node graph.

### 17.2 Copy-paste controller prompt

```text
You are the DharmaGraph Backbone v0 campaign controller.

Start by running make onboard and reading, in authority order:
1. CLAUDE.md and AGENTS.md
2. docs/governance/ACTIVE_TRACK.yaml, dharmagraph-engine-2026-07
3. docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md, especially §§9-18
4. reports/governance/dharmagraph_parity/PARITY_MATRIX.md and receipts
5. docs/ops/MODEL_KEY_ROUTING.md before any model/provider action

Execute the §13 epochs in order. The initial autonomous epoch is A (DG-00,
DG-01 freeze, DG-02); continue into B/C/D only after the current epoch has a
valid tier, admitted head, remaining wall-clock/budget, and no authority stop.
Epoch E always uses a new sterile verifier. Only DG-01 and DG-02 may parallelize
after admission. Use clean worktrees, one writer per file, one atomic commit/PR
per DG node, failing-first tests, frozen negative controls, and independent
verification. Re-derive evidence from the pinned campaign head; do not trust
prose completion markers or silently rebase to moving main.

The locked target is BACKBONE_V0_CANDIDATE_CLOSED_NOT_PROD: versioned Dharma IR,
full durable checkpoint, real process restart, fail-closed journaled effects,
durable HITL, native backend plus test-only oracle backend, production shadow
seam with zero duplicate effects, and one real runtime-history VentureCell whose
imported outcome changes the next shadow decision.

Never: weaken a gate/test; add a skip/xfail; fabricate crash rows/outcomes;
claim exactly-once; create a fourth WorkPacket; use a stale/WIP base; touch an
undeclared sibling-track surface; add a truth store or production backend;
enable canary/world effects/evolution; push/merge/deploy without existing
authority; or round a blocked score up to completion.

Pause only at DGB-D1..D9 authority boundaries or a packet kill criterion.
Record the exact command, exit, evidence, and safest next action, then continue
disjoint permitted work. Report progress every 60-90 minutes. End only with one
of the §18 terminal verdicts and a reproducible receipt bundle.
```

## §18 Closeout

### 18.1 Required final commands

Run from a fresh clean checkout of the exact candidate or merged head:

```bash
make onboard
command -v uv
uv sync --frozen --extra dev --extra test-oracle
make agent-build-preflight
.venv/bin/python -m pytest -q tests/test_graph_*.py \
  tests/test_langgraph_differential_oracle.py \
  tests/test_dharmagraph_parity_gauntlet.py \
  tests/test_orchestrator.py \
  tests/test_orchestrator_spine_dispatch.py \
  tests/test_swarm.py \
  tests/test_swarm_routed_execution.py \
  tests/test_topology_execution.py \
  tests/test_topology_genome.py \
  tests/test_workflow.py
make test-fast
DHARMA_PYTHON="$PWD/.venv/bin/python" \
  bash scripts/governance/run_python_with_repo_env.sh \
  scripts/governance/dharmagraph_parity_gauntlet.py --check
.venv/bin/python scripts/governance/check_track_status.py
.venv/bin/python scripts/governance/render_active_track_includes.py --check
make agent-build-closeout
```

The independent verifier also runs the dedicated real-process crash/effect/HITL
harness and the runtime-history counterfactual command added by DG-05/DG-07.
Those commands must be listed with exact exits in the closeout packet rather
than represented by the broad wildcard suite alone.

### 18.2 Receipt bundle

The external bundle must include:

- base and candidate/merge SHAs, clean status, dependency/tool/environment
  digests, seeds, commands and exits;
- builder and independent-verifier identities and model/provider lanes;
- both compatibility reports, never averaged;
- backbone score by category plus hard-red status;
- normalized traces for concurrency, checkpoint, resume/fork, effect attempts,
  fencing, interrupt, shadow backend, compiler, outcome import, and
  with/without-outcome next decision;
- cost/time ledger and provider-call counts;
- all failures, ambiguities, quarantines, skips, unavailable hosts, operator
  decisions, and unresolved risks;
- rollback proof with graph mode `off`;
- a claim table distinguishing `implemented`, `unit-proven`,
  `integration-proven`, `chaos-proven`, `production-shadowed`, and
  `live-outcome-proven`.

### 18.3 Terminal verdicts

The closeout payload always includes `highest_tier` (one §13 tier or `NONE`),
`first_unproved_node`, and exactly one verdict:

- `BACKBONE_V0_CANDIDATE_CLOSED_NOT_PROD` — every mandatory DG acceptance and
  independent proof passed, no red gate, real non-toy shadow slice complete;
- `EPOCH_ACCEPTED` — the current epoch's named tier passed and was admitted, but
  later epochs were intentionally not attempted in this controller window;
- `CANDIDATE_NOT_MERGED` — technical candidate passed locally but merge/CI
  authority or evidence is absent;
- `BLOCKED_OPERATOR_DECISION` — a named `DGB-D*` choice prevents honest
  continuation;
- `BLOCKED_WITH_EVIDENCE` — a non-authority technical prerequisite is proved
  unavailable or unsatisfied and does not fit `NEEDS_HOST`;
- `NEEDS_HOST` — a required real snapshot/provider/host is unavailable and no
  fixture substitution was made;
- `FAILED_RED_GATE` — a §15.3 invariant failed; affected effects/state are
  quarantined and rollback evidence is present;
- `INCOMPLETE_WITH_EVIDENCE` — time/resources ended before a terminal build
  state; completed nodes and first unproved node are named.

DG-08 `REVISE` is not a promotable terminal verdict: it returns the campaign to
the first invalid node and eventually closes as `INCOMPLETE_WITH_EVIDENCE` if
the epoch stops. DG-08 `BLOCKED` maps to the specific operator, host, or
evidence-blocked verdict above. No generic `BLOCKED` string is emitted.

No terminal verdict closes the active track's 100/100 parity blocker or opens
the North Star trust gate unless their owners independently say so.
