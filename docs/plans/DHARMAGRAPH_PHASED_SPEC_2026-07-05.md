# DharmaGraph — Phased Architect Spec (2026-07-05)

**Role:** the buildable handoff spec for the sovereign graph-runtime campaign ("our own LangGraph, more evolved"). Written to be fed to a fresh Claude instance, to Devin, or to any coding agent with zero prior context. Fuses three deep code audits (2026-07-05, this session), a four-lane external research convoy (~150 primary sources), and Devin's independent code review (adjudicated below — his corrections are integrated, not appended).

**Trust rule:** if this file disagrees with `make onboard`, `docs/governance/ACTIVE_TRACK.yaml`, a receipt, or the code, trust those. Every file:line in this spec was verified on branch `claude/audit-skills-workflows-xadbrl` at 2026-07-05; re-verify before building on it — this repo moves ~60 commits/week.

**Companion evidence:** the full research-lane reports (durability SOTA, graph-runtime field scan, verifiable/self-evolving runtimes, repo seam map) live in the session that produced this spec; the curated reference list is §8. The engine-comparison verdict this spec implements: dharma_swarm is ~60% of LangGraph's engine capabilities, ~25% of its coherence (a federation of 5+ engines where the hot path has the worst machinery), with governance/evolution assets no framework has.

---

## §0 How to use this spec

- Each phase is independently shippable with its own acceptance criteria and kill criterion. Do NOT start phase N+1 until phase N's acceptance criteria have receipts (test output, commit hash, chaos-run log).
- Before any build work: run `make onboard`, read `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, check `INTERFACE_MISMATCH_MAP.md` for the module pairs you touch.
- **This campaign needs its own track** in `docs/governance/ACTIVE_TRACK.yaml` (a new project is a new track). Proposed skeleton in §7. Several files this spec touches are owned by existing tracks (`coordination/**` → orchestration-arena-v1; `archive.py`, `organism.py` → organism-rewire) — those edits go through those tracks' next-items or wait for their owners, per portfolio doctrine.
- Doctrine that binds every phase: extend existing owners, never weaken a gate, no new truth stores, runtime receipts never enter git, zero trained weights until the arena produces labels.

## §1 Current-state truth (the honest baseline)

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

**Durability model (decided, from the research convoy):** snapshot-per-superstep + the receipt log as side-effect journal. NOT Temporal-style replay (retroactive determinism tax across 880 modules; agent loops blow event-history caps; resume latency is noise when steps are seconds-long LLM calls). Validation: DBOS ships SQLite as default system DB; Cloudflare Agents = state-in-embedded-SQLite per agent. The design in one sentence:

> One `BEGIN IMMEDIATE` transaction per superstep commits {checkpoint record, task claims, dispatch-intent rows}; `invoke_agent` memoizes on receipt under a deterministic idempotency key; a boot reconciler requeues or quarantines orphans; retry-exhausted rows are quarantined-and-reported, never hidden.

- Outbox = existing `delegation_runs` row (intent inserted in the superstep transaction — control state and dispatch intent can never disagree; kills torn supersteps).
- Memo = existing `receipt_json`: check-before-execute upgrades write-only audit to effectively-once. Idempotency key = `sha256(run_id:superstep:node_id:retry_count)`; the seam already computes `side_effect_key` (`orchestrator.py:2467`) and the begin/complete machinery exists (`runtime_lifecycle.py:177-201`) — used for claims today, never for the dispatch call itself.
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

### Phase 0b — Run-level crash-resume + exactly-once dispatch (S/M; THE unlock; highest payoff-per-effort)
- New module `dharma_swarm/graph/durable_invoker.py` (new module because orchestrator.py is at its module-budget ceiling): wraps `_orch_invoker`; applies `try_begin_idempotent_side_effect`/`complete_idempotent_side_effect` around the provider call using the existing `side_effect_key`; checks `receipt_json` before executing (memo hit → return prior receipt, no provider call).
- Reconciler: GENERALIZE the existing pattern (Devin verified: `operator_bridge.recover_stale_tasks` + `_mirror_runtime_recovered` already do this for bridge tasks/claims) down to `delegation_runs`. Owner: `SwarmManager` — once at end of `init()` (`swarm.py:551`) + periodically in `tick()` beside `reap_orphaned_tasks` (`swarm.py:2289`, same idiom, wrong database). NOT the API lifespan (best-effort/cancellable, `api/main.py:157-166`); NOT a cron (second process fighting the single writer).
- Boot scan (single host ⇒ anything in-flight at boot is orphaned by definition): `delegation_runs.status IN ('claimed','running') AND quarantined_at IS NULL`; `task_claims.status IN ('claimed','running') AND recovered_at IS NULL AND stale_after < now`. Classify with EXISTING vocabulary: never-ran → `failure_code='claim_timeout'` requeue path; ran-and-died → terminal fail or requeue mirroring `_handle_task_failure` (`orchestrator.py:1987-2055`); retry-exhausted → quarantine stamp per `loop_closure_quarantine.py` convention (never hidden, always tallied). Write `recovered_at` (its first writer on this path). Timestamps compared tz-aware in Python (the `parse_ts` convention, `loop_closure_quarantine.py:48-59`).
- Add the heartbeat: promote `last_heartbeat` out of metadata; executing tasks heartbeat at cadence ≤ stale_after/3 (wire the orphaned `heartbeat_claim_sync`, `runtime_state.py:2062`).
- Triage exception swallows on THIS path only (dispatch/persist/reconcile) — resume is meaningless on a path that swallows; the global ~975-swallow cleanup is Phase 5's problem.
- **Acceptance (chaos receipt required):** kill -9 mid-dispatch → reboot → orphan requeued-or-quarantined, `recovered_at` stamped, zero double provider calls (assert via idempotency records), receipts intact. Plus: 7+ new tests, spine-ownership guard green, `# spine:` headers on any new sqlite-touching module.
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

## §6 Dovetail with the active portfolio

- **This campaign = a new track** (proposed id: `dharmagraph-engine-2026-07`, serves `substrate-nativeness`, owned surfaces: `dharma_swarm/graph/**`, `dharma_swarm/workflow.py`, `dharma_swarm/topology_genome.py`, `dharma_swarm/checkpoint.py`, `tests/test_workflow*.py`, `tests/test_topology_execution.py`, plus this spec). Phase 0b/2 edits to orchestrator.py/swarm.py are hot-path and cross-cutting — coordinate in the track's next-items.
- `loop-closure-2026-06`: Phase 0b IS the durable half of Loop-1 closure (dispatch dropoff becomes a recoverable state, not a corpse label); the reconciler's quarantine path reuses that track's tool and reporting doctrine.
- `orchestration-arena-v1-2026-06`: Phase 6 extends its surfaces through its own next-items; zero-weight doctrine preserved.
- `organism-rewire-2026-07`: D4 sequencing (no standing DarwinEngine unlock before external gradient) binds Phase 6; the VPS item is what makes Phase 0b's reconciler run against a live daemon.
- Receipts upgrade (Phase 4) feeds the `revenue-external-humans-served` gap: EU AI Act Art. 12 (applicable 2026-08-02, ≥6-month log retention, €15M/3% penalties) + AI-agent insurance (AIUC et al. pricing premiums off audit evidence) is the story that makes verifiable execution sellable.

## §7 Proposed track skeleton (for ACTIVE_TRACK.yaml, operator ratifies)

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
