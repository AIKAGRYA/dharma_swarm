# Dharma Forge Current Canon and Overnight Runbook

Date: 2026-07-04  
Status: source-of-truth map and run-readiness note; not a promotion receipt  
Branch/worktree: `/Users/dhyana/ds_forge_spine_v0` on `feat/rsi-lab`  
Runtime root: `/Users/dhyana/.dharma/forge_v1` locally; `/root/.dharma/forge_v1` on Agni

## Canonical Names

Use these names in new receipts and runbooks:

| Semantic Commons object | Use for | Do not confuse with |
| --- | --- | --- |
| `ForgeProvingGround` | The whole measurement/falsification system: taskbeds, control arms, grading, receipts, promotion gates. | Generic quality linting. |
| `ForgeRealityArena` | Historical Hydra/arena work-packet line: dense internal status gym, overnight arena missions, and measurement predecessors. | The current RSI Lab branch. |
| `ForgeRSILab` | Current Forge v2.2 "Honest Loop" implementation under `dharma_swarm/forge_v1/forge_v2`. | Older v1/v0 arena packets. |
| `NativeBenchmarkWorker` | A native x86/Docker worker that executes grade-only benchmark packets. Agni currently fills this role. | A conductor or source-of-truth owner. |
| `NativeBenchmarkConductor` | A coordination host that schedules/polls/syncs workers. `meghadharma` is a candidate for this role. | The benchmark worker itself. |

## Evolution Map

This is the shortest reliable history, from earliest Forge-adjacent surfaces to
the current branch.

1. **Quality Forge diagnostic** — `dharma_swarm/quality_forge.py` on main-family
   worktrees. This is a scoring/diagnostic helper, not a full evolution arena.
2. **Reward Forge v0** — historical branch `forge/dharma-reward-forge-v0`.
   It introduced sealed holdout/evolution-receipt ideas, but is branch-only.
3. **Forge Council / Hydra FQ1** — off-repo autonomy-spine missions under
   `~/.dharma/autonomy_spine`. These proved the receipt-first overnight pattern,
   but not a clean mainline product surface.
4. **External Beast / Measurement Guardian** — sparse external receipt and
   countersign lanes. Important boundary lesson: external/countersigned receipts
   are the only candidates for fitness authority.
5. **Forge Reality Arena v0/v1** — dense internal arena and later "Reality Arena
   Hydra" surface. `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md`
   found the live-ops launcher was missing and the real state was off-repo under
   `~/.dharma/forge_reality_arena*`.
6. **Reality Arena v2/v3.1/v4** — off-repo mission/receipt sequence that moved
   from internal status gym toward benchmark spine, soak runs, and transfer loops.
   Treat as historical evidence, not current run authority.
7. **Swarm Evolution Arena v0 Measurement** —
   `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md`
   and `scripts/runtime/forge_swarm_evolution_arena_v0_*`. This made the key rule
   explicit: positive "swarm evolution" requires budget-matched lift over
   best-single and same-budget Self-MoA, with sealed scoring and controls.
8. **Forge v1 external falsification harness** — `dharma_swarm/forge_v1/`.
   The canonical question became whether the organism improved versus strong
   controls, not whether activity increased.
9. **Forge v2 / RSI Lab v2.1.1 "The Honest Loop"** —
   `dharma_swarm/forge_v1/forge_v2/` on `feat/rsi-lab`. This added the DGM →
   real Forge grade JOIN, packet guard, promotion verifier, taskbed ledger,
   PR-suite harvester/validator/grader, and E4 statistical power discipline.
10. **Forge RSI Lab v2.2 current line** — the current head extends v2.1.1 with:
    canonical receipt replay/audit completeness, exact task-id native runner
    allocation, Agni grade-only proof runs, and the repo-native PR-suite
    harvest/validate/import loop.

## Current Cleanliness Verdict

**Source is now concentrated; history is not fully migrated.**

- Current source canon: `/Users/dhyana/ds_forge_spine_v0`, branch `feat/rsi-lab`.
- Current code locus: `dharma_swarm/forge_v1/forge_v2/`.
- Current runtime locus: `~/.dharma/forge_v1/`.
- Historical evidence remains split across:
  - `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md`;
  - `docs/specs/forge_packets/`;
  - `reports/agentops/work_packets/forge-*`;
  - off-repo `~/.dharma/forge_*` and `~/.dharma/autonomy_spine`.

This document is the current clean index. It does not import the whole old
Hydra state tree into git, because that would mix runtime logs with source canon.

## Semantic Commons Alignment

Forge now has explicit Semantic Commons names in:

- `docs/ontology/semantic_objects.yaml`
- `docs/ontology/semantic_aliases.yaml`
- `docs/ontology/SEMANTIC_COMMONS.md`

Use the canonical names above in new run ids, closeouts, and receipts. Legacy
strings such as "Dharma Forge Arena", "Forge Hydra", and "Forge v2.1" should map
back to `ForgeRealityArena` or `ForgeRSILab` depending on context.

## Overnight Readiness

### Safe tonight

A shadow-only overnight pass is safe if it is limited to:

- harvesting post-cutoff PR-suite candidates;
- validating FAIL_TO_PASS rows;
- importing validated fresh tasks into the taskbed DB;
- running grade-only native worker packets;
- syncing receipts;
- writing closeout reports.

It must keep these flags false:

- source/live code mutation;
- Darwin live apply;
- archive fitness mutation;
- public benchmark submission;
- public superiority/evolution claim;
- trusted memory canon promotion.

### Not safe yet

It is **not** ready for a promotion/evolution-claim overnight. Remaining blockers:

- no full fresh paired CONFIRM corpus near the E4 target;
- control-arm/budget parity packet still incomplete at powered scale;
- final-use proof and external/countersigned promotion battery are not complete;
- public SWE-bench remains `possible_pretrain`, so it cannot certify promotion.

## Host Placement

Use **Agni** as the current `NativeBenchmarkWorker`: it has the right role for
x86_64/Docker/real benchmark execution, and current Forge focused tests pass
there.

Use **meghadharma** as a candidate `NativeBenchmarkConductor`, not automatically
as the benchmark worker. It becomes "best worker" only after it proves:

1. the canonical repo is checked out at `feat/rsi-lab`;
2. Docker/native benchmark dependencies work;
3. the focused Forge suite passes;
4. an exact-ID grade-only packet resolves and syncs receipts without mutation.

## Repo-Native Harvest Loop

The previous Agni harvest loop was an ad-hoc script under
`/root/.dharma/forge_v1/task_harvests`. The repo-native replacement is:

```bash
python3 scripts/runtime/forge_pr_suite_harvest_loop.py \
  --run-id agni_pr_suite_harvest_$(date -u +%Y%m%dT%H%M%SZ) \
  --root /root/.dharma/forge_v1/task_harvests \
  --repo-root /root/ds_forge_spine_v0 \
  --taskbed-db /root/.dharma/forge_v1/taskbed.db \
  --duration-seconds 28800 \
  --max-cycles 32 \
  --sleep-seconds 600 \
  --limit-per-repo 2 \
  --max-pages 1 \
  --github-token-env GITHUB_TOKEN,GH_TOKEN \
  --json
```

If the host has either `GITHUB_TOKEN` or `GH_TOKEN` set, the harvester will use
it for the GitHub REST API. Without a token, long loops may hit the low
unauthenticated API quota and should fail as shadow evidence rather than minting
tasks from incomplete harvests.

Run it under `tmux` on Agni after the current `agni_rsi_harvest_2h` session
finishes or is explicitly superseded. Do not overlap two taskbed-import loops
unless the DB locking/duplicate-import behavior is intentionally being tested.

## Current Recommendation

Run one more all-night pass **only as shadow harvest + grade-only receipt
generation on Agni**. Let `meghadharma` conduct only if it is polling and syncing
Agni, not replacing Agni as the worker. Treat all results as candidate evidence
until the full E4/promotion battery is satisfied.
