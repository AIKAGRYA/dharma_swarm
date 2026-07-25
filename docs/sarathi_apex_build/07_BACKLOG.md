# 07 — Sarathi Closure Backlog

The organization/collapse lane is complete and landed through PR #821. The work
remaining is integration and proof, not another map or runtime scaffold.

## Completed baseline

- Canonical direct identity loader and wake-cycle body retained
  (`dharma_swarm/holon_bridge.py:106`; `dharma_swarm/holon_runtime.py:53`).
- Duplicate repo-root `holon/` package removed (`test ! -d holon`).
- Deterministic reversibility primitive and caller seam landed
  (`dharma_swarm/operator_core/reversibility_gate.py:223-239`;
  `dharma_swarm/holon_runtime.py:99-118`).
- Thin `holon_system` navigation facade and honest Sarathi projections landed
  (`find dharma_swarm/holon_system -type f -name '*.py' -print0 | xargs -0 wc -l`;
  `dharma_swarm/holon_system/sarathi/gateway.py:15-24`).
- Sprawl guard is clean on current main.

Reproduce the completed merge/collapse baseline with:

```bash
git show -s --format='%H %cs %s' 0beef7584
PYTHONPATH=$PWD /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/sprawl_guard.py
```

The exact scoped test commands and dated results are kept once in the estate
map's Section 9 rather than duplicated here.

## Packet 1 — governed effect and receipt

1. Introduce a typed action envelope containing execution identity, requested
   authority, effect scope, reversibility class, cost cap, and verifier contract.
2. Make the package-owned Sarathi runner pass the exact action through
   reversibility classification, an `ExecutionLease`, live spend accounting, and
   a bounded executor before any side effect.
3. Fail closed on missing/expired lease, budget, persistence, verifier, or receipt.
4. Bind the effect artifact, independent verifier, A2A task claim, transport
   acknowledgement, and runtime receipt to the same execution identity.

Done when one real bounded task reaches `ReceiptBound` and a denied task produces
no effect.

## Packet 2 — installed durable seat

1. Move talk/run behavior under `dharma_swarm` or deliberately package it so
   installed `dgc agent talk/run` works outside the repo checkout.
2. Upgrade `/holon/{name}/chat` to the safe dialogue provider, bounded LivingDock
   context, history handling, and normalized dialogue receipt path
   (`api/routers/holon.py:43-89`; `dharma_swarm/holon_bridge.py:198-241,277-305`).
3. Compose the direct holon entry with the existing Living Agent Kernel rather
   than adding a supervisor.
4. Emit build provenance and semantic-success heartbeats; test kill, restart,
   JSONL/receipt recovery, and resume.
5. Replace the two-boolean/tmux liveness promotion with the proposed typed proof
   gate (`dharma_swarm/holon_system/observability/proof_gates.py:6-11`;
   `scripts/runtime/codex_composer_wake_loop.py:1213-1257`).

Done when Sarathi works from an installed current-main build, survives restart,
and cannot report success without durable proof.

## Packet 3 — ecosystem end-to-end and burn-in

1. Converge `DHARMA_A2A`, `DHARMA_FLEET`, and `DS_TASKS`/`DS_DLQ` behind one
   explicit tested production contract (reproduce the split with
   `rg -n 'DS_TASKS|DS_DLQ|DHARMA_A2A|DHARMA_FLEET' dharma_swarm/a2a scripts/runtime scripts/governance`).
2. Run one current-main semantic A2A task through dispatch, lease, bounded effect,
   independent verification, reply, acknowledgement, receipt, and heartbeat.
3. Burn the seat in unattended, exercise kill/restart/resume, and measure
   consecutive semantic successes rather than process uptime.
4. Promote Sarathi to `DurableServiceProven`; only then set liveness flags and
   replicate the composition to other seats.

## Separate cleanup lane

Stale worktrees, old launch wrappers, agent-home code copies, and machine-local
Hermes/Dharma sidecars should be inventoried and retired or promoted separately.
Do not delete them as part of effect closure without confirming their active
process owners.
