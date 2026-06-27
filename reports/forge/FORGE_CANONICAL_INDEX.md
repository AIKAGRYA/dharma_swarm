# Dharma Forge Proving Ground Canonical Index

Date: 2026-06-26 JST
Status: canonical Forge Proving Ground lineage, benchmark ladder, and
overnight-run contract
Semantic Commons object: `semobj.dharma_forge_proving_ground` /
`DharmaForgeProvingGround`
Authority: this is the highest Dharma Forge Proving Ground-specific document.
It is subordinate to the global repo governance stack, Semantic Commons,
runtime truth, and current source code for live-state facts, but it is the
first-stop reference for any agent asked to run, audit, summarize, or evolve
the Forge Proving Ground machinery.

## Canonical Verdict

Yes: the strongest external test for Dharma Swarm is the Dharma Forge Proving
Ground: run the whole swarm, including its coordination spine, verifier gates,
receipt machinery, and Karpathy/DGM-style autoresearch loop, against a small
set of official external benchmarks over and over.

The correct target is not one benchmark and not one celebratory run. The target
is a repeated, budget-matched, receipt-complete external evaluation loop across
3-5 benchmark families, with strong single-agent controls and final-use
coordination evidence.

Forge Arena is folded in, but only as the internal harness and contamination
control layer. It is not external proof by itself.

The current practical truth:

- There is no single production-grade command yet that honestly runs the full
  100-iteration, 3-5 benchmark external loop.
- The most robust official external runner currently present is the Forge v1
  SWE-bench Verified path in `/Users/dhyana/ds_forge_v1_scoreboard`.
- The repo-local Forge Swarm Evolution Arena v0 path is useful for preflight,
  sealed local tasks, budget parity, and receipt discipline, but v0 already
  failed to prove swarm superiority.
- Future operator shorthand must resolve to `run the Forge Proving Ground` or
  `run the canonical Forge Proving Ground external loop`. Bare `run Forge` is
  legacy shorthand only: agents may normalize it to the Proving Ground, but it
  is not preferred operator language. The bare phrase "run the thing" is
  intentionally forbidden in Semantic Commons because it is ambiguous outside a
  local conversation.

## Main Purpose

Dharma Forge Proving Ground is the swarm's epistemic furnace and external
reality-test ground.

It folds the historical Dharma Forge machinery into a clearer umbrella: Forge
names the reward membrane and refinement lineage; Proving Ground names the
measured external reality gate. Its purpose is to turn agent activity into
trusted learning signal:

1. propose an intervention;
2. run it against a real verifier;
3. compare it against strong controls;
4. record receipts, cost, failures, contamination state, and coordination edges;
5. decide whether to kill, hold, mutate, scale, or archive;
6. prevent fake progress from entering routing, memory, fitness, public claims,
   or self-evolution.

In one sentence: the Dharma Forge Proving Ground exists to answer whether the
organism actually improved, or merely produced more convincing activity.

## Naming Hierarchy

| Name | Canonical Meaning | Operator Status |
|---|---|---|
| Dharma Forge Proving Ground | Canonical umbrella for external swarm evolution and hardening through measured reality. | Preferred. |
| Forge Proving Ground | Short preferred name for the same umbrella. | Preferred. |
| Dharma Forge | Legacy/root machinery: reward forge, receipt scoring, Hydra lineage, and fitness membrane. | Active legacy alias, not the full umbrella by itself. |
| Forge Arena | Internal/local competitive or collaborative task arena. | Subsystem only. |
| Forge Swarm Evolution Arena v0/v1 | Concrete measurement generations. | Historical/current implementation names. |
| External Benchmark Loop | Benchmark adapters: SWE-bench, Terminal-Bench, tau3-bench, CodeClash, MultiAgentBench/MARBLE. | Execution layer. |
| Pudgala Autopoiesis Protostar | Separate anti-slop governance and evidence mechanism. | Never Forge; never the Proving Ground. |

## Five Evolutionary Levels

| Level | Name | Core Question | Current Status | Authority |
|---|---|---|---|---|
| 1 | Quality Forge | Is this artifact good? | Implemented in `dharma_swarm/quality_forge.py` and March heat-engine notes. | Diagnostic only. |
| 2 | Hydra / Work Packet Arena | Can repeated agent cycles improve the organism? | Large packet history exists in `reports/agentops/work_packets/`. | Internal dense evidence only. |
| 3 | Forge v0 Sealed Measurement | Does swarm beat best-single and same-budget Self-MoA on controlled local tasks? | Ran 10 valid local measurements; six-agent critique recorded negative result. | Do not evolve from v0. |
| 4 | Forge v1 Falsification Harness | Did coordination causally improve final output under equal budget? | Protocol exists; offline scoreboard and real SWE-bench runner exist in worktree. | Candidate research evidence. |
| 5 | External Evolution Furnace | Can official benchmark evidence safely drive self-improvement? | Target architecture is clear; full 3-5 benchmark overnight wrapper is not yet complete. | No archive fitness mutation until gates pass. |

## Canonical Source Map

| Surface | Path | Meaning |
|---|---|---|
| This index | `reports/forge/FORGE_CANONICAL_INDEX.md` | Canonical operator map and run contract. |
| Quality genesis | `reports/architectural/strange_loop_swarm_20260314/05_quality_forge_efficiency.md` | Forge as marginal quality gain per cost, not raw cycle count. |
| Quality implementation | `dharma_swarm/quality_forge.py` | Artifact scorer and self-scoring strange loop. |
| Hydra archaeology | `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md` | History of Forge/Hydra generations and missing restart truth. |
| Rehydration goal | `docs/agent_tasks/2026-06-12_forge_rehydration_benchmark_evolution_goal.md` | Bounded pilot contract and fake-green traps. |
| v0 launch packet | `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md` | Local sealed task measurement contract. |
| v0 runner | `scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py` | Current repo-local v0 measurement runner. Requires Python 3.11+. |
| v0 preflight | `scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py` | Mechanical gate for local task pack, roster, and ROI. |
| v0 10-run handoff | `docs/agent_tasks/2026-06-17_forge_v0_10x_measurement_goal_handoff.md` | Minimum 10 valid runs before mutation; no mutation without second lease. |
| Six-agent critique | `reports/forge/swarm-uplift-six-agent-critique/20260618T020732Z/decision_packet.md` | Negative v0 verdict and v1 direction. |
| v1 protocol | `reports/forge/swarm-uplift-six-agent-critique/20260618T020732Z/forge_v1_or_v2_protocol.md` | Falsification harness, arms, receipts, and claim gates. |
| v1 code | `/Users/dhyana/ds_forge_v1_scoreboard/dharma_swarm/forge_v1/` | Offline scoreboard plus real SWE-bench Verified runner. |
| v1 real runner | `/Users/dhyana/ds_forge_v1_scoreboard/dharma_swarm/forge_v1/run_real.py` | Current strongest official external runner: SWE-bench Verified, Docker-graded. |
| v1 SWE adapter | `/Users/dhyana/ds_forge_v1_scoreboard/dharma_swarm/forge_v1/swebench_real.py` | Official SWE-bench Docker harness adapter. |
| v1 runtime receipts | `/Users/dhyana/.dharma/forge_v1/` | Runtime artifacts, not repo source. |

## External Benchmark Ladder

The canonical external ladder should use benchmark families that test different
organs of the organism. A 100-iteration overnight run should not be 100 repeats
of one easy instance.

| Benchmark Family | Why It Belongs | Current Canonical Role |
|---|---|---|
| SWE-bench family: Verified, Lite, Multilingual, Multimodal | Repository-level software repair with official resolved metric and Docker grading. | Primary DGM/code-repair fitness signal. |
| Terminal-Bench | Long-horizon terminal tasks with sandboxed execution and tests. | Operator/terminal autonomy and real tool use. |
| tau3-bench | Tool-agent-user reliability across customer-service domains, knowledge, and voice modes. | Policy-following, tool consistency, and repeated pass reliability. |
| CodeClash | Goal-oriented software engineering across multi-round arenas. | Open-ended iteration, logs-to-improvement, competitive adaptation. |
| MultiAgentBench / MARBLE | Explicit multi-agent coordination, topology, collaboration, and competition. | Direct swarm-topology evidence. |

External source anchors:

- SWE-bench: https://www.swebench.com/
- Terminal-Bench: https://www.tbench.ai/
- tau3-bench: https://github.com/sierra-research/tau2-bench
- CodeClash: https://codeclash.ai/
- MultiAgentBench / MARBLE: https://github.com/MultiagentBench/MARBLE

## What "Run The Forge Proving Ground For 100 Iterations Overnight" Means

When the operator says:

```text
Run the canonical Forge Proving Ground external loop for 100 iterations overnight.
```

the agent must interpret it as:

1. Read this file before taking action.
2. Pin the audited checkout and Python 3.13 venv.
3. Start or attach a bounded `ds-goal` mission.
4. Run the strongest available Forge Proving Ground external benchmark path.
5. Use Forge Arena/v0 only as a preflight and internal control layer.
6. Run paired controls, not only the full swarm.
7. Emit receipts under `reports/forge/` and runtime artifacts under
   `/Users/dhyana/.dharma/forge_v1/` or the mission state root.
8. Stop with one of the valid closeout states.
9. Do not mutate archive fitness, production routing, public claims, memory
   canon, or benchmark submissions unless a separate explicit lease grants it.

## Required Control Arms

Every official external task class should run as many of these arms as feasible:

| Arm | Required Purpose |
|---|---|
| `frontier_single_full_budget` | Strongest single model or scaffold with equal or greater budget. |
| `best_of_n_same_model` | Controls for sampling/search without swarm coordination. |
| `same_budget_self_moa` | Controls for same-budget self-aggregation. |
| `planner_builder_verifier_no_a2a` | Controls for structured workflow without standing bus. |
| `full_a2a_swarm` | Tests the full swarm and A2A coordination path. |
| `topology_variants` | Tests star, chain, graph, blackboard, debate, and adversarial verifier variants when cost permits. |

An agent message, transport ack, or handoff does not count as useful
coordination unless it reaches domain receipt plus final incorporation, or
final-use proof with source spans and before/after artifact hashes.

## Karpathy / DGM Autoresearch Loop

The evolution loop must be:

1. Select a benchmark task or task slice.
2. Run controls and swarm under matched budget.
3. Score through the official verifier.
4. Write failure capsules for every miss, timeout, malformed output, or
   coordination stall.
5. Mutate only an isolated candidate: prompt, topology, role allocation,
   verifier gate, retrieval policy, tool affordance, or model roster.
6. Re-run against held-out or preregistered benchmark tasks.
7. Archive both winners and losers as stepping stones.
8. Promote nothing to production until claim gates pass.

The verifier is the fitness function. Self-report is not fitness.

## Current Runnable Paths

### A. Local v0 preflight and internal measurement

Use this to prove local Forge Arena mechanics and receipts. This is not
external proof.

```bash
cd /Users/dhyana/dharma_swarm
/Users/dhyana/dharma_swarm/.venv/bin/python -m py_compile \
  scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py \
  scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py \
  scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py

/Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py \
  --run-dir reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight \
  --max-tasks 1 \
  --timeout-seconds 240 \
  --json
```

### B. Current strongest official external path: Forge v1 SWE-bench

Use this for the current real external proof lane. It is slow on Apple silicon
because the official SWE-bench Docker harness runs amd64 images under emulation.
Native x86_64 Linux is the scale path.

```bash
cd /Users/dhyana/ds_forge_v1_scoreboard
PYTHONPATH=/Users/dhyana/ds_forge_v1_scoreboard \
  /Users/dhyana/dharma_swarm/.venv/bin/python \
  -m dharma_swarm.forge_v1.run_real \
  --instances django__django-12209 \
  --best-of-n 3 \
  --budget 20000 \
  --grade-timeout 1800
```

This command emits full result JSON under:

```text
/Users/dhyana/.dharma/forge_v1/
```

### C. Canonical ds-goal front door

The installed `ds-goal` wrapper uses `python3`, so the repo venv must be placed
first in `PATH` on this machine. Do not rely on the system Python 3.9 default.

```bash
cd /Users/dhyana/dharma_swarm
MISSION_ID="forge-canonical-external-100-$(date -u +%Y%m%dT%H%M%SZ)"

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/.dharma/bin/ds-goal init \
  --mission-id "$MISSION_ID" \
  --title "Forge Proving Ground Canonical External 100" \
  --goal "Run the canonical Forge Proving Ground external benchmark loop from reports/forge/FORGE_CANONICAL_INDEX.md: use official external benchmarks where implemented, run matched controls, record receipts, harvest failures, and do not mutate production, archive fitness, router, memory canon, or public claims." \
  --allowed-write /Users/dhyana/dharma_swarm \
  --verifier-command "Read reports/forge/FORGE_CANONICAL_INDEX.md; validate receipt completeness, controls, budget parity, contamination state, and closeout state." \
  --json

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/.dharma/bin/ds-goal run \
  --mission-id "$MISSION_ID" \
  --duration-hours 8 \
  --dispatch-mode tmux \
  --json

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/.dharma/bin/ds-goal status \
  --mission-id "$MISSION_ID" \
  --board-cards \
  --json
```

Important: this is the canonical mission front door, not proof that the full
3-5 benchmark adapter suite exists. If the executor cannot find a complete
external-loop runner, it must close as `blocked_with_evidence` and name the
missing adapter/wrapper.

## Missing Before the True One-Phrase Overnight Run

The following must exist before the operator phrase can honestly launch the full
100-iteration organism test without extra steering:

1. A dedicated canonical wrapper, likely
   `scripts/runtime/forge_canonical_external_loop.py`, that reads this file or a
   sibling machine config.
2. A task manifest format that mixes the external benchmark families without
   contamination and records source/version/split for each item.
3. Adapter status for SWE-bench, Terminal-Bench, tau3-bench, CodeClash, and
   MultiAgentBench/MARBLE.
4. A run packet schema for `run_manifest.json`, `task_manifest.jsonl`,
   `model_roster.json`, `budget_ledger.jsonl`, `coordination_edges.jsonl`,
   `results.jsonl`, `failure_taxonomy.md`, and `decision_record.md`.
5. A stop-safe controller for `--iterations 100`, `--duration-hours N`,
   `--cost-cap-usd X`, and `--invalid-run-cap 5%`.
6. A separate evaluator pass that does not let the generator judge itself.
7. A native x86_64 SWE-bench execution environment for scaled runs, or an
   explicit slow-path warning on Apple silicon.

Until those exist, agents must run the strongest available subset and say so.

## Valid Closeout States

Only these closeout states are valid:

- `positive_lift_candidate`
- `measured_negative`
- `inconclusive_low_power`
- `contaminated_quarantine`
- `blocked_with_evidence`

Positive lift is not public proof until the claim gates pass.

## Claim Gates

The phrase "Dharma Swarm beats the best single model" is forbidden unless all
of the following are true:

1. At least 100 paired external tasks are valid.
2. The strongest single frontier control had equal or greater budget.
3. Best-of-N, Self-MoA, no-A2A PBV, and full A2A swarm arms ran.
4. Paired confidence interval lower bound is greater than 0.
5. Absolute lift is at least 5 percentage points, or the arena-specific lower
   confidence bound beats the control.
6. Resolved-per-dollar and resolved-per-token beat the strongest control by at
   least 10%, unless the claim explicitly says the swarm is not cost-efficient.
7. Invalid runs are below 5%.
8. Final-use proof exists for at least 30% of swarm-only wins.
9. Public benchmark claims have either official submission or replayable
   artifact bundle.

## Authority Boundaries

Forbidden without a separate explicit operator lease:

- archive fitness mutation;
- trainer mutation;
- production router mutation;
- trusted memory canon promotion;
- public benchmark submission;
- public claim of superiority;
- external outreach;
- paid action or bounty pursuit;
- standing daemon launch;
- destructive repo or filesystem cleanup.

Dense/local benchmark evidence may guide hypotheses and regression tests. It
does not change archive fitness. External acted receipts and official benchmark
evidence can become candidate sparse signal only after countersign and quorum.

## Minimum Receipt Packet

Every real run must write or point to:

- `run_manifest.json`
- `task_manifest.jsonl`
- `model_roster.json`
- `budget_ledger.jsonl`
- `coordination_edges.jsonl`
- `results.jsonl`
- `control_comparison.md`
- `failure_taxonomy.md`
- `decision_record.md`

For each task, the packet must include:

- benchmark family, version, split, and task ID;
- exact provider/model identity;
- budget cap and actual tokens/tool calls/cost;
- arm name and topology;
- verifier command or official harness receipt;
- contamination state;
- output artifact path and hash;
- final-use attribution for accepted swarm contributions;
- failure reason if unresolved or invalid.

## Operating Implications

1. The benchmark suite becomes the swarm's external gradient.
2. Coordination is not valuable unless it changes final verified output.
3. Forge Arena remains valuable as an internal gym, but not as reality proof.
4. Negative results are useful: they identify whether the bottleneck is model
   roster, topology, verifier weakness, tool affordance, handoff loss, or cost.
5. Evolution must be isolated until receipts prove the mutation improves the
   organism under controls.
6. The next large engineering move is a canonical external-loop wrapper, not
   another scattered report.

## Current Bottom Line

The vision is correct: repeated official external benchmark pressure through
the Dharma Forge Proving Ground is the single strongest test for whether Dharma
Swarm is a competitive organism.

The present implementation is partially ready:

- local Forge Arena mechanics exist;
- v0 produced a useful negative verdict;
- v1 has an honest offline scoreboard;
- v1 has a real SWE-bench Verified runner;
- the full multi-benchmark 100-iteration overnight harness is not yet unified.

Any agent encountering the legacy phrase "run Forge" must normalize it to
"run the Forge Proving Ground", preserve the internal-vs-external distinction,
and prefer the explicit Proving Ground command in all new receipts.
