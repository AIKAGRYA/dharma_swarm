# 00 — Start Here: Sarathi Holon System Organization v1.1

Status: **organization and collapse lane in progress**. Do not use this document
to claim a living Sarathi.

## Locked sentence

Sarathi is the apex holon that **uses** persistent-agent lineage, the
LivingAgentKernel, the canonical holon runtime, and existing orchestration, then
**adds** deterministic reversibility gating and operator-facing continuity. It is
not a parallel rewrite and not identity docs alone.

## What changed in v1.1

- The reversibility gate and wake brick already landed on the dirty
  `agent/magpie-seed` line at `f18fe8476`; this clean lane ports it instead of
  re-deriving it.
- Work happens on `feat/holon-system-collapse-base`, a worktree from
  `origin/main`.
- The standalone `holon/` fork is treated as a duplicate body to collapse in
  Phase B, not a canonical runtime.
- The done condition is machine-checkable: `python3 scripts/governance/sprawl_guard.py` must exit `0`.

## What is organized here

This front door connects four things that were previously easy to confuse:

1. **Source code:** repo-owned Python, tests, schemas, docs.
2. **Runtime state:** mutable identities, inboxes, heartbeats, and receipts under `~/.dharma`.
3. **Side ecosystem:** Nous Hermes Agent under `~/.hermes`, including `hermes-m5` as a field-ops peer, not a dharma holon lineage source.
4. **Proof gates:** deterministic checks and receipts that decide when claims can be promoted.

## Current proof status

| Claim | Evidence | Status |
|---|---|---|
| Clean branch exists | `git branch --show-current` → `feat/holon-system-collapse-base`; HEAD `8a3a2e657` after first port commit. | Done |
| Gate ported | `dharma_swarm/operator_core/reversibility_gate.py`; `tests/test_reversibility_gate.py`; `holon_runtime.py` accepts caller-supplied `planned_action`. | Done |
| Wake profile has Sarathi | `scripts/runtime/codex_composer_wake_loop.py` registers `sarathi` as a `WakeProfile`. | Done |
| Scoped gate tests | `.venv/bin/python -m pytest tests/test_reversibility_gate.py tests/test_holon_runtime.py tests/test_codex_composer_wake_loop.py -q` → `39 passed in 0.62s`. | Done |
| Collapse spine | `holon/` fork still exists on the clean branch at this point. | Not done |
| Facade package | `dharma_swarm/holon_system/` is not yet rebuilt fresh on this clean branch. | Not done |
| Sarathi liveness | No unattended proof and no `wake_loop_active=true` claim. | Not alive |

## Surface claim for this lane

```yaml
surface: sarathi_apex_holon_system_v1_1
canonical_code_home: dharma_swarm/holon_system plus canonical dharma_swarm/holon_*.py substrate
canonical_runtime_home: ~/.dharma/agents/sarathi and ~/.dharma/a2a_bus/*/sarathi*
canonical_doc_home: docs/sarathi_apex_build
forbidden_new_files:
  - duplicate load_holon implementations
  - duplicate holon_wake_cycle implementations
  - new orchestrator/router/task-store/bus/receipt spine
proof_before_alive:
  - tests for reversibility gate and holon runtime
  - python3 scripts/governance/sprawl_guard.py exits 0
  - unattended wake receipt before wake_loop_active=true
```
