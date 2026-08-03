# 00 — Start Here: Sarathi Holon System

Status: **collapse base landed; effect and durable-service closure remain**.
Do not use this document to claim a living Sarathi.

For current terminology, runtime-family boundaries, and evidence routes, read
the canonical doorway: [`../SARATHI.md`](../SARATHI.md).

## Locked sentence

Sarathi is intended to be the apex holon that **composes** persistent-agent
lineage, the Living Agent Kernel, the direct holon runtime, canonical provider
routing, existing orchestration/A2A, and deterministic authority gates, then
adds operator-facing continuity. It is not a parallel rewrite and not identity
documents alone.

## Landed baseline

- PR #821 merged the clean collapse lane into main at `0beef7584`.
- The duplicate repo-root `holon/` package was removed.
- `load_holon` and `holon_wake_cycle` each have one canonical definition.
- The reversibility primitive, runtime seam, thin `holon_system` facade, Sarathi
  projections, and sprawl guard are present on main.
- The facade's Sarathi gateway and pulse correctly emit
  `wake_loop_active=false` and `alive_claim=false`
  (`dharma_swarm/holon_system/sarathi/gateway.py:15-24`;
  `dharma_swarm/holon_system/sarathi/pulse.py:12-25`).

Reproduce the merge/collapse claims with:

```bash
git show -s --format='%H %cs %s' 0beef7584
test ! -d holon && echo 'root holon fork absent'
PYTHONPATH=$PWD /Users/dhyana/dharma_swarm/.venv/bin/python \
  scripts/governance/sprawl_guard.py
```

The original branch/worktree names and test counts in the dated subdocuments are
historical evidence of that merge, not current deployment facts.

## Proposed proof level

```text
IdentityPresent
  -> DialogueProven
  -> ProposalCycleProven
  -> GovernedEffectProven
  -> ReceiptBound
  -> DurableServiceProven
```

This build-history file does not assign a current promotion level; the estate
map keeps the dated witness and exact re-run commands. The runner asks which
action should happen next (`scripts/holon_run.py:32-62`) and does not pass
`planned_action`, `spend_fn`, or an execution lease
(`scripts/holon_run.py:66-87`). The six names above are proposed promotion types;
current source still uses weaker booleans
(`dharma_swarm/holon_system/observability/proof_gates.py:6-11`).

## Surface contract

```yaml
surface: sarathi_apex_holon_system
holon_body_reference: docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md
canonical_runtime_primitives:
  - dharma_swarm/holon_bridge.py::load_holon
  - dharma_swarm/holon_runtime.py::holon_wake_cycle
  - dharma_swarm/operator_core/living_agent_kernel.py
  - dharma_swarm/operator_core/execution_lease.py
  - dharma_swarm/operator_core/reversibility_gate.py
canonical_runtime_home: ~/.dharma/agents/sarathi
forbidden:
  - duplicate identity loader or wake-cycle body
  - new provider router, orchestrator, task store, A2A bus, or receipt spine
  - alive claim from PID, tmux, identity, heartbeat, or proposal alone
proposed_promotion_gate: DurableServiceProven
current_enforcement: not_composed
current_candidate_helper: sprawl_guard_clean_and_wake_loop_active_booleans
```

The next work is specified in [`07_BACKLOG.md`](07_BACKLOG.md).
