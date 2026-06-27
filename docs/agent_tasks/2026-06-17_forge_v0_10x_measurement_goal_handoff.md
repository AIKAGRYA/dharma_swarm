# Forge v0 10x Measurement Goal Handoff

Date: 2026-06-17
Status: ready for operator GO on live-provider measurement, not armed for automatic mutation
Seed run dir: `reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight`
Branch observed: `telos-ai-seed-v0-from-sandbox`

## /goal

Run the Forge Swarm Evolution Arena v0 measurement loop at least 10 valid times before making any evolution claim or mutating any trainer, router, archive-fitness, prompt, tool, memory, or production behavior. Use the existing staged readiness packet as the seed unless a fresh preflight proves a better run dir. Produce a 10-run aggregate receipt that tells the swarm whether the full live Dharma swarm gives real signal above strong controls.

## Why This Goal Exists

The Forge idea is strongest when it acts as a closed evidence loop for rapid swarm evolution: sealed tasks, strong controls, decorrelated live roles, paired scoring, and receipts that can later drive trainer/router/roster improvements. The current v0 implementation is a measurement and evidence mechanism. It is not yet authorized as an automatic evolution engine.

The purpose of this goal is to collect enough repeated signal to decide whether to aim the next evolution cycle at the Forge mechanism itself, the roster/router, or the task/scoring design.

## Hard Gate

Minimum valid runs before mutation: `10`

Do not perform any of the following until the 10-run aggregate exists and the operator grants a second explicit lease:

- Build or train a model from the results.
- Mutate production routing, provider ranking, model hierarchy, or roster policy.
- Mutate archive fitness or mark any public benchmark claim.
- Set `external_confirmed=true`.
- Publish, submit, push, merge, release, or start a standing daemon.

Each run may spend live provider calls. Do not start the measurement loop without explicit operator GO.

## Known Ready State

Fresh preflight packet:

`reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight`

Observed readiness:

- `closeout_state: preflight_ready`
- `measurement_mode_allowed: true`
- `mode_decision: measurement_mode`
- `next_action: enter measurement mode with required controls`
- `task_pack_gate: green`
- `roster_gate: green`
- `roi_governor: green`
- `task_count: 3`
- `rubric_item_count: 30`

Verification already run before this handoff:

```bash
pytest -q tests/test_forge_swarm_evolution_arena_v0_taskpack_builder.py tests/test_forge_swarm_evolution_arena_v0_preflight.py tests/test_forge_swarm_evolution_arena_v0_measurement_runner.py
```

Result observed: `10 passed in 0.75s`

```bash
python3 -m py_compile scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py
```

Result observed: passed.

No active Forge tmux session was observed. `tmux ls` only showed `dharma_palantir_pilot_a2a_worker`.

## First Commands

Run these before any live measurement call:

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
git status --short --branch
pytest -q tests/test_forge_swarm_evolution_arena_v0_taskpack_builder.py tests/test_forge_swarm_evolution_arena_v0_preflight.py tests/test_forge_swarm_evolution_arena_v0_measurement_runner.py
python3 -m py_compile scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py
```

Then prove the seed run dir is still green:

```bash
python3 scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py \
  --run-dir reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight \
  --write-readiness-packet \
  --json \
  --strict-exit
```

If strict preflight fails, stop and repair the failed gate before starting run 1.

## 10-Run Measurement Protocol

Default live measurement command:

```bash
python3 scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py \
  --run-dir reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight \
  --timeout-seconds 120 \
  --max-tasks 3 \
  --json
```

Run it 10 times only after explicit GO. Treat each invocation as an independent measurement attempt. The runner should create per-run receipts under the run dir, including a nested `measurement_runs/<measurement_run_id>/` record. Use nested per-run files for aggregation, not just top-level files that may be overwritten by later runs.

Suggested operator loop after GO:

```bash
RUN_DIR=reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight

for i in 01 02 03 04 05 06 07 08 09 10; do
  python3 scripts/runtime/forge_swarm_evolution_arena_v0_preflight.py \
    --run-dir "$RUN_DIR" \
    --write-readiness-packet \
    --json \
    --strict-exit

  python3 scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py \
    --run-dir "$RUN_DIR" \
    --timeout-seconds 120 \
    --max-tasks 3 \
    --json
done
```

## Valid Run Criteria

A run counts toward the 10 only if all of these are true:

- Strict preflight was green immediately before the run.
- `swarm_lift_report.json` exists for that measurement run.
- The run has a unique `measurement_run_id`.
- Required controls are present: `best_single_full_budget`, `same_budget_self_moa`, and `full_live_dharma_swarm`.
- Candidate arms did not see sealed answers or scorer internals.
- Budget parity is preserved well enough for the paired comparison to remain meaningful.
- `trainer_built=false`.
- `production_router_mutated=false`.
- `archive_fitness_mutated=false`.
- `official_score_claimed=false`.
- `public_submission_performed=false`.
- `external_confirmed=false`.
- Any provider failure is recorded in receipts rather than silently ignored.

Invalid runs must remain in the evidence folder, but they do not count toward `valid_run_count`.

## Stop Conditions

Stop the loop and write a blocker receipt if any of these occur:

- The same blocker repeats for 3 consecutive run attempts.
- Strict preflight fails and cannot be repaired locally.
- Sealed task contamination is detected.
- Candidate arms can see scorer answers or rubric answers.
- Budget parity breaks enough to invalidate the comparison.
- Any authority flag flips true.
- Provider liveness collapses below the minimum viable roster.
- The operator budget or time cap is reached.

## Required Receipts Per Run

For each valid or invalid run, preserve or summarize:

- `swarm_lift_report.json`
- `decision_packet.md`
- `control_results.jsonl`
- `role_liveness_receipts.jsonl`
- `anti_goodhart_receipts.jsonl`
- `budget_ledger.jsonl`
- provider error and timeout receipts, if any

After every run, record:

- run index from 1 to 10
- measurement run id
- valid or invalid
- closeout state
- full live swarm score
- best single score
- Self-MoA score
- `swarm_lift`
- contamination status
- authority flag status
- notable provider failures

## Required 10-Run Aggregate

After 10 valid runs, write:

```text
reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight/ten_run_aggregate.json
reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight/ten_run_aggregate.md
```

Aggregate fields:

- `run_count_total`
- `valid_run_count`
- `invalid_run_count`
- closeout-state counts
- positive-lift count
- zero-or-negative-lift count
- blocked count
- mean `swarm_lift`
- median `swarm_lift`
- min and max `swarm_lift`
- bootstrap confidence interval if available, otherwise an explicit low-power caveat
- provider failure taxonomy
- contamination count
- authority flags, all expected false
- recommendation: `positive_lift_candidate`, `measured_negative`, `inconclusive_low_power`, `contaminated_quarantine`, or `blocked_with_evidence`

Do not discard negative or messy results. The aggregate is valuable only if failures survive as signal.

## Evolution Decision After 10 Valid Runs

After the aggregate is written, do not mutate automatically.

If the 10-run aggregate shows robust positive lift, prepare a second-stage proposal for the operator. A reasonable default threshold is at least 7 of 10 valid runs positive with mean lift above 0, or a bootstrap interval whose lower bound is above 0. If the result is weaker, classify it as `inconclusive_low_power` or `measured_negative` and recommend the smallest repair target.

Possible second-stage targets:

- Forge task/scoring quality if runs are noisy or low-power.
- Roster/router policy if specific roles repeatedly dominate or fail.
- Trainer design only after the operator grants an explicit training lease.
- Archive-fitness mutation only after an explicit archive lease.

## Closeout Report

The final `/goal` response must include:

- Whether 10 valid runs completed.
- Aggregate receipt paths.
- Commands actually run.
- Any invalid runs and why they were invalid.
- Final recommendation.
- Confirmation that no trainer, router, archive fitness, external claim, public submission, push, merge, or release occurred unless separately authorized.

