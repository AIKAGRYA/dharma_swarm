# Forge PR #723 Production Audit

Date: 2026-06-30
Audited branch: `codex/routing-canon-20260630`
PR: #723 `routing: canonicalize Forge benchmark lanes`
Head: `70922cf88e2036407b902a54f4f4da0a45f77bb8`
Status: draft, CI green on 2026-06-29 base, not yet current-main verified

## Verdict

Do not merge #723 as a single production PR yet.

The branch contains a valuable Forge substrate: offline equal-budget harness,
hidden verifier tests, model-pool/routing consolidation, SWE-bench adapter,
and first verifier-role Forge v2 slice. It is a good draft and should remain
the Forge staging lane.

It is not production-ready as-is because live entrypoints and operator runbooks
are not coherent enough for handoff, and the branch bundles three risk classes:
canonical provider routing, offline benchmark harness, and live RunPod/SWE-bench
execution.

## Verified Locally

- `pytest -q tests/test_forge_v1.py tests/test_forge_v1_full.py tests/test_forge_v1_providers.py tests/test_forge_v2.py tests/test_model_pool.py tests/test_model_pool_api.py tests/test_model_status_projection.py tests/test_runtime_provider.py tests/test_env_alias_normalization.py tests/test_api_keys.py tests/test_evolution_roster.py tests/test_zhipu_provider.py tests/test_routing_surface_inventory.py --tb=short`
- Result: `176 passed, 1 skipped, 1 warning in 22.06s`
- `python -m dharma_swarm.forge_v1.run_real --help` works.
- `python -m dharma_swarm.forge_v1.canonical --help` works.
- `python -m dharma_swarm.forge_v1.forge_v2.runner --help` works.
- `python -m dharma_swarm.forge_v1.autoloop --help` fails.

## Blockers Before Production Merge

1. `autoloop` CLI is broken.

   `python -m dharma_swarm.forge_v1.autoloop --help` raises a circular import:
   `autoloop.py` imports `autoloop_matrix.py`, while `autoloop_matrix.py`
   imports from `autoloop.py`. The documented matrix command therefore fails
   before parsing arguments.

2. RunPod runbook is stale against the actual CLI.

   `docs/RUNPOD_SWEBENCH_RUNBOOK.md` and `scripts/runpod_swebench_setup.sh`
   tell an operator to run flags like `--n`, `--model`, `--namespace`,
   `--cache_level`, and `--max_workers` on `dharma_swarm.forge_v1.run_real`.
   The current `run_real` CLI accepts `--instances`, `--best-of-n`, `--budget`,
   `--grade-timeout`, `--swarm-second-model`, and `--single-family-standin`.

3. Live equal-budget accounting needs invalid-overrun semantics.

   Offline `TokenBroker` can reject before spend because candidate token cost is
   known. Live model calls only know token usage after the provider returns.
   Several live arms call the provider first, then reject if over budget. That
   means an over-budget call may have been spent but excluded from `tokens_spent`.
   For production-grade equal-budget claims, rejected live calls must either be
   pre-reserved or recorded as invalid budget overruns with actual tokens.

4. #723 is not current-main verified after #731.

   Current `origin/main` is `f84f40344` after #731. #723 is draft and green on
   older CI. A no-write merge-tree probe produced a tree without conflict, but
   this branch still needs a real rebase/merge-forward and fresh CI before any
   merge decision.

5. Optional SWE-bench tests are not fully hermetic.

   `tests/test_forge_v1_swebench.py` marks live Docker grading behind
   `FORGE_SWEBENCH=1`, which is good. Its "offline" shape tests still call the
   SWE-bench/HF dataset loader when the optional package is installed. For a
   production CI contract, separate pure unit shape tests from cached/network
   integration tests.

## Recommended Split

1. PR A: provider/model routing only.

   Include `api_keys.py`, `model_defaults.py`, `model_hierarchy.py`,
   `model_pool.py`, `providers.py`, `runtime_provider.py`, routing docs, and
   routing tests. No Forge runners. This can be production-hardened first.

2. PR B: offline Forge harness only.

   Include `forge_v1/harness.py`, offline fixtures/models/swarm/evolution,
   offline tests, and the honest `swarm_lift` scoreboard. No live provider,
   Docker, RunPod, or SWE-bench execution.

3. PR C: live SWE-bench adapter and RunPod handoff.

   Include `swebench_real.py`, `run_real*`, `canonical.py`, RunPod docs/scripts,
   and explicit live-gated tests. Block merge until the runbook commands match
   the actual CLI and a one-instance live receipt exists.

4. PR D: Forge v2 verifier-role slice.

   Include `forge_v2/*` after A-C are stable. Treat it as a research slice with
   closeout states and receipts, not production autonomy.

## Operator Decision Needed

Define the first production contract for Forge:

- Option 1: "Forge is an offline scoreboard and regression harness."
- Option 2: "Forge is a live SWE-bench measurement runner with RunPod handoff."
- Option 3: "Forge is an autonomous repair/evolution loop."

The least risky production landing is Option 1 first, then Option 2. Option 3
should wait until budget parity, verifier independence, receipt immutability,
and rollback/authority boundaries are all enforced.

## Strategic Read

The larger vision docs are consistent: Forge is the learning lever, not a
standing Hydra and not a fitness authority yet. `swarm_lift` is candidate
training signal only. Production readiness is not "many agents ran"; it is a
bounded, replayable, budget-matched, contamination-aware measurement with
fresh receipts and a closeout state.
