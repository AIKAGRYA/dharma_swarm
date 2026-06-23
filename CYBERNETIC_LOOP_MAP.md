# Cybernetic Loop Map — dharma_swarm

**Last audit:** 2026-06-18T16:49:32Z by `scripts/governance/cybernetics_codex_audit.py --json`
**Previous version:** 2026-05-20 (stale BR-012 surface, retained below as historical context)
**Purpose:** Document every feedback loop's sense→act→evaluate→adapt path.
Each loop is "closed" only when its output feeds back as input to a future cycle.

> **Re-verification pass 2026-06-15 (perplexity-computer):** 26 days / 232 commits since last audit. Code-structural status of all 13 loops is unchanged in the static surface. Two notable code changes since 2026-05-20 worth flagging here without flipping status (runtime closure still depends on live `~/.dharma/` data not visible from cloud seat):
>
> - **Loop 1 (Swarm Task Loop) — spine is wired.** `dharma_swarm/agent_runner.py:55-62` now imports `invoke_agent` and `EvidenceReceipt` directly. The runtime-truth-spine-adoption-2026-06 track stands at 7/8 SHIPPABLE per `docs/governance/ACTIVE_TRACK.yaml`. The remaining gate documented here (working LLM provider with valid API key) is unchanged — a runtime configuration concern, not a code-path concern.
> - **Loop 8 (Recognition).** Wiring from 2026-05-20 (`cascade.py:386-491`, `shakti_executive/inputs.py:100`, `meta_daemon.py`) re-verified present. Status PARTIAL unchanged.
>
> No new BLOCKERs surfaced. The full re-running of "Evidence From ~/.dharma/" section requires live-seat access and is deferred.

---

## Canonical Truth Source

The authoritative projection is now:

```bash
python3 scripts/governance/cybernetics_codex_audit.py --json
```

`delegation_runs.receipt_json` is the orchestrator/spine-dispatch witness column.
It is not the universal closure witness. A2A-surface rows can be successful with
empty `receipt_json` because their canonical witness is `runtime_receipts` plus
idempotency records. For Loop 1, the current production acceptance bar is actual
served provider/model truth in the audited scope, zero `dispatch_dropoff`, and a
bounded replay proving tick N affects tick N+1.

Live runtime truth from the latest audit:

| Surface | Current value |
|---------|---------------|
| `delegation_runs` | 5,222 total, 2,027 completed, 3,144 failed, 50 running, 1 claimed |
| `runtime_receipts` | 17,410 rows, latest 2026-06-18T16:45:05Z |
| `receipt_json` | 669 rows, orchestrator surface only |
| served provider/model truth | 599 completed delegation runs, 1,716 runtime receipts |
| `dispatch_dropoff` | 1,428 failures, latest 2026-06-18T15:02:59Z |
| One Wire quorum | N=3/5, M=1/3, not eligible |
| evolution archive | 11,591 entries, 11,145 internal-positive-fitness risk rows, 0 external authority markers |

Bounded Loop 1 replay proof (current code/provider lane):

| Surface | Current value |
|---------|---------------|
| report | `reports/loop_closure/cybernetics_codex/2026-06-18_loop1_bounded_spine_dispatch.json` |
| command | `python3 scripts/loop1_closure_run.py --tasks 3 --agents 1 --provider ollama --timeout-per-task 180 --tick-sleep 1.0 --report reports/loop_closure/cybernetics_codex/2026-06-18_loop1_bounded_spine_dispatch.json` |
| result | `LOOP1_CLOSED=yes` |
| completed tasks | 3/3 |
| dispatch dropoff | 0 |
| evidence receipts | 3 ok |
| served provider/model truth | 3/3 completed delegation receipts, source `receipt_json` |
| tick errors | 0 |

---

## Loop Status Summary

| # | Loop | Interval | Closed? | Remaining Blocker |
|---|------|----------|---------|-------------------|
| 1 | Swarm Task Loop | 60s | **CLOSED in bounded replay; PARTIAL in all-history audit** | Current bounded replay closes with 3/3 completed tasks, zero dropoff, 3 ok evidence receipts, and served provider/model truth. Standing all-history audit still includes historical `dispatch_dropoff=1428`, so do not call the whole daemon history clean. |
| 2 | Organism Heartbeat | 300s | **PARTIAL** | Runtime substrate is active, but this loop lacks a dedicated closure receipt. |
| 3 | Evolution Loop / DarwinEngine | every 3rd tick | **PARTIAL** | Activity exists, but adaptation/fitness authority is not closure-proven. |
| 4 | Consolidation Loop / Memory | configurable | **PARTIAL** | Runtime substrate is active, but this loop lacks a dedicated closure receipt. |
| 5 | Zeitgeist Scanner | configurable | **PARTIAL** | Runtime substrate is active, but this loop lacks a dedicated closure receipt. |
| 6 | Witness Auditor | 3600s | **PARTIAL** | Audit/receipt activity exists, but current Loop 1 production tie-in is not proven. |
| 7 | Training Flywheel | 300s | **PARTIAL** | Activity exists, but adaptation/fitness authority is not closure-proven. |
| 8 | Recognition Loop / eigenform | 7200s | **PARTIAL** | Activity exists, but adaptation/fitness authority is not closure-proven. |
| 9 | Conductors | 120s | **PARTIAL** | Runtime substrate is active, but this loop lacks a dedicated closure receipt. |
| 10 | Context Agent | 60s | **PARTIAL** | Runtime substrate is active, but this loop lacks a dedicated closure receipt. |
| 11 | Replication Monitor | 3600s | **PARTIAL** | Runtime substrate is active, but this loop lacks a dedicated closure receipt. |
| 12 | Self-Improvement | 3600s | **BLOCKED** | One Wire guardian quorum below threshold: N=3/5, M=1/3. |
| 13 | Free Evolution Grind | 600s | **BLOCKED** | One Wire guardian quorum below threshold: N=3/5, M=1/3. |

**Summary: standing all-history audit is still 0 fully clean, 11 PARTIAL, 2 BLOCKED. Current bounded production replay closes Loop 1 only. The old "1 of 13 closed" reading came from mixing a historical harness receipt, this stale prose map, and live runtime truth; the current map separates standing history from bounded replay proof.**

---

## Evidence From ~/.dharma/ (Audited 2026-05-05)

Data on disk proves the system has been exercised:

| Data Source | Rows/Files | Source |
|-------------|-----------|--------|
| `state/runtime.db` sessions | 27 | SwarmManager test/integration runs |
| `state/runtime.db` task_claims | 42 (all failed) | Orchestrator dispatch attempts |
| `state/runtime.db` delegation_runs | 42 (all failed) | All `dispatch_dropoff` — worker unavailable |
| `state/runtime.db` session_events | 489 | Task lifecycle events (enqueued, claimed, retried) |
| `state/runtime.db` context_bundles | 30 | Context compilation for agent dispatch |
| `witness/*.jsonl` | 1,013 entries | WitnessAuditor test suite assertions |
| `traces/*.jsonl` | 182 entries | Agent dispatch traces (test-origin) |
| `logs/router/routing_decisions.jsonl` | 86 (39 success, 35 fail) | ModelRouter decisions (test suite) |
| `logs/router/route_retrospectives.jsonl` | 3 | Route quality retrospectives |
| `evolution/meta_archive.jsonl` | 3 entries | MetaEvolutionEngine parameter updates |
| `organism_memory/entities.jsonl` | 89 (11 valid) | Heartbeat decisions, algedonic events, gnani verdicts |
| `quality_gates/log/evaluations.jsonl` | 5+ entries | Structural quality gate evaluations |
| `kaizen/ops.db` cron_health | 7 jobs tracked | Pulse, locked pulse, portable pulse, Jagat Kalyan |
| `data/economic_spine.db` | 0 rows | No economic events (depends on Loop 1) |
| `data/corrections.db` | 0 rows | No correction events (depends on Loop 1) |

**Key finding:** Routing decisions show 39 successes across openai (6), anthropic (21), openrouter_free (3), openrouter (9). The router CAN reach providers. The 35 failures are: ollama unreachable (88 attempts), claude_code embedded null byte (84), OPENROUTER_API_KEY not set (18). These are from test fixtures that exercise provider failure paths, not real configuration failures.

**Key finding:** All 42 delegation_runs failed with `dispatch_dropoff` — "Dispatch accepted but worker unavailable (runner=False)". The orchestrator dispatches tasks but `AgentRunner` is not instantiated in the test context. This is NOT a code bug — it's the gap between "test suite exercises routing" and "live orchestrator has a running AgentRunner with a real provider."

---

## Detailed Loop Traces

### Loop 1: Swarm Task Loop (the core loop — everything depends on this)

```
SENSE:   orchestrator.tick() → route_next() → find ready tasks + idle agents
ACT:     orchestrator._execute_task() → agent_runner.run_task() → provider.complete_for_task()
         → router_v1.build_routing_signals() → tiny_router_shadow (heuristic fallback)
         → ModelRouter selects provider → LLM call → response
EVALUATE: orchestrator._execute_task() → on_task_complete():
         - Writes result to shared notes (~/.dharma/shared/)
         - Leaves stigmergy mark (StigmergyStore.leave_mark)
         - Emits SIGNAL_TASK_COMPLETED to signal_bus
         - Records cost in economic_spine
         - Records provenance via telic_seam (record_dispatch + record_gate_decision)
ADAPT:   orchestrator.route_next() reads stigmergy hot_paths to influence routing
         DarwinEngine reads fitness from task outcomes
         DynamicCorrectionEngine detects error_cascade/budget_overrun/dharmic_drift
         route_retrospectives log quality feedback for routing self-correction
```

**What "closed" means:** The orchestrator's routing decisions in tick N+1 are influenced by the outcomes of tick N. Specifically:
- `route_next()` reads `hot_paths()` from stigmergy to prioritize active areas
- `_fitness_biased_pick()` uses agent fitness scores to prefer better agents
- `DynamicCorrectionEngine` signals cause task reassignment or agent retirement

**Current state (updated):** MM-01 (huggingface crash) RESOLVED — heuristic fallback works. MM-02/03 (enum coercion) RESOLVED. Routing decisions succeed in test (39/86). Dispatch fails because `AgentRunner` is not running in test context. **The code path from routing through dispatch is structurally sound. The remaining gap is operational: a running `AgentRunner` with a configured LLM provider.**

---

### Loop 2: Organism Heartbeat

```
SENSE:   organism.heartbeat() computes 4 invariants:
         - criticality (λ_max): spectral radius of agent interaction graph
         - closure_ratio: fraction of loops where output feeds back as input
         - info_retention: fraction of state that persists across ticks
         - diversity_equilibrium: behavioral diversity across agent pool
INTERPRET: OrganismPulse classifies overall health (critical/degraded/healthy)
CONSTRAIN: TelosGatekeeper.check() — should this pulse trigger any action?
PROPOSE:  If health is degraded, propose corrective actions:
         - spawn new agents if diversity is low
         - retire failing agents if error_cascade detected
         - adjust DarwinEngine parameters if convergence stalled
EXECUTE:  Apply proposed actions (spawn, retire, adjust)
EVALUATE: Compare pre/post invariant values
ADAPT:    Update organism state, emit SIGNAL_HEARTBEAT to signal_bus
```

**Current state (updated):** SENSE and INTERPRET work. 5 heartbeat cycles recorded with health=1.00, coherence=0.28. Algedonic events fire (48 entries) including telos drift detection. Gnani verdicts issued (18 entries). Organism correctly identifies "degraded state" and issues HOLD verdicts. Loop supervisor detects NO_PROGRESS and issues PAUSE_LOOP. **This loop is closer to closed than any other — the sense→interpret→constrain path works. Act/adapt blocked on having running agents to act upon.**

---

### Loop 3: Evolution Loop (DarwinEngine)

```
SENSE:   Read fitness scores from completed tasks
         Read stigmergy marks for hotspot detection
         Read routing_memory EWMA for provider performance
ACT:     DarwinEngine.auto_evolve():
         1. AutoProposer.cycle() — scan codebase for improvement opportunities
         2. DarwinEngine.propose() — generate code mutation
         3. TelosGatekeeper.check() — safety gate (AHIMSA, SATYA, etc.)
         4. Apply mutation (diff_applier.py — backup → apply → test → rollback if fail)
         5. Run tests to verify mutation doesn't break anything
EVALUATE: FitnessScore = weighted combination of:
         - correctness (test pass rate)
         - dharmic_alignment (gate scores)
         - performance (jikoku timing)
         - utilization (token efficiency)
         - elegance (code quality heuristics)
         - efficiency (API cost)
         - safety (no security regressions)
ADAPT:   Archive mutation + fitness in evolution/archive.jsonl
         MetaEvolutionEngine adjusts DarwinEngine parameters based on fitness trends
         DiversityArchive (MAP-Elites) tracks behavioral diversity
         Population control spawns/retires agents based on fitness
```

**Current state (updated):** AutoProposer stigmergy guard fixed (MM-10 RESOLVED). MetaEvolutionEngine has recorded 3 meta-parameter updates (meta_fitness=0.58494, n_object_cycles=2). DarwinEngine signature fixed (NEW-02: `_provider` attr removed). **The evolution machinery runs and records data. Real fitness computation blocked on Loop 1 producing completed tasks.**

---

### Loop 4: Consolidation Loop (Memory)

```
SENSE:   Read recent pulse history, agent outputs, shared notes
ACT:     SleepTimeAgent.consolidate_knowledge():
         - Extract entities from text
         - Classify into Propositions (facts) and Prescriptions (recommendations)
         - Store in knowledge graph (graph_nexus)
         NeuralConsolidator (if provider available):
         - Synthesize patterns from multiple sources
         - Generate consolidated memory entries
EVALUATE: Check if consolidated knowledge matches existing entries (dedup)
ADAPT:   MemoryLattice.index_document() — add to searchable memory
         Stigmergy marks with action="dream" — subconscious contributions
         Next agent context compilation includes consolidated knowledge
```

**Current state (updated):** 89 organism_memory entities exist. Consolidation deduplication is working — entities are marked with `invalidation_reason: "consolidated_duplicate_of:..."` and `invalidated_at` timestamps. 11 valid (non-invalidated) entities remain after dedup. **The consolidation pipeline works on organism heartbeat data. No agent-produced outputs exist to consolidate yet.**

---

### Loop 5: Zeitgeist Scanner (Environmental Intelligence)

```
SENSE:   ZeitgeistScanner.scan():
         - _scan_local(): read witness logs, shared notes, gate check patterns
         - _scan_claude(): (optional) use LLM to classify signals
ACT:     Classify signals as: competing_research, tool_release, methodology, threat, opportunity
EVALUATE: Count threats. If high gate block rate detected:
         - Write gate_pressure.json to ~/.dharma/
         - This tightens S3 trust mode (VSM System 3 control)
ADAPT:   Next cycle: telos gates read gate_pressure.json and adjust strictness
         This closes VSM Gap #1: S3↔S4 bidirectional feedback
```

**Current state (updated):** Local scanning works. Witness logs now exist (1,013 entries) providing real gate check data for local scanning to consume. No `gate_pressure.json` written yet. The S3↔S4 loop is structurally present with data now flowing into the sense path.

---

### Loop 6: Witness Auditor (Random Audit)

```
SENSE:   WitnessAuditor randomly samples agent behavior
ACT:     Evaluate action against dharmic principles (AHIMSA, SATYA, etc.)
EVALUATE: Score output on dharmic dimensions
ADAPT:   Record witness observation to ~/.dharma/witness/
         Emit SIGNAL_WITNESS_ALERT if violation detected
         Evolution engine uses witness scores as fitness signal
```

**Current state (updated):** **Fully functional in test context.** 1,013 witness entries recorded across 2 days. Correctly BLOCKED destructive filesystem commands (AHIMSA violation). PASSED 444 actions, BLOCKED 230, WARNED 4. Provider mismatch (MM-11) RESOLVED — uses `OpenRouterFreeProvider`. Phases audited: before_write (394), before_complete (144), before_pivot (134), conductor_wake (2), before_git (2), before_debug (2). **This loop closes when real agent actions replace test-generated actions.**

---

### Loop 7: Training Flywheel

```
SENSE:   trajectory_collector reads recent agent execution traces
ACT:     thinkodynamic_scorer scores each trajectory on quality dimensions
         strategy_reinforcer uses UCB1 to select winning patterns
EVALUATE: Compare strategy effectiveness over time
ADAPT:   dataset_builder creates training JSONL for fine-tuning
         Strategy patterns are fed back into agent system prompts
         UCB exploration/exploitation balance shifts based on accumulated evidence
```

**Current state (updated):** 182 trace entries exist. Quality gate evaluations running (structural scorer). No real agent trajectories to score yet — traces are from test fixtures.

---

### Loop 8: Recognition Loop (Strange Loop / Eigenform)

```
SENSE:   Read cascade history (39 entries in 5 domains)
ACT:     Compute recognition seed — system's self-model
         Run cascade F(S)=S across domains until convergence (eigenform)
EVALUATE: Did the cascade converge? What fitness did each domain reach?
ADAPT:   Write recognition_seed.md to ~/.dharma/meta/
         Update catalytic_graph.json (autocatalytic set detection)
         The recognition seed influences future agent system prompts
```

**Current state (updated 2026-05-20):** Recognition seed computation is wired: `cascade.py:386-491` feeds loop results back into the seed, `shakti_executive/inputs.py:100` reads it as an executive signal, `meta_daemon.py` includes it in context health. 89 organism_memory entities provide input. Periodic trigger depends on LoopEngine schedule activation.

---

### Loops 9-13: Dependent Loops

| Loop | Status | Update |
|------|--------|--------|
| 9: Conductors | PARTIAL | Cron health tracks 7 jobs. Conductor configs use proper enums. Blocked on LLM provider for actual conductor work. |
| 10: Context Agent | NO | Depends on Loop 1 (running AgentRunner). MM-01 resolved. Dispatch IS available (keyless claude_code). |
| 11: Replication Monitor | PARTIAL | MM-02/03 RESOLVED. Replication path structurally correct. No trigger events yet. |
| 12: Self-Improvement | NO | DarwinEngine instantiable. `auto_evolve()` fixed. Requires `DHARMA_SELF_IMPROVE` (dispatch is available, see below). |
| 13: Free Evolution Grind | NO | Router works AND dispatch is available keyless (claude_code); needs the evolution cadence wired, not a key. |

---

## Which Loops Close First — dispatch is ALREADY available (no key needed)

**Correction (2026-06-23):** the long-standing "needs a provider key / no real provider" claim was FALSE. The `claude_code` lane is **keyless** and live whenever the `claude` binary is on PATH (every Claude Code web/remote/CI session) — verified by a real completion. The single source of truth is `key_oracle.dispatchable_now()` (surfaced in `make onboard`), NOT a frozen line in this map. With 0 BLOCKERs remaining, the cascade is purely operational and a key is **optional** (only to add OTHER providers).

**Step 1: confirm dispatch** — `python3 -c "from dharma_swarm.key_oracle import dispatchable_now; print(dispatchable_now())"` (claude_code = keyless). Add `OPENROUTER_API_KEY` / ollama only to widen the roster.

**Immediately closeable (dispatch already available, keyless):**
- Loop 1 (Swarm Task) — routing works, dispatch path clear, keyless claude_code lane is live; just needs `AgentRunner` wired into the live loop
- Loop 6 (Witness) — already works on test data, will audit real actions immediately
- Loop 2 (Organism Heartbeat) — invariants will compute real data

**Closeable after first task completes:**
- Loop 5 (Zeitgeist) — witness logs + gate check data enable real scanning
- Loop 9 (Conductors) — conductor configs are correct, just need provider

**Closeable after ~10 tasks complete:**
- Loop 3 (Evolution) — enough fitness data for real DarwinEngine proposals
- Loop 4 (Consolidation) — enough agent outputs to consolidate
- Loop 7 (Flywheel) — enough trajectories to score and reinforce

**Closeable after ~100 tasks:**
- Loop 8 (Recognition) — enough data for eigenform convergence
- Loops 10-13 (dependent loops) — enough system stability

---

## Verification Checklist

After configuring a provider, run these commands to verify loop closure:

```bash
# Loop 1: Did a task complete?
dgc status  # Tasks Completed > 0

# Loop 2: Did invariants move?
dgc organism-pulse --dry-run  # criticality > 0, closure > 0

# Loop 3: Does evolution have real data?
dgc evolve trend  # fitness entries from real tasks

# Loop 4: Does memory have content?
dgc memory  # memory entries > 0

# Loop 5: Did zeitgeist find signals?
dgc loops  # Check signal bus status

# Loop 6: Did witness produce observations?
ls ~/.dharma/witness/  # witness log files exist with real agent actions

# The acid test: run two consecutive ticks and check if tick 2 is different from tick 1
# If the orchestrator routes differently on tick 2 because of tick 1's outcome,
# the loop is closed.
```

---

*This document was last audited on 2026-05-05 against HEAD `74d015c`. Previous version: 2026-04-04. See `INTERFACE_MISMATCH_MAP.md` for the current mismatch status (0 BLOCKERs, 4 DEGRADED).*
