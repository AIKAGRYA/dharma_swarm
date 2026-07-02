# Forge Lane Protection Map - 2026-07-01 JST

## Purpose

Record the active Forge surfaces so adjacent cleanup does not overwrite,
duplicate, or prematurely merge work already in motion.

No Forge code, worktree, branch, run artifact, process, PR, VM, or router/Darwin
state was changed while producing this map.

## Protected Active Lanes

### 1. Forge v1/v2 scoreboard WIP

- Path: `/Users/dhyana/ds_forge_v1_scoreboard`
- Branch: `forge-v1/tokenbroker-scoreboard-20260620`
- Head: `d8bca7aab20af7871cff4ef46d08227cdb0923fa`
- State: dirty WIP; broad provider/model/runtime changes plus untracked
  `dharma_swarm/forge_v1/autoloop.py`, `canonical.py`, `forge_v2/`, and v2
  tests.
- Active processes observed: multiple `codex exec -C
  /Users/dhyana/ds_forge_v1_scoreboard` workers.
- Boundary: do not edit, rebase, split, test-fix, or stage this worktree from
  another lane without an explicit Forge handoff.

### 2. Forge v2.1 Learning Spine scope

- Path: `/Users/dhyana/.dharma/forge_v1/learning_spine_scope_20260701`
- Fresh outputs: `00_scope_synthesis.md`, `01_architecture_contract.md`,
  `02_signals_learning_store.md`, `03_router_registry_bridge.md`,
  `04_darwin_evolution_bridge.md`, `06_preflight_promotion_plan.md`, plus logs.
- Active processes observed: Codex agents writing learning-spine outputs under
  this scope and reading `/Users/dhyana/ds_forge_v1_scoreboard`.
- Current verdict from the scope: ready for a narrow shadow-only build, not for
  live evolutionary mutation.
- Boundary: no key reads, no second router, no Darwin apply calls, no live router
  mutation, no promotion from public SWE-bench evidence, and no implementation
  inside the dirty scoreboard worktree.

### 3. PR #723 Forge/routing staging lane

- Path: `/Users/dhyana/ds_routing_canon_20260630`
- Branch: `codex/routing-canon-20260630`
- Head: `70922cf88e2036407b902a54f4f4da0a45f77bb8`
- PR: #723, draft, `routing: canonicalize Forge benchmark lanes`
- State: clean worktree at inspection time.
- Prior audit: `forge_pr723_prod_audit.md`
- Boundary: keep as staging until split into routing, offline harness, live
  SWE-bench/RunPod, and Forge v2 verifier-role decisions. Do not merge as one
  production PR.

### 4. Dharma Forge Proving Ground 10/10 lanes

- Path: `/Users/dhyana/ds_forge_proving_ground_10_10_20260626`
- Branch: `codex/dharma-forge-proving-ground-10-10-20260626`
- Head: `50c8e2b7556258d80839e9860065dad488d855cc`
- State: dirty with Makefile and Semantic Commons changes plus untracked Forge
  proving-ground modules, docs, fixtures, and tests.

- Path: `/Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626`
- Branch: `droid/dharma-forge-proving-ground-10-10-20260626`
- Head: `50c8e2b7556258d80839e9860065dad488d855cc`
- State: staged/untracked proving-ground implementation, including a staged
  `.venv` entry and `forge_swebench_adapter.py` follow-on files.

- Boundary: these are separate 10/10 readiness attempts. Do not consolidate,
  dedupe, or clean their deltas without lane-owner approval.

### 5. Forge SWE-bench VM

- Runtime: Colima VM `forge-swebench`
- Observed processes: `colima daemon start forge-swebench`, `limactl hostagent`
  for `colima-forge-swebench`, and the matching SSH mux.
- Boundary: treat as active infrastructure. Do not stop or repurpose without an
  explicit operator lease.

## Safe Coordination Rule

Use fan-out for read-only audits, critique, report synthesis, and independent
test-plan design. Use serial ownership for code changes and PR repair.

Recommended merge/build order:

1. Routing/model-provider contract only.
2. Offline Forge scoreboard and regression harness.
3. Live SWE-bench/RunPod handoff with current CLI docs and one-instance receipt.
4. Forge v2 verifier-role slice.
5. Forge v2.1 Learning Spine shadow layer.
6. Private/fresh enterprise taskbed, starting with `enterprise_invoice_exception_v0`.

## Operator Decisions Needed

1. Pick the first production contract: offline scoreboard, live SWE-bench runner,
   or autonomous repair/evolution loop. The lowest-risk first landing remains
   offline scoreboard.
2. Confirm whether a clean implementation worktree should be created for Forge
   v2.1 Learning Spine, with minimal Forge v1/v2 code ported from the dirty
   scoreboard lane.
3. Decide whether the active learning-spine agents should continue to closeback
   or be reaped after their outputs are inspected.
4. Define the private/fresh enterprise taskbed shape and baseline difficulty
   floor before any promotion-capable Forge run.
5. Keep Forge in its own lane while other cleanup proceeds around open PRs,
   receipts, and non-Forge governance debt.
