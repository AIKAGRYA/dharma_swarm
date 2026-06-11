# Forge Rehydration + Benchmark Evolution Pilot Goal

Date: 2026-06-12
Status: longrun goal handoff spec
Intended runner: Codex 5.5 `/goal` or `/longrun`
Primary mode: bounded implementation + verification loop

## Pasteable Goal Envelope

```text
/longrun /goal Codex 5.5: follow docs/agent_tasks/2026-06-12_forge_rehydration_benchmark_evolution_goal.md. Mission: rehydrate Dharma Forge into a main-owned, stop-safe benchmark evolution pilot, not standing autonomy. Truth rule: treat prior Forge/Hydra claims as hypotheses until fresh command output, artifact paths, or evaluator receipts prove them in this run. Scope: build only the smallest local Forge Arena v0 path needed for fresh taskpack preflight, one-feature coder->verifier->evaluator smoke gate, and at most one bounded measurement smoke. Authority: no external actions, public claims, standing daemons, archive-fitness mutation, provider/router mutation, protected identity edits, test deletion, new truth substrate, or wholesale Hydra imports. Dense benchmark results are Tier 1 training signal only. Close with changed files, verifier commands, receipt paths, BAR score, custody labels, closeout state, and exact blockers.
```

## Mission

Make Forge the swarm's practical learning lever again.

The operator's corrected thesis is accepted as the working hypothesis: the next
center is not enterprise "agentic code governance" sales. The next center is a
hard benchmark-and-receipt loop that teaches the swarm by running against real
or sealed tasks, comparing protocols, harvesting failures, and feeding only
verified lessons back into the organism.

The first longrun does not launch an open-ended Hydra. It rehydrates the Forge
surface into a reproducible, repo-owned pilot that can prove:

1. the current Forge/Hydra state and custody truth;
2. a green local Forge Arena v0 preflight on a fresh taskpack;
3. a one-feature coder -> verifier -> commit -> evaluator smoke gate;
4. one bounded measurement smoke;
5. exact receipts and stop conditions for the next sustained run.

## What This Must Not Become

- Not a Hydra resurrection or wholesale import from `~/.dharma`.
- Not a new daemon, runner, dashboard, memory store, truth store, command spine,
  receipt schema, or parallel autonomous-build framework.
- Not a benchmark-theater lane that turns dense local reps into fitness.
- Not a celebration of old `100/100` scorecards, 500 dense reps, or candidate
  lists. Those are useful history, not external proof.
- Not a sales sprint for agentic code governance. The commercial story comes
  after Forge earns receipts.
- Not mega-prompt minimalism. This is a repeated execution/evaluator regime, so
  use dense playbooks, explicit criteria, calibration examples, failure modes,
  and receipts.

## Required Skill Reading

Read these files before designing or editing prompts:

- `/Users/dhyana/.claude/skills/mega-prompt/SKILL.md`
- `/Users/dhyana/.claude/skills/spec-forge/SKILL.md`
- `/Users/dhyana/.claude/cabinet/systems/AUTONOMOUS_BUILD_BAR_v1.md`
- `/Users/dhyana/.codex/skills/codex-agent-loops/SKILL.md`

Apply the regime boundary from `mega-prompt`: this is a repeated-execution
launch/evaluator/harness prompt, so route to the dense `spec-forge` playbook
regime. Do not compress loop, coder, evaluator, or constitution prompts into
lean one-shot frames; instead emit explicit playbooks, criteria, calibration
examples, failure modes, and receipts.

Score this goal against the BAR before launch. Below 80 means no launch. 80-94
means viable with named risk. 95+ means SOTA-complete only if verifier
independence and inaccessibility are real, not just a same-run subagent.

## First Reads

Read these source families before edits:

- `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md`
- `docs/plans/2026-06-10-honest-spine-v2-decision-memo.md`
- `reports/agentops/work_packets/forge-reality-arena-status.json`
- `reports/agentops/work_packets/forge-reality-arena-master-cycle-50.json`
- `reports/agentops/work_packets/forge-measurement-guardian-cycle-003.json`
- `~/.dharma/forge_reality_arena_master/shared/codex_overnight_handoff.md` if readable
- `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md`
- `scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py`
- `scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py`
- `scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py`
- `tests/test_forge_swarm_evolution_arena_v0_taskpack_builder.py`
- `tests/test_forge_swarm_evolution_arena_v0_preflight.py` if present
- `tests/test_forge_swarm_evolution_arena_v0_measurement_runner.py`
- `dharma_swarm/spine/`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/a2a/`
- `scripts/governance/check_a2a_readiness.py`
- `tests/test_a2a_readiness_gate.py`
- `docs/governance/ACTIVE_TRACK.yaml`

Use exact file existence and test results over inherited narrative. If a cited
artifact is absent, mark it `STALE_REF` or `MISSING` rather than carrying the
claim forward.

## Fake-Green Traps

- `score: 100`, Docker smoke, 500 dense reps, and 0 authority violations are
  local evidence only.
- `candidate_for_human_review` is not an external acted receipt.
- A2A, NATS, tmux, dashboard, heartbeat, or file-mirror green is not completion.
- A public PR opened is not enough; maintainer action, merge, payment, or other
  counterparty action is the receipt.
- Guardian cycle 003 confirms only 3 receipts in 1 domain; the quorum
  `N >= 5` and `M >= 3` is unmet.
- SWE-bench-style/local benchmark lift is Tier 1 training signal only.
- `receipt_json`, OTel spans, reports, cards, and work packets are projections
  unless tied to canonical `EvidenceReceipt`, `RuntimeReceipt`, and
  idempotency records.
- Work packets without replayable commands, current runtime provenance, and
  artifact existence checks are narrative artifacts.

## Authority Boundaries

Dense benchmarks are Tier 1 training signal. They may guide hypotheses,
regression tests, and candidate improvements. They do not touch archive fitness.

External acted receipts are Tier 2 sparse signal. They require Guardian or
equivalent countersign and quorum before any fitness-authority path.

Do not start standing autonomy; instead run bounded commands with explicit
duration, stop conditions, and receipts.

Do not perform external outreach, public benchmark submission, deploy, push/PR,
payment, live trading, archive-fitness mutation, trusted-memory promotion, or
production router mutation unless the operator gives an explicit lease in the
current run.

Do not import off-repo Hydra state wholesale; instead extract only narrow
launcher, status, custody, and receipt contracts.

Do not create or use parallel truth primitives such as `WorkCommand`, `WorkRun`,
`WorkReceipt`, `command_runs`, `work_runs`, a new command ledger, or a new
receipt store. Use the existing Runtime Truth Spine: `ExecutionIdentity`,
`spine.EvidenceReceipt`, `RuntimeReceipt`, `RuntimeStateStore`, and
`IdempotencyRecord`.

## Custody Labels

Use these labels in any matrix, receipt, status packet, or closeout:

- `SOURCE_OWNED`: authoritative owner surface, not a dashboard projection.
- `PROJECTION_ONLY`: readable projection over another owner.
- `JOINED`: carries canonical identity and writes runtime facts/receipts.
- `ADAPTER_READY`: can carry identity, but enforcement is incomplete.
- `OPT_IN_ONLY`: safe only behind explicit opt-in.
- `LEGACY`: old path, not receipt-authoritative.
- `MISSING`: cited path or module is absent.
- `STALE_REF`: cited artifact cannot be reproduced from current checkout.
- `QUARANTINE`: unsafe to use as authority until repaired.
- `DRY_RUN_ONLY`: candidate signal only.
- `EXTERNAL_GATED`: blocked on operator, Guardian, or acted external receipt.
- `LEASED_MUTATION`: scoped mutation with owner, surfaces, expiry, rollback.
- `AMBER`: partial proof or receipt gap.
- `RED`: forged, mismatched, unsafe, or false-green claim.
- `PAUSED_UNTIL_AUTHORITY_INPUT`: honest stop, not failure.

## BAR Contract And Durable State

Before implementation, create or update the pilot's durable state under the
Forge packet/spec area:

- `contract.md` with at least 20 numbered, machine-checkable criteria seeded
  from BAR sections A-E.
- `status.md` with current phase, last command, current blocker, and next
  admissible action.
- `attempts.md` with every failed command/blocker and the reset rule.
- `RECEIPT.md` or a JSON packet with command outputs, hashes, custody labels,
  and final authority statement.
- `archive/` or iteration snapshots for meaningful attempts if the longrun
  branches strategies.

The single numeric gradient metric for the pilot is `swarm_lift`:

```text
full_live_dharma_swarm_score - max(best_single_full_budget_score, same_budget_self_moa_score)
```

This metric is candidate evidence only. It is not archive fitness.

The verifier must exercise behavior from outside the builder's claimed
rationale. If true verifier inaccessibility is not possible in this environment,
state that residual risk instead of calling the run SOTA-complete.

## Phase 0 - Baseline Truth

Run from `/Users/dhyana/dharma_swarm`:

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
git status --short --branch
git log --oneline -12
```

Record a baseline receipt under `reports/forge/` or `reports/agentops/work_packets/`
with branch, HEAD, dirty-worktree truth, active tracks, custody findings, and
the exact artifacts that are missing or stale. Include whether the latest Forge
handoff was readable before any launcher or restart-related work.

If this work becomes an active implementation lane, add or propose an
`ACTIVE_TRACK.yaml` entry named `forge-benchmark-evolution-pilot-2026-06` serving
`research-depth`, with owned surfaces and acceptance criteria. If policy or dirty
state makes editing `ACTIVE_TRACK.yaml` unsafe, document the proposed entry in
the baseline receipt instead.

## Phase 1 - Spec-Forge Harness Contract

Create or update a compact Forge pilot spec under:

- `docs/specs/forge_packets/FORGE_REHYDRATION_BENCHMARK_EVOLUTION_SPEC.md`

It should state the build contract, not re-litigate the whole mythology. Include:

- objective and non-goals;
- current custody map of Forge generations;
- surfaces that are main, branch-only, untracked, off-repo, or missing;
- benchmark ladder;
- runtime truth requirements;
- receipt schema or packet shape;
- BAR score and lowest-scoring gaps;
- frozen `contract.md` criteria;
- evaluator role and sensor;
- stop policy;
- next sustained-run gate.

Emit the prompt pack as first-class deliverables under:

- `docs/specs/forge_packets/forge_rehydration_prompt_pack/INITIALIZER.md`
- `docs/specs/forge_packets/forge_rehydration_prompt_pack/CODER.md`
- `docs/specs/forge_packets/forge_rehydration_prompt_pack/EVALUATOR.md`

`INITIALIZER.md` initializes the pilot, captures baselines, prepares the taskpack,
and writes the progress file.

`CODER.md` uses one-feature-per-session discipline. A coder reads the constitution
and features cold, selects one highest-priority unverified feature, runs the
pre-work smoke, implements only that feature, runs its verifier, updates status,
commits if allowed, and records evidence.

`EVALUATOR.md` is a skeptical independent verifier. Calibrate it on the run's
real sensor. If tonight's sensor is `tmux capture-pane` text frames, include
3-5 graded examples of tmux text evidence and failure cases. The evaluator owns
the `verified` flag; builders never flip it.

Prompt hygiene metric: 0 violations for reasoning-echo instructions, aggressive
trigger-language stacks, prestige quality anchors, and bare negations. Use
functional criteria and negation+redirect pairs.

Provider/model roster selection must be resolved from current local truth
(`dkeys`, `model_hierarchy`, runner output, or explicit provider smoke result),
not hardcoded mythology. If the current runner hardcodes roles, record that as a
custody/measurement limitation.

## Required Canon Lines For The Prompt Pack

`CONSTITUTION` material and `CODER.md` must carry these exact sentences or rules:

1. "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."
2. "Only mark features as passing after careful testing."
3. "Leave the environment in a clean state, appropriate for merging to a main branch."
4. "Implement a solution that works correctly for all valid inputs, not just the test cases. If the task is unreasonable or infeasible, or if any of the tests are incorrect, please inform me rather than working around them."
5. "Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly."
6. Rollback-on-red: an evaluator red verdict triggers git revert of that feature's commit; status returns to `not_started` with a failure note in the progress file. A red feature never stays merged.
7. Re-planning authority: at session start, after reading progress and features, the agent may re-prioritize feature order based on what it learned, logging the re-plan and reason to the progress file. Feature definitions, steps, and verification criteria remain immutable.

If a `features.json` is created, feature `steps` are behavioral, not
implementation prescriptions. Builders may set `status` only. The evaluator
alone may set `verified`.

## Phase 2 - Local Forge Arena Rehydration

Prefer `/tmp` for new run directories until the harness is green:

```bash
RUN_DIR=/tmp/forge-arena-v0-$(date -u +%Y%m%dT%H%M%SZ)
python3 -m py_compile scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py
pytest -q tests/test_forge_swarm_evolution_arena_v0_taskpack_builder.py tests/test_forge_swarm_evolution_arena_v0_preflight.py tests/test_forge_swarm_evolution_arena_v0_measurement_runner.py --tb=short
python3 scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py --output-dir "$RUN_DIR" --json
python3 scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py --run-dir "$RUN_DIR" --write-readiness-packet --json --strict-exit
```

If a test file is missing, mark it `MISSING` and either create the narrow test
or remove it from the command with an explicit receipt. Do not report a green
preflight from old prose; instead run the current preflight.

Preflight is green only when `task_pack_gate=green`, `roster_gate=green`,
`roi_governor=green`, and `measurement_mode_allowed=true` are all true in
fresh artifacts from this run.

## Phase 3 - Runtime Truth And A2A Gate

Before trusting multi-agent measurement, run the smallest truth slice that exists:

```bash
PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 pytest -q tests/test_runtime_state_invariants.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_runtime_truth_spine_v2_adapters.py tests/test_spine_persistence_invariant.py --tb=short
PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 pytest -q tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_spec_conformance.py --tb=short
PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 pytest -q tests/test_a2a_readiness_gate.py --tb=short
python3 scripts/agents/a2a_roundtrip_perplexity_computer.py
```

If `tests/test_a2a_readiness_gate.py` fails because
`dharma_swarm.operator_core.a2a_task_lifecycle` is missing, either repair the
missing receipt layer narrowly or classify the readiness gate as `MISSING` /
`QUARANTINE`. Core A2A passing does not equal readiness passing.

For any live send path, distinguish transport publish, handler delivery, domain
receipt, semantic reply, and completion.

For any side effect, idempotency must be acquired before the side effect.
Receipt chains must tie together `run_id`, `trace_id`, `correlation_id`,
`task_id`, and `idempotency_key`.

## Phase 3.5 - Pre-Launch Smoke Gate

Before any unattended or multi-hour run, drive exactly one feature through the
full observed loop:

1. fresh-context coder reads the pilot spec, prompt pack, progress file, and feature;
2. coder runs the baseline smoke command before new work;
3. coder implements one feature only;
4. coder runs the feature verifier and records tool evidence;
5. coder updates `status` only and commits only if allowed by the current lease;
6. evaluator re-verifies from the real sensor and flips `verified` only on proof;
7. rollback path is exercised or at least dry-run documented;
8. prompt hygiene audit passes with zero violations.

If the smoke gate fails, fix the harness first. Do not spend hours on the loop
while the loop itself is unproven.

## Phase 4 - Measurement Smoke

Only after green preflight and smoke gate:

```bash
dkeys test
python3 scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py --run-dir "$RUN_DIR" --max-tasks 1 --timeout-seconds 240 --json
```

Valid closeouts:

- `blocked_with_evidence`
- `inconclusive_low_power`
- `measured_negative`
- `positive_lift_candidate`
- `contaminated_quarantine`

`positive_lift_candidate` remains candidate-for-human-review only.

## Phase 5 - Full Local Pilot

Only after the one-task smoke produces a useful receipt:

```bash
python3 scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py --run-dir "$RUN_DIR" --timeout-seconds 240 --json
```

Compare full live swarm against best-single-full-budget and same-budget Self-MoA.
Enforce budget parity, role liveness, contamination checks, and an ROI governor.

Stop or pivot if:

- receipts increase but evidence quality does not;
- fewer than 3 live provider roles are available for the intended measurement;
- role liveness collapses;
- budget parity breaks;
- contamination appears;
- the same blocker repeats three times;
- task, intervention, hypothesis, and next action all repeat;
- provider failures make the run a provider test rather than a swarm test.

Valid full-run closeouts are only:

- `positive_lift_candidate`
- `measured_negative`
- `inconclusive_low_power`
- `contaminated_quarantine`
- `blocked_with_evidence`

The final authority fields must remain false unless an explicit operator lease
changes the run scope: no trainer, no router mutation, no archive fitness
mutation, no official score claim, no public submission, and no
`external_confirmed`.

## Sustained-Run Stop Conditions

Stop before a sustained or unattended loop if any of these are true:

- launcher, status, or handoff contract is missing or unread;
- dirty or untracked artifacts lack custody labels;
- identity, runtime receipt, or idempotency-before-side-effect is missing;
- A2A readiness import failure is unclassified;
- A2A loopback is being treated as external or AGNI proof;
- fewer than 3 live provider roles are available;
- benchmark contamination or budget-parity break appears;
- the same blocker repeats three times;
- any external, public, router, fitness, or protected-identity mutation would be
  needed without an explicit operator lease.

## Phase 6 - Failure Harvest

Every failed or blocked run becomes one of:

- a regression test;
- a failure capsule;
- a forbidden pattern;
- a custody label update;
- a next packet with explicit authority requirement.

Do not let failure become narrative residue. Instead, make it executable or
classify why it cannot yet be executable.

## Phase 7 - External Proof Ladder

After the local Forge pilot is reproducible, graduate evidence in this order:

1. local rehydration with runtime provenance, dry-run replay, and no fitness
   mutation;
2. official benchmark instance through the official harness, starting with one
   SWE-bench Verified or Terminal-Bench-compatible task;
3. maintained OSS PRs where maintainer action is the receipt;
4. paid microtasks or eval gigs with permission to cite anonymized receipts;
5. escrowed bounties only when merge and payout are tracked;
6. Guardian countersign and transfer gate;
7. quorum of at least 5 confirmed receipts across at least 3 domains;
8. public writeup only after reproducible receipts exist.

Do not sell the governance sprint first; instead earn receipts that make any
future offer obvious.

## Acceptance Criteria

The run is successful if it closes with:

- baseline receipt written;
- BAR score recorded with named residual risk;
- `contract.md`, `status.md`, `attempts.md`, and final receipt packet written
  or explicitly classified as blocked;
- Forge custody map updated or created;
- latest Forge handoff read or explicitly marked unreadable/missing;
- prompt pack emitted and prompt-hygiene checked;
- local Forge scripts compile;
- Forge harness tests either pass or missing tests are created/classified;
- fresh taskpack preflight run recorded;
- one-feature smoke gate attempted and honestly closed;
- one-task measurement smoke attempted only if gates are green;
- role-liveness and budget ledger recorded if measurement runs;
- runtime truth/A2A readiness status classified without overclaim;
- `swarm_lift` computed only if full local pilot runs, with paired deltas and
  bootstrap CI if supported by the runner;
- final authority statement includes `archive_fitness_changed=false` unless
  quorum plus operator lease exists;
- no external action, archive fitness mutation, public claim, or standing
  autonomy activation;
- final closeout lists changed files, verifier commands, receipt paths, custody
  labels, and exact blockers for the next sustained run.

## Final Report Shape

Close with:

```text
Outcome:
Changed files:
Commands run:
Receipts/artifacts:
Custody states:
What is now runnable:
What remains blocked:
Next admissible /goal:
```
