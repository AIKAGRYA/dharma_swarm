# Cybernetic Loop Map — dharma_swarm

**Last audit:** 2026-07-02T01:42:15Z by `scripts/governance/cybernetics_codex_audit.py --json`
**Previous version:** 2026-05-20 (stale BR-012 surface, retained below as historical context)
**Purpose:** Document every feedback loop's sense→act→evaluate→adapt path.
Each loop is "closed" only when its output feeds back as input to a future cycle.

> **Claim boundary:** `scripts/governance/cybernetics_codex_audit.py` is a
> read-only verifier over receipts and bounded replay outputs. It does **not**
> re-execute live owner-surface checks. `HARNESS_PROVEN` means a bounded replay
> passed; `CLOSED_LIVE` requires a separate live owner-surface proof on the
> daemon branch that actually runs. Current production-live closure claim:
> `CLOSED_LIVE: 0/13`.
> This PR does not claim production-live closure of any loop. `HARNESS_PROVEN
> 11/13` means bounded replay harnesses pass; it does not mean the loops are
> closed in production.

> **Re-verification pass 2026-06-15 (perplexity-computer):** 26 days / 232 commits since last audit. Code-structural status of all 13 loops is unchanged in the static surface. Two notable code changes since 2026-05-20 worth flagging here without flipping status (runtime closure still depends on live `~/.dharma/` data not visible from cloud seat):
>
> - **Loop 1 (Swarm Task Loop) — spine is wired.** `dharma_swarm/agent_runner.py:55-62` now imports `invoke_agent` and `EvidenceReceipt` directly. The runtime-truth-spine-adoption-2026-06 track currently has 7/8 criteria passing but remains unshipped under the rigorous bar. The remaining gate is a *proven dispatchable provider in the live seat*; `claude_code` is keyless only when headless `claude -p` smokes green, and local Ollama may be the current live fallback.
> - **Loop 8 (Recognition).** Wiring from 2026-05-20 (`cascade.py:386-491`, `shakti_executive/inputs.py:100`, `meta_daemon.py`) was re-verified present. This historical PARTIAL note is superseded by the 2026-07-01 bounded replay closure below.
>
> No new BLOCKERs surfaced. The full re-running of "Evidence From ~/.dharma/" section requires live-seat access and is deferred.

---

## Canonical Truth Source

The authoritative projection is now:

```bash
python3 scripts/governance/cybernetics_codex_audit.py --json
```

Latest machine projections:

- JSON: `reports/loop_closure/cybernetics_codex/latest_audit.json`
- Markdown: `reports/loop_closure/cybernetics_codex/latest_audit.md`

`delegation_runs.receipt_json` is the orchestrator/spine-dispatch witness column.
It is not the universal closure witness. A2A-surface rows can be successful with
empty `receipt_json` because their canonical witness is `runtime_receipts` plus
idempotency records. For Loop 1, the current production acceptance bar is actual
served provider/model truth in the audited scope, zero `dispatch_dropoff`, and a
bounded replay proving completed tasks leave an adaptive signal for later routing.

Live runtime truth from the latest audit:

(hand-copied from `reports/loop_closure/cybernetics_codex/latest_audit.json`
observed 2026-07-02T13:47Z — if this table disagrees with that JSON, trust the JSON)

| Surface | Current value |
|---------|---------------|
| `delegation_runs` | 8,837 total, 4,184 completed, 4,532 failed, 120 running, 1 claimed |
| `runtime_receipts` | 105,029 rows, latest 2026-07-02T13:15:59Z |
| `receipt_json` | 8,837 rows |
| served provider/model truth | 1,943 completed delegation runs, 24,700 runtime receipts |
| `dispatch_dropoff` | 2,191 historical failures, latest 2026-07-01T16:45:35Z |
| One Wire quorum | N=3/5, M=1/3, not eligible |
| evolution archive | 12,273 entries, 11,391 internal-positive-fitness risk rows, 0 external authority markers |

Bounded Loop 1 replay proof (current code/provider lane):

| Surface | Current value |
|---------|---------------|
| report | `reports/loop_closure/cybernetics_codex/2026-06-23_loop1_ollama_fresh_spine_dispatch.json` |
| command | `uv run python scripts/loop1_closure_run.py --canonical --provider ollama --model llama3.2:latest --tasks 3 --agents 1 --timeout-per-task 180 --tick-sleep 1.0 --report reports/loop_closure/cybernetics_codex/2026-06-23_loop1_ollama_fresh_spine_dispatch.json` |
| result | `LOOP1_CLOSED=yes` |
| completed tasks | 3/3 |
| dispatch dropoff | 0 |
| evidence receipts | 3 ok |
| served provider/model truth | 3/3 new task receipts verified in `delegation_runs.receipt_json` with `provider=ollama`, `model=llama3.2:latest`, `operation=invoke_agent`, `status=ok` |
| tick errors | 0 |
| adapt signal | 3 run-attributed stigmergy marks; `adapt_fired=true` |

---

## Loop Status Summary

| # | Loop | Interval | Current Verdict | Remaining Live-Closure Blocker |
|---|------|----------|---------|-------------------|
| 1 | Swarm Task Loop | 60s | **HARNESS_PROVEN; not CLOSED_LIVE** | Current bounded replay proves 3/3 completed tasks, zero replay dropoff, 3 ok evidence receipts, and served provider/model truth. Standing all-history audit still includes historical `dispatch_dropoff`, so do not call the daemon history clean. |
| 2 | Organism Heartbeat | 300s | **HARNESS_PROVEN; not CLOSED_LIVE** | Receipt proves 3 harness cycles and fed-forward algedonic state. Live closure still needs standing daemon pulse/algedonic owner-surface evidence consumed by a later daemon cycle. |
| 3 | Evolution Loop / DarwinEngine | every 3rd tick | **HARNESS_PROVEN; not CLOSED_LIVE** | Receipt proves scratch Darwin outcomes feed predictor/archive selection without touching live archive fitness. Live closure still needs governed non-scratch evolution owner-surface evidence. |
| 4 | Consolidation Loop / Memory | configurable | **HARNESS_PROVEN; not CLOSED_LIVE** | Receipt proves memory/context mechanics, but the sensed work is harness-owned evidence. Live closure needs external/completed work consolidated from the memory owner surface and consumed by later context. |
| 5 | Zeitgeist Scanner | configurable | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness proves internal S3/S4 gate-pressure feedback. It does not prove external-world zeitgeist sensing or live environmental owner-surface closure. |
| 6 | Witness Auditor | 3600s | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness proves witness/governance mark feedback. Live closure needs production completions audited from the live witness/runtime receipt surface and consumed downstream. |
| 7 | Training Flywheel | 300s | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness seeds and scores its own trajectory JSONL. Live closure needs recent non-synthetic trajectory owner-surface rows that the flywheel scores and persists into later strategy selection. |
| 8 | Recognition Loop / eigenform | 7200s | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness proves recognition seed mechanics from receipt history. Live closure needs non-scratch loop-history owner receipts generating a seed later consumed by agent context. |
| 9 | Conductors | 120s | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness proves conductor signal -> action -> scheduler state -> later scheduler read. Live closure needs production scheduler state changed by observed signals and consumed by a later tick. |
| 10 | Context Agent | 60s | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness proves context package mechanics. Live closure needs production memory inputs changing a served context package later read by an agent. |
| 11 | Replication Monitor | 3600s | **HARNESS_PROVEN; not CLOSED_LIVE** | Harness proves durable proposal -> child/probation/roster -> later monitor read. Live closure needs a real proposal materialized into live roster/probation and observed later. |
| 12 | Self-Improvement | 3600s | **BLOCKED** | One Wire guardian quorum below threshold: N=3/5, M=1/3; `tests/test_one_wire_archive_fitness_guard.py` proves archive fitness fails closed without N>=5, M>=3, and explicit authority. |
| 13 | Free Evolution Grind | 600s | **BLOCKED** | Same One Wire guard: free-evolution authority remains blocked until external quorum and explicit archive-fitness authority exist. |

**Summary: standing all-history audit is still not daemon-clean because historical `dispatch_dropoff` rows remain. Bounded replays now prove regression harnesses for Loops 1-11; they do not prove production-live closure. Loops 12/13 remain BLOCKED behind One Wire. Promote a loop to `CLOSED_LIVE` only after its declared live owner-surface criterion passes on the daemon branch that actually runs.**

---

## Historical Evidence From ~/.dharma/ (Audited 2026-05-05; Superseded)

Historical data on disk proved the system had been exercised as of 2026-05-05.
This section is retained for archaeology only and is superseded by
`reports/loop_closure/cybernetics_codex/latest_audit.json` for current counts
and by the `HARNESS_PROVEN`/`CLOSED_LIVE` verdict tiers for current claims.

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

**Current state (updated 2026-07-02): HARNESS_PROVEN, not CLOSED_LIVE.** `scripts/loop3_evolution_closure_run.py` runs local DarwinEngine behavioral probes, constrains a bounded scratch-only proposal, gate-checks it, records evaluated fitness in a scratch archive, then proves a later proposal/predictor/parent-selection cycle reads the changed predictor/archive state. It explicitly does not write live archive fitness.

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

**Current state (updated 2026-07-02): HARNESS_PROVEN, not CLOSED_LIVE.** `scripts/loop4_10_memory_context_closure_run.py` senses completed work artifacts, admits only completed/hash-backed evidence, writes real StrangeLoopMemory rows, consolidates META memory, then proves later `get_context()` and `read_recent_memories()` read the marker. Live closure still needs external/completed owner-surface work rather than the closure harness's own file evidence.

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

**Current state (updated 2026-07-02): HARNESS_PROVEN, not CLOSED_LIVE, for the internal S3/S4 arm only.** `scripts/loop5_zeitgeist_closure_run.py` drives gate checks on harmful actions through the `TelosGatekeeper` (each BLOCK lands a `BLOCKED` witness entry), the `InternalPressureScanner` reads the block rate, a high block rate becomes a threat signal, `_write_gate_pressure` writes `gate_pressure.json`, and the gatekeeper's `_apply_gate_pressure` resolves trust mode `internal_yolo -> external_strict` on its next check. This does **not** prove real-world/external zeitgeist sensing.

#### Loop 5b: World Radar Go chain (external arm)

```
SENSE:   go_bridge.run_world_radar_go_once() collects raw world observations
         (operator drops, world feeds, optional world_scout_go fetch)
ACT:     tools/world_signal_ingestor_go (prebuilt binary or `go run .`)
         normalizes observations into scored signals; --min-score gate drops
         low-signal rows; one go_evidence_receipt.v0 per accepted signal
         lands in ~/.dharma/go_receipts/world/
EVALUATE: receipt_bridge summarizes receipts; project_world_signal_receipts
         projects accepted receipts back into the world-signal feed
ADAPT:   the next pass's board/brief/health are rebuilt from receipt-projected
         rows; per-source failures surface as structured `source_errors` in
         world_radar_health.json and the control-surface `go.world_radar_health`
         row; invocation mode (binary vs go_run vs needs_host) is receipted in
         health. Invocation is toolchain-checked (`go_invoke._go_invocation`):
         with neither a prebuilt binary nor a Go toolchain the bridge never
         invokes — it records a structured `needs_host` source error naming
         `make go-build`, and the cockpit row flags `go_world_radar_needs_host`.
```

**Current state (updated 2026-07-02, organism-rewire-2026-07): CLOSED via bounded replay on a committed fixture observation (no live fetch).** `scripts/loop5b_world_radar_closure_run.py` runs the REAL Go ingestor via `go_bridge` on `tests/fixtures/world_radar_go/loop5b_observations.jsonl`: fixture read (sense), Go process scores signals (interpret), min-score drops the noise row — emitted < raw (constrain), exactly one EvidenceReceipt per emitted signal with summarize + feed projection matching (act), and the receipt store grows across cycles while `world_radar_health.ingest_run_id` changes, fed forward into the next pass's board (adapt). Receipt: `reports/loop_closure/cybernetics_codex/2026-07-02_loop5b_world_radar_closure.json` (LOOP5B_CLOSED=yes, invocation_mode=binary). The check is HOST-AWARE per the rewire doctrine: on a host with neither a prebuilt binary (`make go-build`) nor a Go toolchain it reports `NEEDS_HOST` and exits 0 instead of failing. Live public-source fetch (world_scout_go against the network) is explicitly **not** proven by this closure.

Verification:

```bash
make go-build   # optional: prebuilt binaries; falls back to `go run .`
python3 scripts/loop5b_world_radar_closure_run.py --cycles 2
# expect LOOP5B_CLOSED=yes (or NEEDS_HOST on a host without Go)
```

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

**Current state (updated 2026-07-02): HARNESS_PROVEN, not CLOSED_LIVE.** The harness exercises the completion-trace -> Witness -> governance-mark feedback path and the audit recomputes that the receipt has all five transitions and fed-forward adaptation. Live closure still requires production completions from the live witness/runtime receipt owner surface and downstream consumption of those governance marks.

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

**Current state (updated 2026-07-02): HARNESS_PROVEN, not CLOSED_LIVE.** `scripts/loop7_training_flywheel_closure_run.py` seeds persisted trajectory JSONL in its own replay state, scores it with `ThinkodynamicScorer`, applies score thresholds, writes strategy and dataset state, then proves a fresh `StrategyReinforcer` changes the next prompt from the persisted pattern. Live closure requires recent non-synthetic trajectory owner-surface rows.

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

**Current state (updated 2026-07-02): HARNESS_PROVEN, not CLOSED_LIVE.** `scripts/loop8_recognition_closure_run.py` reads loop-history receipts, derives a receipt-hash-bound self-model, runs `RecognitionEngine.synthesize()` into private replay state, and proves later `build_agent_context()` reads the recognition seed. Live closure requires non-scratch loop-history owner receipts and a later live context consumer.

---

### Loops 9-13: Dependent Loops

| Loop | Status | Update |
|------|--------|--------|
| 9: Conductors | HARNESS_PROVEN | `scripts/loop9_11_conductor_replication_closure_run.py` proves conductor signal -> action -> scheduler state -> later scheduler read. Live closure still needs production scheduler owner-surface evidence. |
| 10: Context Agent | HARNESS_PROVEN | `scripts/loop4_10_memory_context_closure_run.py` proves context assembly reads consolidated memory and writes a changed context package. Live closure still needs production memory inputs changing a served context package. |
| 11: Replication Monitor | HARNESS_PROVEN | `scripts/loop9_11_conductor_replication_closure_run.py` proves durable proposal -> materialized child/probation/roster -> later monitor read. Live closure still needs live proposal/roster/probation evidence. |
| 12: Self-Improvement | BLOCKED | One Wire N=3/5, M=1/3. `dharma_swarm/archive.py` now fails closed for governed nonzero archive-fitness writes without N>=5, M>=3, and explicit authority. |
| 13: Free Evolution Grind | BLOCKED | Same One Wire guard. Free-evolution/archive-fitness authority remains unavailable until external quorum truth exists. |

---

## Live-Closure Promotion Sketch — non-claim roadmap

**Correction (2026-06-23):** the long-standing "needs a provider key / no real provider" claim was too broad. The `claude_code` lane uses the Claude Code login rather than a project API key, but it is live only when headless `claude -p` can complete now; a binary on PATH is not enough. The single source of truth is `key_oracle.dispatchable_now()` (surfaced in `make onboard`), NOT a frozen line in this map. If `claude -p` fails authentication, Loop 1 is not live on that host until Claude Code auth is repaired or another provider is proven live.

**Step 1: confirm dispatch** — `python3 -c "from dharma_swarm.key_oracle import dispatchable_now; print(dispatchable_now())"`. `claude_code` is keyless only if the command's headless smoke proves it; add/repair Ollama or keyed providers to widen the roster.

The bullets below are planning notes, not closure assertions. A loop only
promotes to `CLOSED_LIVE` after the declared live owner-surface criterion passes
on the daemon branch that actually runs.

**First candidates after `dispatchable_now()` is non-empty:**
- Loop 1 (Swarm Task) — routing works and dispatch path is clear; needs a proven live provider and `AgentRunner` wired into the live loop
- Loop 6 (Witness) — already works on test data, will audit real actions immediately
- Loop 2 (Organism Heartbeat) — invariants will compute real data

**Candidates after first task completes:**
- Loop 5 (Zeitgeist) — witness logs + gate check data enable real scanning
- Loop 9 (Conductors) — conductor configs are correct, just need provider

**Candidates after ~10 tasks complete:**
- Loop 3 (Evolution) — enough fitness data for real DarwinEngine proposals
- Loop 4 (Consolidation) — enough agent outputs to consolidate
- Loop 7 (Flywheel) — enough trajectories to score and reinforce

**Candidates after ~100 tasks:**
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

# Loop 5b: Does the world-radar Go chain close on a fixture?
python3 scripts/loop5b_world_radar_closure_run.py  # LOOP5B_CLOSED=yes (or NEEDS_HOST)

# Loop 6: Did witness produce observations?
ls ~/.dharma/witness/  # witness log files exist with real agent actions

# The acid test: run two consecutive ticks and check if tick 2 is different from tick 1
# If the orchestrator routes differently on tick 2 because of tick 1's outcome,
# the loop is closed.
```

---

*Verdicts and runtime numbers are owned by `reports/loop_closure/cybernetics_codex/latest_audit.json` (header carries the last-audit date). See `INTERFACE_MISMATCH_MAP.md` for current mismatch status — no counts frozen here.*
